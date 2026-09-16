from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IngestTask


async def claim_next_task(session: AsyncSession) -> IngestTask | None:
    result = await session.execute(
        select(IngestTask)
        .where(IngestTask.status == "pending")
        .order_by(IngestTask.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    task = result.scalar_one_or_none()
    if task is not None:
        task.status = "processing"
        await session.commit()
    return task
