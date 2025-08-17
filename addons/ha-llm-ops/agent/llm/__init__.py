"""LLM adapter implementations and factory."""

from __future__ import annotations

import os

from .base import LLM
from .mock import MockLLM
from .openai import OpenAI


def create_llm() -> LLM:
    """Return an ``LLM`` instance based on environment."""

    if os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY"):
        return OpenAI()
    return MockLLM()


__all__ = ["LLM", "MockLLM", "OpenAI", "create_llm"]
