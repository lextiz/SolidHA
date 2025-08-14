import json
from pathlib import Path

from agent.analysis.storage import list_incidents


def _line(ts: str) -> str:
    return json.dumps({"time_fired": ts})


def test_list_incidents_empty(tmp_path: Path) -> None:
    assert list_incidents(tmp_path) == []


def test_list_incidents_multiple(tmp_path: Path) -> None:
    f1 = tmp_path / "incidents_a.jsonl"
    f1.write_text(
        "\n".join(
            [
                _line("2024-01-01T00:00:00+00:00"),
                _line("2024-01-01T01:00:00+00:00"),
            ]
        ),
        encoding="utf-8",
    )
    f2 = tmp_path / "incidents_b.jsonl"
    f2.write_text(
        "\n".join(
            [
                _line("2024-01-02T00:00:00+00:00"),
                "not json",
                _line("2024-01-02T01:00:00+00:00"),
            ]
        ),
        encoding="utf-8",
    )

    refs = list_incidents(tmp_path)
    assert len(refs) == 2
    names = [r.path.name for r in refs]
    assert "incidents_a.jsonl" in names and "incidents_b.jsonl" in names
    r1 = next(r for r in refs if r.path.name == "incidents_a.jsonl")
    assert r1.start < r1.end


def test_list_incidents_malformed_lines(tmp_path: Path) -> None:
    bad = tmp_path / "incidents_bad.jsonl"
    bad.write_text('{not json}\n{"time_fired": "not-a-date"}\n', encoding="utf-8")
    assert list_incidents(tmp_path) == []
