"""Development UX utilities like a minimal HTTP incident endpoint."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


def list_incidents(directory: Path) -> list[str]:
    """Return sorted incident bundle file names."""
    return sorted(p.name for p in directory.glob("incidents_*.jsonl"))


def list_analyses(directory: Path) -> list[str]:
    """Return sorted analysis bundle file names."""
    return sorted(p.name for p in directory.glob("analyses_*.jsonl"))


def render_index(incidents: list[str], analyses: list[str]) -> bytes:
    """Render a minimal HTML page for incidents and analyses."""
    html = ["<html><head><title>HA LLM Ops</title></head><body>"]
    html.append("<h1>Incidents</h1><ul>")
    for name in incidents:
        html.append(f'<li><a href="/incidents/{name}">{name}</a></li>')
    html.append("</ul><h1>Solutions</h1><ul>")
    for name in analyses:
        incident = name.replace("analyses_", "incidents_")
        html.append(
            f'<li><a href="/analyses/{name}">{name}</a> '
            f'(from <a href="/incidents/{incident}">{incident}</a>)</li>'
        )
    html.append("</ul></body></html>")
    return "".join(html).encode("utf-8")


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
            path = unquote(self.path.rstrip("/"))
            if path == "" or path == "/":
                incidents = list_incidents(incident_dir)
                analyses = list_analyses(analysis_dir) if analysis_dir else []
                body = render_index(incidents, analyses)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif path == "/incidents":
                body = json.dumps(list_incidents(incident_dir)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path.startswith("/incidents/"):
                name = path.split("/", 2)[2]
                file_path = incident_dir / name
                if not file_path.exists():
                    self.send_response(404)
                    self.end_headers()
                    return
                body = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/analyses" and analysis_dir is not None:
                body = json.dumps(list_analyses(analysis_dir)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path.startswith("/analyses/") and analysis_dir is not None:
                name = path.split("/", 2)[2]
                file_path = analysis_dir / name
                if not file_path.exists():
                    self.send_response(404)
                    self.end_headers()
                    return
                body = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                self.send_response(404)
                self.end_headers()
                return
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
