import time
from pathlib import Path

import requests

from agent import devux


def test_list_and_delete(tmp_path: Path) -> None:
    (tmp_path / "problems_1.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "problems_2.jsonl").write_text("{}\n", encoding="utf-8")
    assert devux.list_problems(tmp_path) == ["problems_1.jsonl", "problems_2.jsonl"]
    devux.delete_problem(tmp_path, "problems_1.jsonl")
    assert devux.list_problems(tmp_path) == ["problems_2.jsonl"]


def test_http_server(tmp_path: Path) -> None:
    (tmp_path / "problems_1.jsonl").write_text("{\"a\":1}\n", encoding="utf-8")
    server = devux.start_http_server(tmp_path, port=0)
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        assert "problems_1.jsonl" in resp.text
        resp = requests.get(
            f"http://127.0.0.1:{port}/problems/problems_1.jsonl", timeout=5
        )
        assert resp.json() == {"a": 1}
        resp = requests.get(
            f"http://127.0.0.1:{port}/details/problems_1.jsonl", timeout=5
        )
        assert "a" in resp.text
        resp = requests.get(f"http://127.0.0.1:{port}/unknown", timeout=5)
        assert resp.status_code == 404
        resp = requests.get(
            f"http://127.0.0.1:{port}/problems/missing.jsonl", timeout=5
        )
        assert resp.status_code == 404
        resp = requests.delete(
            f"http://127.0.0.1:{port}/delete/problems_1.jsonl", timeout=5
        )
        assert resp.status_code == 200
        assert not (tmp_path / "problems_1.jsonl").exists()
        resp = requests.delete(f"http://127.0.0.1:{port}/oops", timeout=5)
        assert resp.status_code == 404
    finally:
        server.shutdown()
