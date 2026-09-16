from typing import Literal

from pydantic import BaseModel, Field, field_validator

QuestionType = Literal["eight_legged", "handwritten_code", "scenario", "project"]


class ExtractedQuestion(BaseModel):
    content: str
    question_type: QuestionType
    answer_full: str | None = None
    follow_ups: list[str] = Field(default_factory=list)
    company: str | None = None
    direction: str | None = None
    interview_round: str | None = None
    source_image_indexes: list[int] = Field(default_factory=list)
    source_text_spans: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)

    @field_validator("content")
    @classmethod
    def content_not_trivial(cls, v: str) -> str:
        if len("".join(v.split())) < 4:
            raise ValueError("题目内容过短（去空白后需 ≥ 4 字符）")
        return v


class QuestionExtractionResult(BaseModel):
    questions: list[ExtractedQuestion] = Field(default_factory=list)
