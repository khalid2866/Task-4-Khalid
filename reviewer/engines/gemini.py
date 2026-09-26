"""Gemini engine — Google GenAI API client.

The Persona Constraints are defined at client initialisation via the
``system_instruction`` parameter, hardcoding the behavioural rules into
the execution environment (The LLM Taming Matrix).
"""

from __future__ import annotations

import os
import time

from ..exceptions import EngineError

_MODEL = "gemini-2.5-flash"
_TIMEOUT_S = 60


class GeminiEngine:
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str = _MODEL) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise EngineError(
                "GEMINI_API_KEY is not set. Add it to your .env file "
                "or use --engine demo for the offline engine."
            )
        self.model = model

    def generate(self, system: str, user: str, ctx=None) -> str:  # noqa: ANN001, ARG002
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise EngineError(
                "The 'google-genai' package is not installed. "
                "Run: pip install google-genai"
            ) from exc

        client = genai.Client(
            api_key=self.api_key,
            http_options={"timeout": _TIMEOUT_S * 1000},
        )
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=0.2,
                        max_output_tokens=4096,
                    ),
                )
                text = (resp.text or "").strip()
                if not text:
                    raise EngineError("Gemini returned an empty response.")
                return text
            except EngineError:
                raise
            except Exception as exc:  # noqa: BLE001 - retry transient API faults
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise EngineError(f"Gemini request failed after 3 attempts: {last_error}")
