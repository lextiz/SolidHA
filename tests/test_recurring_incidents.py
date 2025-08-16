import json
import logging
from pathlib import Path

import pytest

from agent.analysis.llm.mock import MockLLM
from agent.analysis.runner import AnalysisRunner


def _incident(path: Path, ts: str, msg: str) -> None:
    data = {"time_fired": ts, "message": msg}
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def test_runner_deduplicates_recurring(tmp_path: Path) -> None:
    inc_dir = tmp_path / "inc"
    out_dir = tmp_path / "out"
    inc_dir.mkdir()
    out_dir.mkdir()

    _incident(inc_dir / "incidents_1.jsonl", "2024-01-01T00:00:00+00:00", "mock error")

    runner = AnalysisRunner(
        inc_dir,
        out_dir,
        MockLLM(),
        rate_seconds=0,
        max_lines=5,
        max_bytes=1000,
    )
    runner.run_once()

    patterns = json.loads((out_dir / "recurring.json").read_text())
    assert patterns[0]["occurrences"] == 1

    _incident(
        inc_dir / "incidents_2.jsonl",
        "2024-01-02T00:00:00+00:00",
        "mock error again",
    )
    runner.run_once()

    patterns = json.loads((out_dir / "recurring.json").read_text())
    assert patterns[0]["occurrences"] == 2
    assert patterns[0]["last_occurred"].startswith("2024-01-02")

    files = sorted(out_dir.glob("analyses_*.jsonl"))
    lines = files[0].read_text().splitlines()
    assert len(lines) == 1


def test_runner_logs_new_and_known_incidents(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    inc_dir = tmp_path / "inc"
    out_dir = tmp_path / "out"
    inc_dir.mkdir()
    out_dir.mkdir()

    _incident(inc_dir / "incidents_1.jsonl", "2024-01-01T00:00:00+00:00", "mock error")

    runner = AnalysisRunner(
        inc_dir,
        out_dir,
        MockLLM(),
        rate_seconds=0,
        max_lines=5,
        max_bytes=1000,
    )

    with caplog.at_level(logging.INFO):
        runner.run_once()
    assert "new incident analyzed" in caplog.text

    _incident(
        inc_dir / "incidents_2.jsonl",
        "2024-01-02T00:00:00+00:00",
        "mock error again",
    )

    caplog.clear()
    with caplog.at_level(logging.INFO):
        runner.run_once()
    assert "known incident occurred again" in caplog.text
