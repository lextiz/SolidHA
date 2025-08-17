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
        "candidate_actions": [{"action": "act", "rationale": "why"}],
        "risk": "low",
        "tests": ["check"],
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
    rec2 = json.dumps({"event": "bad", "occurrence": 1})
    rec3 = _record("2024-01-03T00:00:00Z", 1, extra={"msg": "bar"})
    rec4 = _record("2024-01-04T00:00:00Z", 2, extra={"msg": "foo"})
    path = tmp_path / "problems_1.jsonl"
    path.write_text(f"{rec1}\n\n{rec2}\n{rec3}\n{rec4}\n", encoding="utf-8")

    assert devux.list_problems(tmp_path) == ["problems_1.jsonl"]
    problems = devux._load_problems(tmp_path)
    key = next(iter(problems))
    assert problems[key].occurrences == 2
    assert len(problems[key].events) == 2
    assert problems[key].last_seen == "2024-01-04 00:00:00"
    assert devux._event_ts({}) == ""

    devux.delete_problem(tmp_path, "missing")
    devux.delete_problem(tmp_path, key)
    assert path.exists()
    remaining = path.read_text(encoding="utf-8")
    assert rec2 in remaining and rec3 in remaining
    assert rec1 not in remaining and rec4 not in remaining


def test_http_server(tmp_path: Path) -> None:
    rec1 = _record("2024-01-01T00:00:00Z", 1, _sample_result(), {"msg": "foo"})
    path = tmp_path / "problems_1.jsonl"
    path.write_text(f"{rec1}\n", encoding="utf-8")

    server = devux.start_http_server(tmp_path, port=0)
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        resp = requests.get(base + "/", timeout=5)
        assert "Problem summary" in resp.text
        match = re.search(r"details/(\w+)", resp.text)
        assert match is not None
        key = match.group(1)
        resp = requests.get(f"{base}/details/{key}", timeout=5)
        assert "Root Cause" in resp.text and "act" in resp.text
        assert requests.get(f"{base}/details/bad", timeout=5).status_code == 404
        assert requests.get(f"{base}/problems", timeout=5).json() == [path.name]
        resp = requests.get(f"{base}/problems/{path.name}", timeout=5)
        assert resp.status_code == 200
        assert requests.get(f"{base}/problems/nope", timeout=5).status_code == 404
        assert requests.get(f"{base}/unknown", timeout=5).status_code == 404
        assert requests.delete(f"{base}/nope", timeout=5).status_code == 404
        resp = requests.delete(f"{base}/delete/{key}", timeout=5)
        assert resp.status_code == 200
        assert not path.exists()
    finally:
        server.shutdown()
