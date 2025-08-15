"""Development UX utilities like a minimal HTTP incident endpoint."""

from __future__ import annotations

import datetime as dt
import html
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
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.UTC).isoformat()


def render_index(entries: list[tuple[str, str]]) -> bytes:
    """Render a simple HA-style page for incidents with details links."""
    style = (
        "body{margin:0;padding:16px;font-family:'Roboto',sans-serif;"
        "background-color:#f5f5f5;}"
        "\n.card{max-width:800px;margin:0 auto;background:#fff;border-radius:12px;"
        "box-shadow:0 2px 4px rgba(0,0,0,0.2);}" 
        "\n.card h1{margin:0;padding:16px;font-size:20px;border-bottom:1px solid "
        "#e0e0e0;}"
        "\n.list{list-style:none;margin:0;padding:0;}"
        "\n.item{display:flex;align-items:center;justify-content:space-between;"
        "padding:12px 16px;border-bottom:1px solid #e0e0e0;}"
        "\n.item:last-child{border-bottom:none;}"
        "\n.item a{color:#03a9f4;text-decoration:none;}"
        "\n.name{flex:1;}"
        "\n.timestamp{color:#666;font-size:0.9em;margin-right:16px;}"
    )
    html_parts = [
        "<html><head><title>HA LLM Ops</title>",
        "<link rel='preconnect' href='https://fonts.gstatic.com'>",
        (
            "<link href='https://fonts.googleapis.com/css2?family=Roboto:wght@400;"
            "500&display=swap' rel='stylesheet'>"
        ),
        "<style>",
        style,
        "</style>",
        "</head><body>",
        "<div class='card'>",
        "<h1>Incidents</h1>",
        "<ul class='list'>",
    ]
    for name, last in entries:
        html_parts.append(
            f"<li class='item'><span class='name'>{html.escape(name)}</span>"
            f"<span class='timestamp'>{html.escape(last)}</span>"
            f"<a href=\"details/{html.escape(name)}\">View</a></li>"
        )
    html_parts.extend(["</ul></div></body></html>"])
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
    style = (
        "body{margin:0;padding:16px;font-family:'Roboto',sans-serif;"
        "background-color:#f5f5f5;}"
        "\n.card{max-width:800px;margin:0 auto;background:#fff;border-radius:12px;"
        "box-shadow:0 2px 4px rgba(0,0,0,0.2);padding:16px;}"
        "\nh1{margin-top:0;font-size:20px;}"
        "\npre{background:#f0f0f0;padding:8px;border-radius:8px;white-space:pre-wrap;"
        "word-break:break-word;}"
        "\na{color:#03a9f4;text-decoration:none;}"
    )
    parts = [
        "<html><head><title>HA LLM Ops</title>",
        "<link rel='preconnect' href='https://fonts.gstatic.com'>",
        (
            "<link href='https://fonts.googleapis.com/css2?family=Roboto:wght@400;"
            "500&display=swap' rel='stylesheet'>"
        ),
        "<style>",
        style,
        "</style>",
        "</head><body>",
        "<div class='card'>",
        f"<h1>{html.escape(name)}</h1>",
        "<h2>Incident</h2>",
        f"<pre>{html.escape(incident_data)}</pre>",
        "<h2>Analysis</h2>",
        f"<pre>{html.escape(analysis_text)}</pre>",
        '<p><a href="../">Back</a></p>',
        "</div></body></html>",
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
