"""OpenAI Responses API adapter."""

from __future__ import annotations

import os
from typing import Any, cast

import requests

from .base import LLM

_SYSTEM_PROMPT = "Respond with **only** valid JSON per schema below; no prose."
_API_URL = "https://api.openai.com/v1/responses"


class OpenAI(LLM):
    """LLM adapter using OpenAI's responses endpoint."""

    def __init__(
        self, model: str = "gpt-5", *, api_key: str | None = None
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.model = model

    def generate(self, prompt: str, *, timeout: float) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": _SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                },
            ],
            "temperature": 0,
        }
        resp = requests.post(_API_URL, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = cast(dict[str, Any], resp.json())
        text = data.get("output_text")
        if not isinstance(text, str):
            text = cast(str, data["output"][0]["content"][0]["text"])
        return text


__all__ = ["OpenAI"]
