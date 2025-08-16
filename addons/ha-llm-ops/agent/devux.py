"""Development UX utilities like a minimal HTTP incident endpoint."""

from __future__ import annotations

import datetime as dt
import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from urllib.parse import unquote

IGNORED_FILE = "ignored.json"


def list_incidents(directory: Path) -> list[str]:
    """Return sorted incident bundle file names."""
    return sorted(p.name for p in directory.glob("incidents_*.jsonl"))


def list_analyses(directory: Path) -> list[str]:
    """Return sorted analysis bundle file names."""
    return sorted(p.name for p in directory.glob("analyses_*.jsonl"))


def delete_incident(
    incident_dir: Path, name: str, analysis_dir: Path | None = None
) -> None:
    """Delete ``name`` from ``incident_dir`` and related analyses."""

    inc_path = incident_dir / name
    inc_path.unlink(missing_ok=True)
    if analysis_dir is None:
        return
    inc_str = str(inc_path)
    for path in analysis_dir.glob("analyses_*.jsonl"):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:  # pragma: no cover - defensive
            continue
        new_lines: list[str] = []
        changed = False
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:  # pragma: no cover - defensive
                new_lines.append(line)
                continue
            if record.get("incident") == inc_str:
                changed = True
                continue
            new_lines.append(line)
        if changed:
            if new_lines:
                path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            else:
                path.unlink(missing_ok=True)


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
    ts = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.UTC).isoformat()
    return _format_ts(ts)


