"""Base protocol for LLM adapters."""

from __future__ import annotations

from typing import Protocol


class LLM(Protocol):
    """Interface for large language models."""

    def generate(self, prompt: str, *, timeout: float) -> str:
        """Return a response for ``prompt`` within ``timeout`` seconds."""


__all__ = ["LLM"]
