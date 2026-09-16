from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import IngestTask, Question
from app.schemas.question import TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if status:
        conditions.append(IngestTask.status == status)
    total = await db.scalar(select(func.count()).select_from(IngestTask).where(*conditions))
    rows = (
        await db.execute(
            select(IngestTask)
            .where(*conditions)
            .order_by(IngestTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"items": [TaskOut.model_validate(r) for r in rows], "total": total}


@router.get("/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(IngestTask, task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")
    return TaskOut.model_validate(task)


@router.post("/{task_id}/retry")
async def retry_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(IngestTask, task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")
    if task.status != "failed":
        raise HTTPException(409, "只有失败的任务可以重试")
    await db.execute(delete(Question).where(Question.post_id == task.post_id))
    task.status = "pending"
    task.error_message = None
    await db.commit()
    return TaskOut.model_validate(task)
