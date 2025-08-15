"""Typed structures for analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..contracts import RcaResult

# Public alias for downstream modules.
RcaOutput = RcaResult


@dataclass(slots=True, frozen=True)
class IncidentRef:
    """Reference to an incident file and its time span."""

    path: Path
    start: datetime
    end: datetime


@dataclass(slots=True, frozen=True)
class ContextBundle:
    """Collection of events associated with an incident."""

    incident: IncidentRef
    events: list[dict[str, Any]]


@dataclass(slots=True, frozen=True)
class Prompt:
    """Prompt text and JSON schema to send to an LLM."""

    text: str
    schema: dict[str, Any]


__all__ = ["IncidentRef", "ContextBundle", "Prompt", "RcaOutput"]
