from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Question
from app.schemas.question import QuestionOut, QuestionUpdate

router = APIRouter(prefix="/api/questions", tags=["questions"])


@router.get("")
async def list_questions(
    company: str | None = None,
    direction: str | None = None,
    question_type: str | None = None,
    answer_source: str | None = None,
    q: str | None = None,
    min_confidence: float | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    conditions = [Question.deleted_at.is_(None)]
    if company:
        conditions.append(Question.company == company)
    if direction:
        conditions.append(Question.direction == direction)
    if question_type:
        conditions.append(Question.question_type == question_type)
    if answer_source:
        conditions.append(Question.answer_source == answer_source)
    if q:
        conditions.append(Question.content.ilike(f"%{q}%"))
    if min_confidence is not None:
        conditions.append(Question.confidence >= min_confidence)

    total = await db.scalar(select(func.count()).select_from(Question).where(*conditions))
    rows = (
        await db.execute(
            select(Question)
            .where(*conditions)
            .order_by(Question.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"items": [QuestionOut.model_validate(r) for r in rows], "total": total}


@router.get("/{question_id}")
async def get_question(question_id: int, db: AsyncSession = Depends(get_db)):
    question = await db.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise HTTPException(404, "题目不存在")
    return QuestionOut.model_validate(question)


@router.patch("/{question_id}")
async def update_question(
    question_id: int, payload: QuestionUpdate, db: AsyncSession = Depends(get_db)
):
    question = await db.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise HTTPException(404, "题目不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    await db.commit()
    await db.refresh(question)
    return QuestionOut.model_validate(question)


@router.delete("/{question_id}", status_code=204)
async def delete_question(question_id: int, db: AsyncSession = Depends(get_db)):
    question = await db.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise HTTPException(404, "题目不存在")
    question.deleted_at = datetime.now(UTC)
    await db.commit()
