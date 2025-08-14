"""Build context bundles from incident files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..redact import load_secret_keys, redact
from .types import ContextBundle, IncidentRef


def build_context(
    incident: IncidentRef,
    *,
    max_lines: int = 50,
    secrets_path: Path = Path("/config/secrets.yaml"),
) -> ContextBundle:
    """Return a ``ContextBundle`` for ``incident``.

    Reads the incident file, selects the last ``max_lines`` entries, applies
    redaction, and deduplicates consecutive duplicate events.
    """

    secret_keys = load_secret_keys(secrets_path)
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
        redacted = redact(data, secret_keys)
        cmp = {k: v for k, v in redacted.items() if k != "time_fired"}
        if last_cmp != cmp:
            events.append(redacted)
            last_cmp = cmp
    return ContextBundle(incident=incident, events=events)


__all__ = ["build_context"]
