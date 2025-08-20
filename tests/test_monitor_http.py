"""Tests for monitoring logs via the Supervisor API."""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar

from agent.llm.mock import MockLLM
from agent.problems import monitor


class LogHandler(BaseHTTPRequestHandler):
    auth: ClassVar[str | None] = None

    def do_GET(self) -> None:  # noqa: D401
        type(self).auth = self.headers.get("Authorization")
        self.send_response(200)
        self.end_headers()
        for line in ["INFO start\n", "ERROR boom\n"]:
            self.wfile.write(line.encode())
            self.wfile.flush()

    def log_message(self, format: str, *args: object) -> None:  # pragma: no cover
        return


def test_monitor_streams_logs(tmp_path: Path) -> None:
    server = HTTPServer(("localhost", 0), LogHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://localhost:{server.server_port}"

    async def run() -> None:
        await monitor(
            url,
            token="t",
            problem_dir=tmp_path,
            llm=MockLLM(),
            limit=None,
            batch_seconds=0,
        )

    asyncio.run(run())
    server.shutdown()

    assert LogHandler.auth == "Bearer t"
    files = sorted(tmp_path.glob("problems_*.jsonl"))
    assert files
    lines = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert any("boom" in json.dumps(entry) for entry in lines)
