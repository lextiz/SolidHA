"""Build context bundles from incident files."""

from __future__ import annotations

import json
from typing import Any

from .types import ContextBundle, IncidentRef


def build_context(
    incident: IncidentRef,
    *,
    max_lines: int = 50,
) -> ContextBundle:
    """Return a ``ContextBundle`` for ``incident``.

    Reads the incident file, selects the last ``max_lines`` entries and
    deduplicates consecutive duplicate events.
    """
    try:
        lines = incident.path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:  # pragma: no cover - defensive
        lines = []

    events: list[dict[str, Any]] = []
    last_cmp: dict[str, Any] | None = None
    for line in lines[-max_lines:]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        cmp = {k: v for k, v in data.items() if k != "time_fired"}
        if last_cmp != cmp:
            events.append(data)
            last_cmp = cmp
    return ContextBundle(incident=incident, events=events)


__all__ = ["build_context"]
