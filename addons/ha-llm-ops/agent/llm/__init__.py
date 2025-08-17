"""LLM adapter implementations and factory."""

from __future__ import annotations

import os

from .base import LLM
from .mock import MockLLM
from .openai import OpenAI


def create_llm(backend: str | None = None) -> LLM:
    """Return an ``LLM`` instance based on ``backend`` or environment."""

    if backend is None:
        backend = "OPENAI" if os.getenv("OPENAI_API_KEY") else "MOCK"
    backend = backend.upper()
    if backend == "OPENAI":
        return OpenAI()
    return MockLLM()


__all__ = ["LLM", "MockLLM", "OpenAI", "create_llm"]
