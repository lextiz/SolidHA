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
