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


def _format_ts(value: str) -> str:
    """Return ``value`` formatted as ``YYYY-MM-DD HH:MM:SS`` if possible."""
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:  # pragma: no cover - best effort
        return value
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


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
                    return _format_ts(str(record[key]))
    except Exception:  # pragma: no cover - defensive
        pass
    return _format_ts(dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.UTC).isoformat())


def _load_analyses(directory: Path) -> dict[str, dict[str, object]]:
    """Return mapping of incident file name to latest analysis result."""
    mapping: dict[str, dict[str, object]] = {}
    for path in sorted(directory.glob("analyses_*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:  # pragma: no cover - defensive
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:  # pragma: no cover - defensive
                continue
            inc = record.get("incident")
            result = record.get("result")
            if isinstance(inc, str) and isinstance(result, dict):
                mapping[Path(inc).name] = result
    return mapping


def render_index(entries: list[tuple[str, str, str]]) -> bytes:
    """Render a simple HA-style page for incidents with details links."""
    style = (
        "body{margin:0;padding:16px;font-family:'Roboto',sans-serif;"
        "background-color:#121212;color:#e0e0e0;}"
        "\n.card{max-width:800px;margin:0 auto;background:#1e1e1e;border-radius:12px;"
        "box-shadow:0 2px 4px rgba(0,0,0,0.6);}"
        "\n.card h1{margin:0;padding:16px;font-size:20px;border-bottom:1px solid #333;}"
        "\n.list{list-style:none;margin:0;padding:0;}"
        "\n.item{display:flex;align-items:center;justify-content:space-between;"
        "padding:12px 16px;border-bottom:1px solid #333;}"
        "\n.item:last-child{border-bottom:none;}"
        "\n.item a{color:#03a9f4;text-decoration:none;}"
        "\n.name{flex:1;}"
        "\n.timestamp{color:#bbb;font-size:0.9em;margin-right:16px;}"
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
    for desc, last, name in entries:
        html_parts.append(
            f"<li class='item'><span class='name'>{html.escape(desc)}</span>"
            f"<span class='timestamp'>{html.escape(last)}</span>"
            f"<a href=\"details/{html.escape(name)}\">View</a></li>"
        )
    html_parts.extend(["</ul></div></body></html>"])
    return "".join(html_parts).encode("utf-8")


def render_details(name: str, incident_path: Path, analysis: dict[str, object] | None) -> bytes:
    """Render an incident details page including its analysis if available."""
    incident_lines = [
        line
        for line in incident_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    occurrences = len(incident_lines)
    last_seen = _last_occurrence(incident_path)
    title = name
    if isinstance(analysis, dict):
        title = str(analysis.get("impact", name))
    style = (
        "body{margin:0;padding:16px;font-family:'Roboto',sans-serif;"
        "background-color:#121212;color:#e0e0e0;}"
        "\n.card{max-width:800px;margin:0 auto;background:#1e1e1e;border-radius:12px;"
        "box-shadow:0 2px 4px rgba(0,0,0,0.6);padding:16px;}"
        "\nh1{margin-top:0;font-size:20px;}"
        "\na{color:#03a9f4;text-decoration:none;}"
        "\npre{background:#2b2b2b;padding:8px;border-radius:8px;white-space:pre-wrap;"
        "word-break:break-word;}"
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
        f"<h1>{html.escape(title)}</h1>",
        f"<p>Occurrences: {occurrences} {'occurrence' if occurrences == 1 else 'occurrences'}<br>"
        f"Last occurrence: {html.escape(last_seen)}</p>",
        "<h2>Analysis</h2>",
    ]
    if isinstance(analysis, dict):
        parts.extend([
            "<ul>",
            f"<li><strong>Root Cause:</strong> {html.escape(str(analysis.get('root_cause', '')))}</li>",
            f"<li><strong>Impact:</strong> {html.escape(str(analysis.get('impact', '')))}</li>",
            f"<li><strong>Confidence:</strong> {html.escape(str(analysis.get('confidence', '')))}</li>",
            f"<li><strong>Risk:</strong> {html.escape(str(analysis.get('risk', '')))}</li>",
        ])
        actions = analysis.get("candidate_actions") or []
        if actions:
            parts.append("<li><strong>Candidate Actions:</strong><ul>")
            for act in actions:
                action = html.escape(str(act.get("action", "")))
                rationale = html.escape(str(act.get("rationale", "")))
                parts.append(f"<li>{action}: {rationale}</li>")
            parts.append("</ul></li>")
        tests = analysis.get("tests") or []
        if tests:
            parts.append("<li><strong>Tests:</strong><ul>")
            for t in tests:
                parts.append(f"<li>{html.escape(str(t))}</li>")
            parts.append("</ul></li>")
        if "recurrence_pattern" in analysis:
            parts.append(
                f"<li><strong>Recurrence Pattern:</strong> {html.escape(str(analysis['recurrence_pattern']))}</li>"
            )
        parts.append("</ul>")
    else:
        parts.append("<p>No analysis available.</p>")
    parts.extend([
        '<p><a href="../">Back</a></p>',
        "</div></body></html>",
    ])
    return "".join(parts).encode("utf-8")


def start_http_server(
    incident_dir: Path,
    *,
    analysis_dir: Path | None = None,
    host: str = "0.0.0.0",
    port: int = 8000,
) -> ThreadingHTTPServer:
    """Start a thread-based HTTP server exposing incident and analysis bundles."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: D401 - HTTP handler
            path = unquote(self.path.rstrip("/"))
            if path == "" or path == "/":
                incidents = []
                analyses = (
                    _load_analyses(analysis_dir) if analysis_dir is not None else {}
                )
                for name in list_incidents(incident_dir):
                    inc_path = incident_dir / name
                    desc = analyses.get(name, {}).get("impact", name)
                    incidents.append((desc, _last_occurrence(inc_path), name))
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
                analyses = (
                    _load_analyses(analysis_dir) if analysis_dir is not None else {}
                )
                body = render_details(name, file_path, analyses.get(name))
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

        def log_message(self, format: str, *args: object) -> None:  # noqa: D401
            return

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
