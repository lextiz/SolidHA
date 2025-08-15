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
        self,
        model: str = "gpt-5",
        *,
        api_key: str | None = None,
        project_id: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.project_id = project_id or os.getenv("OPENAI_PROJECT_ID")
        self.model = model

    def generate(self, prompt: str, *, timeout: float) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "responses-v1",
        }
        if self.project_id:
            headers["OpenAI-Project"] = self.project_id
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": _SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            ],
            "temperature": 0,
        }
        resp = requests.post(_API_URL, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = cast(dict[str, Any], resp.json())
        # Prefer the consolidated output_text if present
        text = data.get("output_text")
        if isinstance(text, str):
            return text

        # Fallback to extracting the first message content
        for item in data.get("output", []):
            if item.get("type") == "message":
                contents = item.get("content", [])
                for content in contents:
                    maybe_text = content.get("text")
                    if isinstance(maybe_text, str):
                        return maybe_text
        raise RuntimeError("No text in response")


__all__ = ["OpenAI"]
