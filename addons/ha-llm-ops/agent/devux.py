"""Development UX utilities like a minimal HTTP incident endpoint."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def list_incidents(directory: Path) -> list[str]:
    """Return sorted incident bundle file names."""
    return sorted(p.name for p in directory.glob("incidents_*.jsonl"))


def list_analyses(directory: Path) -> list[str]:
    """Return sorted analysis bundle file names."""
    return sorted(p.name for p in directory.glob("analyses_*.jsonl"))


def start_http_server(
    incident_dir: Path,
    *,
    analysis_dir: Path | None = None,
    host: str = "0.0.0.0",
    port: int = 8000,
) -> ThreadingHTTPServer:
    """Start a thread-based HTTP server exposing incident and analysis bundles.

    The server provides ``/incidents`` and ``/analyses`` endpoints returning JSON
    lists of bundles found in ``incident_dir`` and ``analysis_dir`` respectively.
    It runs in a background thread and returns the server instance for optional
    shutdown.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: D401 - HTTP handler
            path = self.path.rstrip("/")
            if path == "/incidents":
                bundles = list_incidents(incident_dir)
            elif path == "/analyses" and analysis_dir is not None:
                bundles = list_analyses(analysis_dir)
            else:
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(bundles).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(
            self, format: str, *args: object
        ) -> None:  # pragma: no cover - noise
            return

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
