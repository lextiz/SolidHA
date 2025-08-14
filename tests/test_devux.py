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
