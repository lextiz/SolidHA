import json
import re
import time
from pathlib import Path

import requests

from agent import devux


def _sample_result() -> dict:
    return {
        "summary": "Problem summary",
        "root_cause": "Root cause",
        "impact": "Impact",
        "confidence": 0.5,
        "candidate_actions": [],
        "risk": "low",
        "tests": [],
        "recurrence_pattern": "foo",
    }


def _record(
    time_str: str,
    occurrence: int,
    result: dict | None = None,
    extra: dict | None = None,
) -> str:
    event: dict[str, object] = {"time": time_str}
    if extra:
        event.update(extra)
    data: dict[str, object] = {"event": event, "occurrence": occurrence}
    if result is not None:
        data["result"] = result
    return json.dumps(data)


def test_list_and_delete(tmp_path: Path) -> None:
    rec1 = _record("2024-01-01T00:00:00Z", 1, _sample_result(), {"msg": "foo"})
    rec2 = _record("2024-01-02T00:00:00Z", 2, extra={"msg": "foo"})
    path = tmp_path / "problems_1.jsonl"
    path.write_text(f"{rec1}\n{rec2}\n", encoding="utf-8")

    problems = devux._load_problems(tmp_path)
    key = next(iter(problems))
    assert problems[key].occurrences == 2

    devux.delete_problem(tmp_path, key)
    assert not path.exists()


def test_http_server(tmp_path: Path) -> None:
    rec1 = _record("2024-01-01T00:00:00Z", 1, _sample_result(), {"msg": "foo"})
    path = tmp_path / "problems_1.jsonl"
    path.write_text(f"{rec1}\n", encoding="utf-8")

    server = devux.start_http_server(tmp_path, port=0)
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        assert "Problem summary" in resp.text
        match = re.search(r"details/(\w+)", resp.text)
        assert match is not None
        key = match.group(1)
        resp = requests.get(f"http://127.0.0.1:{port}/details/{key}", timeout=5)
        assert "Root Cause" in resp.text
        resp = requests.delete(f"http://127.0.0.1:{port}/delete/{key}", timeout=5)
        assert resp.status_code == 200
        assert not path.exists()
    finally:
        server.shutdown()
