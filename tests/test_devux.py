import time
from pathlib import Path

import requests

from agent.devux import start_http_server


def test_http_lists_incident_files(tmp_path: Path) -> None:
    (tmp_path / "incidents_1.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "incidents_2.jsonl").write_text("{}\n", encoding="utf-8")
    server = start_http_server(tmp_path, host="127.0.0.1", port=0)
    try:
        # Allow server thread to start
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/incidents", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == ["incidents_1.jsonl", "incidents_2.jsonl"]
    finally:
        server.shutdown()


def test_http_root_page(tmp_path: Path) -> None:
    (tmp_path / "incidents_1.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "analyses_1.jsonl").write_text("{}\n", encoding="utf-8")
    server = start_http_server(
        tmp_path, analysis_dir=tmp_path, host="127.0.0.1", port=0
    )
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        assert resp.status_code == 200
        assert "incidents_1.jsonl" in resp.text
        assert "analyses_1.jsonl" in resp.text
    finally:
        server.shutdown()


def test_http_lists_analysis_files(tmp_path: Path) -> None:
    (tmp_path / "analyses_1.jsonl").write_text("{}\n", encoding="utf-8")
    server = start_http_server(
        tmp_path,
        analysis_dir=tmp_path,
        host="127.0.0.1",
        port=0,
    )
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/analyses", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == ["analyses_1.jsonl"]
    finally:
        server.shutdown()


def test_http_analyses_empty(tmp_path: Path) -> None:
    server = start_http_server(
        tmp_path,
        analysis_dir=tmp_path,
        host="127.0.0.1",
        port=0,
    )
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/analyses", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        server.shutdown()


def test_http_analyses_404(tmp_path: Path) -> None:
    server = start_http_server(tmp_path, host="127.0.0.1", port=0)
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/analyses", timeout=5)
        assert resp.status_code == 404
    finally:
        server.shutdown()
