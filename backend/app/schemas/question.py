from datetime import datetime
from typing import Literal

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


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    image_id: int | None
    content: str
    question_type: str
    answer_markdown: str | None
    answer_source: str
    company: str | None
    direction: str | None
    interview_round: str | None
    source_url: str | None
    crop_image_path: str | None
    confidence: float
    created_at: datetime
    updated_at: datetime


class QuestionUpdate(BaseModel):
    content: str | None = None
    question_type: Literal["eight_legged", "handwritten_code", "scenario", "project"] | None = None
    answer_markdown: str | None = None
    company: str | None = None
    direction: str | None = None
    interview_round: str | None = None
