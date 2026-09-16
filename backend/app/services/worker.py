import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.models import IngestTask, Question, SourceImage, SourcePost
from app.utils.text import normalize_question_text

logger = logging.getLogger(__name__)


async def run_task(
    task_id: int,
    *,
    session_factory,
    ocr,
    llm,
    low_confidence_threshold: float = 0.6,
) -> None:
    async with session_factory() as session:
        task = await session.get(IngestTask, task_id)
        # 允许 pending（重试直调）与 processing（worker 领取后），其余跳过
        if task is None or task.status not in ("pending", "processing"):
            return
        post = await session.get(SourcePost, task.post_id)
        images = (
            await session.execute(
                select(SourceImage).where(SourceImage.post_id == post.id).order_by(SourceImage.index)
            )
        ).scalars().all()
        try:
            ocr_texts: list[str] = []
            for image in images:
                result = await ocr.recognize(image.file_path)
                image.ocr_text = result.text
                image.ocr_confidence = result.avg_confidence
                ocr_texts.append(result.text)

            post_text = "\n".join(filter(None, [post.title, post.raw_text]))
            questions = await llm.extract_questions(post_text, "\n\n".join(ocr_texts))

            seen: set[str] = set()
            min_confidence = 1.0
            for item in questions:
                key = normalize_question_text(item.content)
                if key in seen:
                    continue
                seen.add(key)
                if item.answer_full:
                    answer, source = item.answer_full, "original"
                else:
                    answer, source = await llm.generate_answer(item.content, item.question_type), "ai"
                main_image = (
                    images[item.source_image_indexes[0]]
                    if item.source_image_indexes and item.source_image_indexes[0] < len(images)
                    else None
                )
                session.add(
                    Question(
                        post_id=post.id,
                        image_id=main_image.id if main_image else None,
                        content=item.content.strip(),
                        question_type=item.question_type,
                        answer_markdown=answer,
                        answer_source=source,
                        company=item.company,
                        direction=item.direction,
                        interview_round=item.interview_round,
                        source_url=post.url,
                        confidence=item.confidence,
                    )
                )
                min_confidence = min(min_confidence, item.confidence)

            task.status = (
                "done_with_warnings" if min_confidence < low_confidence_threshold else "done"
            )
            task.stage_stats = {"ocr_images": len(images), "extracted": len(questions), "saved": len(seen)}
        except Exception as e:  # noqa: BLE001 —— 单任务失败不能拖垮 worker
            task.status = "failed"
            task.error_message = f"{type(e).__name__}: {e}"
            task.retry_count += 1
            logger.exception("任务 %s 处理失败", task_id)
        finally:
            task.finished_at = datetime.now(UTC)
            await session.commit()


async def start_worker_loop(app) -> None:
    """FastAPI lifespan 启动的常驻循环：每 2 秒领取一个任务。"""
    from app.services.llm.deepseek import DeepSeekClient
    from app.services.ocr import PaddleOcrService

    settings = app.state.settings
    ocr = PaddleOcrService()
    llm = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        max_retries=settings.llm_max_retries,
    )
    while True:
        async with app.state.session_factory() as session:
            task = await claim_next_task(session)
        if task is None:
            await asyncio.sleep(2)
            continue
        await run_task(
            task.id,
            session_factory=app.state.session_factory,
            ocr=ocr,
            llm=llm,
            low_confidence_threshold=settings.low_confidence_threshold,
        )
