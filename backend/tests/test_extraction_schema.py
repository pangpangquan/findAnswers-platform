import pytest
from pydantic import ValidationError

from app.schemas.extraction import ExtractedQuestion, QuestionExtractionResult


def make_valid(**overrides):
    data = dict(
        content="讲讲 TCP 三次握手的过程",
        question_type="eight_legged",
        source_image_indexes=[0],
        confidence=0.9,
    )
    data.update(overrides)
    return data


def test_valid_question():
    q = ExtractedQuestion(**make_valid())
    assert q.content == "讲讲 TCP 三次握手的过程"


def test_content_too_short_raises():
    with pytest.raises(ValidationError):
        ExtractedQuestion(**make_valid(content="你好"))


def test_invalid_question_type_raises():
    with pytest.raises(ValidationError):
        ExtractedQuestion(**make_valid(question_type="essay"))


def test_confidence_out_of_range_raises():
    with pytest.raises(ValidationError):
        ExtractedQuestion(**make_valid(confidence=1.5))


def test_result_allows_empty_list():
    result = QuestionExtractionResult(questions=[])
    assert result.questions == []
