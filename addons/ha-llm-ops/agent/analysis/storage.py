"""Utilities for loading incident references from disk."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .types import IncidentRef

LOGGER = logging.getLogger(__name__)


def _extract_title(event: dict[str, Any]) -> str | None:
    """Return a human-readable title for ``event`` if possible."""

    etype = event.get("event_type")
    data = event.get("data", {})
    if not isinstance(data, dict):
        data = {}
    if etype == "system_log_event":
        message = data.get("message")
        if isinstance(message, str):
            return message
    elif etype == "trace":
        error = data.get("error")
        if isinstance(error, str):
            return error
        result = data.get("result")
        if isinstance(result, dict):
            err = result.get("error")
            if isinstance(err, str):
                return err
    elif etype == "state_changed":
        entity = data.get("entity_id")
        new_state = data.get("new_state")
        state = new_state.get("state") if isinstance(new_state, dict) else None
        if isinstance(entity, str) and isinstance(state, str):
            return f"{entity} became {state}"
        if isinstance(entity, str):
            return entity
    if isinstance(etype, str):
        return etype
    return None


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
        title: str | None = None
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            continue
        for line in lines:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if title is None:
                title = _extract_title(data)
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
            LOGGER.debug(
                "incident %s: start=%s end=%s title=%s", path, start, end, title
            )
            refs.append(IncidentRef(path, start, end, title))
    LOGGER.debug("listed %d incident(s) in %s", len(refs), directory)
    return refs


__all__ = ["list_incidents"]
