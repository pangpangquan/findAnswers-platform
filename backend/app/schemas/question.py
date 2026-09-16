from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    task_type: str
    status: str
    retry_count: int
    error_message: str | None
    stage_stats: dict | None
    created_at: datetime
    finished_at: datetime | None
