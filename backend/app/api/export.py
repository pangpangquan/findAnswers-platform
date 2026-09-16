from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Question
from app.schemas.question import QuestionOut
from app.services.exporters.md import build_markdown

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("")
async def export(format: str = "md", db: AsyncSession = Depends(get_db)):
    if format != "md":
        raise HTTPException(400, "目前仅支持 format=md")
    rows = (
        await db.execute(
            select(Question).where(Question.deleted_at.is_(None)).order_by(Question.id)
        )
    ).scalars().all()
    markdown = build_markdown([QuestionOut.model_validate(r) for r in rows])
    return StreamingResponse(
        iter([markdown]),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="mianjing-export.md"'},
    )
