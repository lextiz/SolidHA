"""Utilities for loading incident references from disk."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .types import IncidentRef


def _parse_time(value: str) -> datetime | None:
    """Parse an ISO formatted timestamp to ``datetime``.

    Returns ``None`` if the timestamp is invalid.
    """

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def list_incidents(
    directory: Path | str = Path("/data/incidents"),
) -> list[IncidentRef]:
    """Return ``IncidentRef`` objects for incident files in ``directory``.

    Each incident file is expected to be a JSONL file where each line contains a
    ``time_fired`` field. Malformed lines are ignored. Files without any valid
    timestamps are skipped.
    """

    if isinstance(directory, str):
        directory = Path(directory)
    refs: list[IncidentRef] = []
    for path in sorted(directory.glob("incidents_*.jsonl")):
        start: datetime | None = None
        end: datetime | None = None
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            continue
        for line in lines:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = data.get("time_fired")
            if not isinstance(ts, str):
                continue
            parsed = _parse_time(ts)
            if parsed is None:
                continue
            if start is None or parsed < start:
                start = parsed
            if end is None or parsed > end:
                end = parsed
        if start is not None and end is not None:
            refs.append(IncidentRef(path, start, end))
    return refs


__all__ = ["list_incidents"]
