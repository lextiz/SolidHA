"""Deterministic mock LLM for tests."""

from __future__ import annotations

import json

from .base import LLM

_RESPONSE = {
    "root_cause": "mock root cause",
    "impact": "mock impact",
    "confidence": 0.42,
    "candidate_actions": [
        {"action": "mock action", "rationale": "because tests"}
    ],
    "risk": "low",
    "tests": ["test check"],
}


class MockLLM(LLM):
    """LLM returning a canned response regardless of input."""

    def generate(self, prompt: str, *, timeout: float) -> str:  # noqa: D401
        """Return canned ``RcaResult`` JSON ignoring ``prompt`` and ``timeout``."""

        return json.dumps(_RESPONSE)


__all__ = ["MockLLM"]
