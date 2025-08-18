import asyncio
import json
from pathlib import Path

from agent import problems


def test_problem_logger_rotates(tmp_path: Path) -> None:
    logger = problems.ProblemLogger(tmp_path, max_bytes=20)
    logger.write({"a": 1})
    logger.write({"b": "x" * 50})
    files = list(tmp_path.glob("problems_*.jsonl"))
    assert len(files) == 2


def test_contains_failure_iterable() -> None:
    assert problems._contains_failure([{"success": False}])
    assert not problems._contains_failure([{"success": True}])


def test_load_problems(tmp_path: Path) -> None:
    record = {
        "event": {},
        "occurrence": 2,
        "result": {
            "summary": "s",
            "root_cause": "c",
            "impact": "i",
            "confidence": 0.5,
            "candidate_actions": [],
            "risk": "r",
            "tests": [],
            "recurrence_pattern": "pattern",
        },
    }
    (tmp_path / "problems_0.jsonl").write_text(json.dumps(record) + "\n")
    loaded = problems._load_problems(tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["count"] == 2


def test_event_batcher_groups(tmp_path: Path) -> None:
    calls: list[list[dict]] = []

    async def callback(batch: list[dict]) -> None:
        calls.append(batch)

    batcher = problems.EventBatcher(0.01, callback)

    async def run() -> None:
        batcher.add({"a": 1})
        batcher.add({"b": 2})
        await asyncio.sleep(0.02)
        await batcher.flush()

    asyncio.run(run())
    assert len(calls) == 1 and len(calls[0]) == 2


def test_event_batcher_flush_pending() -> None:
    calls: list[list[dict]] = []

    async def callback(batch: list[dict]) -> None:
        calls.append(batch)

    batcher = problems.EventBatcher(1.0, callback)

    async def run() -> None:
        batcher.add({"a": 1})
        await batcher.flush()

    asyncio.run(run())
    assert calls == [[{"a": 1}]]