def _count_occurrences(path: Path) -> int:
    """Return the number of non-empty lines in ``path``."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except FileNotFoundError:  # pragma: no cover - defensive
        return 0


def _load_ignored(directory: Path) -> set[str]:
    """Return set of ignored incident file names."""

    try:
        return set(
            json.loads((directory / IGNORED_FILE).read_text(encoding="utf-8"))
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save_ignored(directory: Path, names: set[str]) -> None:
    """Persist ignored incident ``names`` to disk."""

    (directory / IGNORED_FILE).write_text(
        json.dumps(sorted(names)), encoding="utf-8"
    )


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
            event = record.get("event")
            if isinstance(inc, str) and isinstance(result, dict):
                combined = dict(result)
                if event is not None:
                    combined["trigger_event"] = event
                mapping[Path(inc).name] = combined
    return mapping


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def render_index(entries: list[tuple[str, int, str, str, bool]]) -> bytes:
    """Render a simple HA-style page for incidents with details links."""
    items = "\n".join(
        (
            "<li class='item{}'><span class='name'>{}</span>"
            "<span class='occurrences'>{}</span>"
            "<span class='timestamp'>{}</span>"
            "<a href=\"details/{}\">View</a></li>".format(
                " ignored" if ignored else "",
                html.escape(desc),
                occ,
                html.escape(last),
                html.escape(name),
            )
        )
        for desc, occ, last, name, ignored in entries
    )
    template = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    body = Template(template).safe_substitute(items=items)
    return body.encode("utf-8")


def render_details(
    name: str,
    incident_path: Path,
    analysis: dict[str, object] | None,
    ignored: bool = False,
) -> bytes:
    """Render an incident details page including its analysis if available."""
    incident_lines = [
        line
        for line in incident_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    occurrences = len(incident_lines)
    last_seen = _last_occurrence(incident_path)
    title = name
    summary = ""
    if isinstance(analysis, dict):
        summary = str(analysis.get("summary", ""))
        title = str(summary or analysis.get("impact", name))
    title = html.escape(title)
    parts = []
    if isinstance(analysis, dict):
        parts.append("<ul>")
        trigger = analysis.get("trigger_event")
        if trigger is not None:
            event_json = html.escape(json.dumps(trigger, indent=2, sort_keys=True))
            parts.append(
                "<li><strong>Trigger Event:</strong><pre>" f"{event_json}" "</pre></li>"
            )
        parts.extend(
            [
                (
                    "<li><strong>Summary:</strong> "
                    f"{html.escape(str(analysis.get('summary', '')))}</li>"
                ),
                (
                    "<li><strong>Root Cause:</strong> "
                    f"{html.escape(str(analysis.get('root_cause', '')))}</li>"
                ),
                (
                    "<li><strong>Impact:</strong> "
                    f"{html.escape(str(analysis.get('impact', '')))}</li>"
                ),
                (
                    "<li><strong>Confidence:</strong> "
                    f"{html.escape(str(analysis.get('confidence', '')))}</li>"
                ),
                (
                    "<li><strong>Risk:</strong> "
                    f"{html.escape(str(analysis.get('risk', '')))}</li>"
                ),
            ]
        )
        actions = analysis.get("candidate_actions")
        if isinstance(actions, list):
            parts.append("<li><strong>Candidate Actions:</strong><ul>")
            for act in actions:
                if isinstance(act, dict):
                    action = html.escape(str(act.get("action", "")))
                    rationale = html.escape(str(act.get("rationale", "")))
                    parts.append(f"<li>{action}: {rationale}</li>")
            parts.append("</ul></li>")
        tests = analysis.get("tests")
        if isinstance(tests, list):
            parts.append("<li><strong>Tests:</strong><ul>")
            for t in tests:
                parts.append(f"<li>{html.escape(str(t))}</li>")
            parts.append("</ul></li>")
        if "recurrence_pattern" in analysis:
            parts.append(
                "<li><strong>Recurrence Pattern:</strong> "
                f"{html.escape(str(analysis['recurrence_pattern']))}</li>"
            )
        parts.append("</ul>")
    else:
        parts.append("<p>No analysis available.</p>")
    analysis_html = "".join(parts)
    incident_html = "<pre>" + "\n".join(
        html.escape(line) for line in incident_lines
    ) + "</pre>"
    template = (TEMPLATE_DIR / "details.html").read_text(encoding="utf-8")
    body = Template(template).safe_substitute(
        title=title,
        occurrences=occurrences,
        last_seen=html.escape(last_seen),
        incident=incident_html,
        analysis=analysis_html,
        name=html.escape(name),
        ignore_action="Unignore" if ignored else "Ignore",
    )
    return body.encode("utf-8")


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
                analyses = (
                    _load_analyses(analysis_dir) if analysis_dir is not None else {}
                )
                ignored = _load_ignored(incident_dir)
                incidents: list[tuple[str, int, str, str, bool]] = []
                for name in list_incidents(incident_dir):
                    inc_path = incident_dir / name
                    ana = analyses.get(name, {})
                    desc = str(
                        ana.get("summary")
                        or ana.get("impact")
                        or name
                    )
                    occurrences = _count_occurrences(inc_path)
                    is_ignored = name in ignored
                    incidents.append(
                        (
                            desc,
                            occurrences,
                            _last_occurrence(inc_path),
                            name,
                            is_ignored,
                        )
                    )
                active = [i for i in incidents if not i[4]]
                ignored_list = [i for i in incidents if i[4]]
                active.sort(key=lambda x: x[1], reverse=True)
                ignored_list.sort(key=lambda x: x[3])
                body = render_index(active + ignored_list)
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
                ignored = _load_ignored(incident_dir)
                body = render_details(
                    name, file_path, analyses.get(name), name in ignored
                )
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
            elif path.startswith("/ignore/"):
                name = path.split("/", 2)[2]
                ignored = _load_ignored(incident_dir)
                if name in ignored:
                    ignored.remove(name)
                else:
                    ignored.add(name)
                _save_ignored(incident_dir, ignored)
                self.send_response(303)
                self.send_header("Location", "/")
                body = b""
            elif path.startswith("/delete/"):
                name = path.split("/", 2)[2]
                delete_incident(incident_dir, name, analysis_dir)
                self.send_response(303)
                self.send_header("Location", "/")
                body = b""
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
