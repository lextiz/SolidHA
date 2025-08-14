import json
from datetime import datetime
from pathlib import Path

from agent.analysis.context import build_context
from agent.analysis.types import IncidentRef


def _evt(event_type: str, **data: object) -> str:
    return json.dumps({"event_type": event_type, **data})


def test_build_context_redaction_and_dedupe(tmp_path: Path) -> None:
    file = tmp_path / "incidents.jsonl"
    lines = [
        _evt("log", time_fired="2024-01-01T00:00:00+00:00", api_key="secret"),
        _evt("log", time_fired="2024-01-01T00:00:01+00:00", api_key="secret"),
        _evt("state", time_fired="2024-01-01T00:00:02+00:00"),
    ]
    file.write_text("\n".join(lines), encoding="utf-8")
    secrets = tmp_path / "secrets.yaml"
    secrets.write_text("api_key: secret\n")

    ref = IncidentRef(file, datetime(2024, 1, 1), datetime(2024, 1, 1, 0, 0, 2))
    bundle = build_context(ref, max_lines=10, secrets_path=secrets)

    assert len(bundle.events) == 2  # duplicate removed
    assert bundle.events[0]["api_key"] == "[redacted]"


def test_build_context_respects_limit(tmp_path: Path) -> None:
    file = tmp_path / "incidents.jsonl"
    lines = [
        _evt("a", time_fired="2024-01-01T00:00:00+00:00"),
        _evt("b", time_fired="2024-01-01T00:00:01+00:00"),
        _evt("c", time_fired="2024-01-01T00:00:02+00:00"),
    ]
    file.write_text("\n".join(lines), encoding="utf-8")
    ref = IncidentRef(file, datetime(2024, 1, 1), datetime(2024, 1, 1, 0, 0, 2))

    bundle = build_context(ref, max_lines=2)
    assert [e["event_type"] for e in bundle.events] == ["b", "c"]
