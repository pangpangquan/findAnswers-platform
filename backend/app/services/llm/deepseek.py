import json

import httpx
from pydantic import ValidationError

from app.schemas.extraction import ExtractedQuestion, QuestionExtractionResult
from app.services.llm.prompts import (
    ANSWER_SYSTEM,
    ANSWER_USER_TEMPLATE,
    EXTRACT_SYSTEM,
    EXTRACT_USER_TEMPLATE,
    QUESTION_TYPE_LABELS,
)


class LLMError(Exception):
    pass


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        max_retries: int = 3,
        transport: httpx.AsyncHTTPTransport | None = None,
    ):
        self.model = model
        self.max_retries = max_retries
        kwargs = {
            "base_url": base_url,
            "headers": {"Authorization": f"Bearer {api_key}"},
            "timeout": httpx.Timeout(120.0),
        }
        if transport is not None:
            kwargs["transport"] = transport
        self._http = httpx.AsyncClient(**kwargs)

    async def _chat(self, system: str, user: str, json_mode: bool) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        resp = await self._http.post("/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def extract_questions(self, post_text: str, ocr_text: str) -> list[ExtractedQuestion]:
        user = EXTRACT_USER_TEMPLATE.format(post_text=post_text, ocr_text=ocr_text)
        feedback = ""
        for _ in range(self.max_retries):
            retry_note = (
                f"\n\n上次输出错误：{feedback}，请修正后重新只输出 JSON。" if feedback else ""
            )
            content = await self._chat(EXTRACT_SYSTEM, user + retry_note, json_mode=True)
            try:
                result = QuestionExtractionResult.model_validate(json.loads(content))
                return result.questions
            except (json.JSONDecodeError, ValidationError) as e:
                feedback = str(e)[:500]
        raise LLMError(f"抽题 JSON 解析/校验连续失败 {self.max_retries} 次：{feedback}")

    async def generate_answer(self, content: str, question_type: str) -> str:
        label = QUESTION_TYPE_LABELS.get(question_type, question_type)
        return await self._chat(
            ANSWER_SYSTEM,
            ANSWER_USER_TEMPLATE.format(content=content, qtype=label),
            json_mode=False,
        )
