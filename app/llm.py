"""Groq client for constrained text generation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from groq import Groq

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMCompletion:
    content: str
    model: str


class LLMClient:
    """Thin wrapper around the Groq SDK for chat completions."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.llm_configured:
            raise ValueError("GROQ_API_KEY is not set. Add it to .env (see .env.example).")
        self._client = Groq(
            api_key=self.settings.groq_api_key,
            timeout=float(self.settings.llm_timeout_seconds),
        )

    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        response = self._client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self.settings.llm_max_tokens,
            temperature=self.settings.llm_temperature,
        )
        content = (response.choices[0].message.content or "").strip()
        return LLMCompletion(content=content, model=self.settings.llm_model)

    def complete_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_retries: int = 3,
    ) -> LLMCompletion:
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                return self.complete(system_prompt, user_prompt)
            except Exception as exc:
                last_error = exc
                logger.warning("Groq completion attempt %s failed: %s", attempt + 1, exc)
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
        raise RuntimeError("Groq completion failed after retries") from last_error


def get_llm_client() -> LLMClient:
    return LLMClient()
