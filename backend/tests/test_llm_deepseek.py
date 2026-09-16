import httpx
import pytest

from app.services.llm.deepseek import DeepSeekClient, LLMError

VALID_JSON = (
    '{"questions":[{"content":"讲讲TCP三次握手的过程","question_type":"eight_legged",'
    '"source_image_indexes":[0],"source_text_spans":["三次握手"],"confidence":0.9}]}'
)


def _client(handler) -> DeepSeekClient:
    return DeepSeekClient(api_key="k", transport=httpx.MockTransport(handler))


async def test_extract_success():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": VALID_JSON}}]})

    qs = await _client(handler).extract_questions("帖子", "OCR文本")
    assert qs[0].content == "讲讲TCP三次握手的过程"
    assert qs[0].question_type == "eight_legged"


async def test_extract_retries_on_bad_json_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        content = "不是JSON" if calls["n"] == 1 else VALID_JSON
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    qs = await _client(handler).extract_questions("帖子", "OCR文本")
    assert calls["n"] == 2
    assert len(qs) == 1


async def test_extract_exhausts_retries_and_raises():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "不是JSON"}}]})

    with pytest.raises(LLMError):
        await _client(handler).extract_questions("帖子", "OCR文本")


async def test_generate_answer_returns_plain_text():
    def handler(request):
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "- 要点1\n---\n详解"}}]}
        )

    answer = await _client(handler).generate_answer("讲讲三次握手", "eight_legged")
    assert "---" in answer
