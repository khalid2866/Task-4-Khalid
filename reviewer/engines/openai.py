"""OpenAI engine — alternative LLM backend for the review pipeline."""

from __future__ import annotations

import os
import time

from ..exceptions import EngineError

_MODEL = "gpt-4o-mini"


class OpenAIEngine:
    name = "openai"

    def __init__(self, api_key: str | None = None, model: str = _MODEL) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise EngineError(
                "OPENAI_API_KEY is not set. Add it to your .env file "
                "or use --engine demo for the offline engine."
            )
        self.model = model

    def generate(self, system: str, user: str, ctx=None) -> str:  # noqa: ANN001, ARG002
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EngineError(
                "The 'openai' package is not installed. Run: pip install openai"
            ) from exc

        client = OpenAI(api_key=self.api_key, timeout=60.0)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.2,
                    max_tokens=4096,
                )
                text = (resp.choices[0].message.content or "").strip()
                if not text:
                    raise EngineError("OpenAI returned an empty response.")
                return text
            except EngineError:
                raise
            except Exception as exc:  # noqa: BLE001 - retry transient API faults
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise EngineError(f"OpenAI request failed after 3 attempts: {last_error}")
