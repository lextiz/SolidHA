"""Development UX utilities like a minimal HTTP incident endpoint."""

from __future__ import annotations

import html
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


def list_incidents(directory: Path) -> list[str]:
    """Return sorted incident bundle file names."""
    return sorted(p.name for p in directory.glob("incidents_*.jsonl"))


def list_analyses(directory: Path) -> list[str]:
    """Return sorted analysis bundle file names."""
    return sorted(p.name for p in directory.glob("analyses_*.jsonl"))


def _last_occurrence(path: Path) -> str:
    """Best effort extraction of the last occurrence timestamp for ``path``."""
    try:
        last = ""
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last = line
        if last:
            record = json.loads(last)
            for key in ("time_fired", "timestamp", "time"):
                if key in record:
                    return str(record[key])
    except Exception:  # pragma: no cover - defensive
        pass
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def render_index(entries: list[tuple[str, str]]) -> bytes:
    """Render a minimal HTML page for incidents with details links."""
    html_parts = [
        "<html><head><title>HA LLM Ops</title>",
        "<style>table{border-collapse:collapse;}th,td{padding:4px;border:1px solid #ccc;}"
        "body{font-family:sans-serif;}</style>",
        "</head><body>",
        "<h1>Incidents</h1>",
        "<table>",
        "<tr><th>Incident</th><th>Last Occurrence</th><th>Details</th></tr>",
    ]
    for name, last in entries:
        html_parts.append(
            f"<tr><td>{html.escape(name)}</td><td>{html.escape(last)}</td>"
            f'<td><a href="details/{html.escape(name)}">View</a></td></tr>'
        )
    html_parts.append("</table></body></html>")
    return "".join(html_parts).encode("utf-8")


def render_details(
    name: str, incident_path: Path, analysis_dir: Path | None
) -> bytes:
    """Render an incident details page including its analysis if available."""
    incident_data = incident_path.read_text(encoding="utf-8")
    analysis_text = "No analysis available."
    if analysis_dir is not None:
        analysis_path = analysis_dir / name.replace("incidents_", "analyses_")
        if analysis_path.exists():
            analysis_text = analysis_path.read_text(encoding="utf-8")
    parts = [
        "<html><head><title>HA LLM Ops</title></head><body>",
        f"<h1>{html.escape(name)}</h1>",
        "<h2>Incident</h2>",
        f"<pre>{html.escape(incident_data)}</pre>",
        "<h2>Analysis</h2>",
        f"<pre>{html.escape(analysis_text)}</pre>",
        '<p><a href="../">Back</a></p>',
        "</body></html>",
    ]
    return "".join(parts).encode("utf-8")


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
                incidents = []
                for name in list_incidents(incident_dir):
                    inc_path = incident_dir / name
                    incidents.append((name, _last_occurrence(inc_path)))
                body = render_index(incidents)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif path.startswith("/details/"):
                name = path.split("/", 2)[2]
                file_path = incident_dir / name
                if not file_path.exists():
                    self.send_response(404)
                    self.end_headers()
                    return
                body = render_details(name, file_path, analysis_dir)
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
