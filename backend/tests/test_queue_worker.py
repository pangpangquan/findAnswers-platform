from sqlalchemy import select

from app.models import IngestTask, Question, SourceImage, SourcePost
from app.schemas.extraction import ExtractedQuestion
from app.services.ocr import DummyOcrService, OcrResult
from app.services.queue import claim_next_task
from app.services.worker import run_task


def make_ocr(text_="1. 讲讲 TCP 三次握手\n2. 介绍一下 Redis 持久化机制"):
    return DummyOcrService(OcrResult(text=text_, avg_confidence=0.95, lines=[]))


class FakeLlm:
    def __init__(self, questions=None, fail=False):
        self.questions = questions or []
        self.fail = fail
        self.answered = []

    async def extract_questions(self, post_text, ocr_text):
        if self.fail:
            raise RuntimeError("LLM 挂了")
        return self.questions

    async def generate_answer(self, content, question_type):
        self.answered.append(content)
        return "- 口述要点\n---\n详细解释"


def q(content, conf=0.9, answer_full=None):
    return ExtractedQuestion(
        content=content,
        question_type="eight_legged",
        source_image_indexes=[0],
        source_text_spans=["x"],
        confidence=conf,
        answer_full=answer_full,
    )


async def seed(app, n_images=1):
    async with app.state.session_factory() as session:
        post = SourcePost(platform="manual", title="测试面经")
        session.add(post)
        await session.flush()
        for i in range(n_images):
            session.add(SourceImage(post_id=post.id, index=i, file_path=f"/tmp/{i}.png"))
        task = IngestTask(post_id=post.id, task_type="manual_images")
        session.add(task)
        await session.commit()
        return task.id, post.id


async def test_claim_marks_processing(app):
    task_id, _ = await seed(app)
    async with app.state.session_factory() as session:
        task = await claim_next_task(session)
        assert task.id == task_id
        assert task.status == "processing"


async def test_run_task_saves_deduped_questions(app):
    task_id, post_id = await seed(app)
    llm = FakeLlm(
        questions=[
            q("讲讲 TCP 三次握手的过程", answer_full="RDB 快照"),
            q("讲讲tcp三次握手的过程"),  # 归一化后重复，应被丢弃
            q("介绍一下 Redis 持久化机制"),
        ]
    )
    await run_task(task_id, session_factory=app.state.session_factory, ocr=make_ocr(), llm=llm)

    async with app.state.session_factory() as session:
        rows = (await session.execute(select(Question).order_by(Question.id))).scalars().all()
        assert len(rows) == 2  # 3 抽 2，重复题被合并
        tcp = next(r for r in rows if "三次握手" in r.content)
        redis = next(r for r in rows if "Redis" in r.content)
        assert tcp.answer_source == "original"  # 原帖答案
        assert redis.answer_source == "ai"  # LLM 生成
        assert llm.answered == ["介绍一下 Redis 持久化机制"]
        task = await session.get(IngestTask, task_id)
        assert task.status == "done"
        assert task.stage_stats == {"ocr_images": 1, "extracted": 3, "saved": 2}


async def test_run_task_low_confidence_marks_warning(app):
    task_id, _ = await seed(app)
    llm = FakeLlm(questions=[q("讲讲 操作系统 进程与线程的区别", conf=0.4)])
    await run_task(task_id, session_factory=app.state.session_factory, ocr=make_ocr(), llm=llm)
    async with app.state.session_factory() as session:
        task = await session.get(IngestTask, task_id)
        assert task.status == "done_with_warnings"


async def test_run_task_failure_marks_failed(app):
    task_id, _ = await seed(app)
    llm = FakeLlm(fail=True)
    await run_task(task_id, session_factory=app.state.session_factory, ocr=make_ocr(), llm=llm)
    async with app.state.session_factory() as session:
        task = await session.get(IngestTask, task_id)
        assert task.status == "failed"
        assert "LLM 挂了" in task.error_message
        assert task.retry_count == 1
