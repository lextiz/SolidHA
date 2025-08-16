import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agent.analysis.llm.mock import MockLLM
from agent.analysis.llm.openai import OpenAI
from agent.analysis.runner import AnalysisRunner, create_llm
from agent.analysis.types import IncidentRef


def _incident(path: Path, ts: str) -> None:
    path.write_text(f'{{"time_fired":"{ts}"}}\n', encoding="utf-8")


def test_runner_processes_new_incidents(tmp_path: Path) -> None:
    inc_dir = tmp_path / "inc"
    out_dir = tmp_path / "out"
    inc_dir.mkdir()
    out_dir.mkdir()

    _incident(inc_dir / "incidents_1.jsonl", "2024-01-01T00:00:00+00:00")

    runner = AnalysisRunner(
        inc_dir,
        out_dir,
        MockLLM(),
        rate_seconds=0,
        max_lines=5,
        max_bytes=1000,
    )
    runner.run_once()

    files = sorted(out_dir.glob("analyses_*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text().splitlines()
    assert len(lines) == 1

    _incident(inc_dir / "incidents_2.jsonl", "2024-01-01T00:00:01+00:00")
    runner.run_once()
    lines = files[0].read_text().splitlines()
    assert len(lines) == 2
    data = [json.loads(line)["incident"] for line in lines]
    assert data == [
        str(inc_dir / "incidents_1.jsonl"),
        str(inc_dir / "incidents_2.jsonl"),
    ]


def test_runner_rate_limit(tmp_path: Path) -> None:
    inc_dir = tmp_path / "inc"
    out_dir = tmp_path / "out"
    inc_dir.mkdir()
    out_dir.mkdir()

    _incident(inc_dir / "incidents_1.jsonl", "2024-01-01T00:00:00+00:00")

    current = 0.0

    def now() -> float:
        return current

    llm = MockLLM()
    count = {"c": 0}
    orig = llm.generate

    def gen(prompt: str, *, timeout: float) -> str:
        count["c"] += 1
        return orig(prompt, timeout=timeout)

    llm.generate = gen  # type: ignore[assignment]

    runner = AnalysisRunner(
        inc_dir,
        out_dir,
        llm,
        rate_seconds=10,
        max_lines=5,
        max_bytes=1000,
        now_fn=now,
    )

    runner.run_once()
    assert count["c"] == 1

    _incident(inc_dir / "incidents_2.jsonl", "2024-01-01T00:00:01+00:00")
    runner.run_once()
    assert count["c"] == 1  # skipped due to rate limit

    current = 11
    runner.run_once()
    assert count["c"] == 2


def test_runner_rotation(tmp_path: Path) -> None:
    inc_dir = tmp_path / "inc"
    out_dir = tmp_path / "out"
    inc_dir.mkdir()
    out_dir.mkdir()

    runner = AnalysisRunner(
        inc_dir,
        out_dir,
        MockLLM(),
        rate_seconds=0,
        max_lines=5,
        max_bytes=80,
    )

    for i in range(5):
        _incident(inc_dir / f"incidents_{i}.jsonl", f"2024-01-01T00:00:0{i}+00:00")
        runner.run_once()

    files = sorted(out_dir.glob("analyses_*.jsonl"))
    assert len(files) >= 2
    total = sum(len(f.read_text().splitlines()) for f in files)
    assert total == 5

def test_create_llm_backend_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(create_llm(), MockLLM)
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    assert isinstance(create_llm(), OpenAI)
    assert isinstance(create_llm("mock"), MockLLM)


def test_run_forever_cancel(tmp_path: Path) -> None:
    inc_dir = tmp_path / "inc"
    out_dir = tmp_path / "out"
    inc_dir.mkdir()
    out_dir.mkdir()

    runner = AnalysisRunner(
        inc_dir,
        out_dir,
        MockLLM(),
        rate_seconds=0,
        max_lines=5,
        max_bytes=1000,
    )

    async def run_and_cancel() -> None:
        task = asyncio.create_task(runner.run_forever())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run_and_cancel())


def test_runner_retries_failed_analysis(tmp_path: Path) -> None:
    inc_dir = tmp_path / "inc"
    out_dir = tmp_path / "out"
    inc_dir.mkdir()
    out_dir.mkdir()

    _incident(inc_dir / "incidents_1.jsonl", "2024-01-01T00:00:00+00:00")

    class FailLLM:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, prompt: str, *, timeout: float) -> str:  # noqa: D401
            """Raise to simulate LLM failure."""
            self.calls += 1
            raise RuntimeError("boom")

    current = 0.0

    def now() -> float:
        return current

    llm = FailLLM()
    runner = AnalysisRunner(
        inc_dir,
        out_dir,
        llm,  # type: ignore[arg-type]
        rate_seconds=0,
        max_lines=5,
        max_bytes=1000,
        now_fn=now,
    )

    for _ in range(5):
        runner.run_once()
        current = runner._next_run

    runner.run_once()
    current = runner._next_run
    runner.run_once()
    assert llm.calls == 5
    assert (inc_dir / "incidents_1.jsonl") in runner._processed


def test_runner_logs_no_events(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "incidents_1.jsonl"
    path.write_text("", encoding="utf-8")

    runner = AnalysisRunner(
        tmp_path,
        tmp_path,
        MockLLM(),
        rate_seconds=0,
        max_lines=5,
        max_bytes=1000,
    )

    inc = IncidentRef(path, datetime.now(UTC), datetime.now(UTC))

    with caplog.at_level(logging.INFO):
        runner._analyze(inc)  # noqa: SLF001
    assert (
        "no events selected for analysis because none were filtered out"
        in caplog.text
    )
