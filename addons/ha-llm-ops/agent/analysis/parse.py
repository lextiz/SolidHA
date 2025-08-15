"""Parsing utilities for LLM responses."""

from __future__ import annotations

import json

from pydantic import ValidationError

from .types import RcaOutput


class ParseError(ValueError):
    """Raised when an LLM response cannot be parsed."""


def parse_result(text: str) -> RcaOutput:
    """Parse ``text`` into an ``RcaOutput`` instance."""

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ParseError("LLM response is not valid JSON") from exc
    try:
        return RcaOutput.model_validate(data)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise ParseError("LLM response does not match schema") from exc


__all__ = ["ParseError", "parse_result"]
