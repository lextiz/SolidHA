"""Development UX utilities like a minimal HTTP incident endpoint."""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from typing import Any


@dataclass
class _ProblemEntry:
    summary: str
    occurrences: int
    last_seen: str
    analysis: dict[str, Any]
    events: list[str]
    pattern: re.Pattern[str]


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def list_problems(directory: Path) -> list[str]:
    """Return sorted problem log file names."""

    return sorted(p.name for p in directory.glob("problems_*.jsonl"))


def _format_ts(value: str) -> str:
    """Return ``value`` formatted as ``YYYY-MM-DD HH:MM:SS`` if possible."""

    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:  # pragma: no cover - best effort
        return value
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _event_ts(event: dict[str, Any]) -> str:
    for key in ("time_fired", "timestamp", "time"):
        if key in event:
            return _format_ts(str(event[key]))
    return ""


def _load_problems(directory: Path) -> dict[str, _ProblemEntry]:
    """Return mapping of problem key to latest info and events."""

    mapping: dict[str, _ProblemEntry] = {}
    for path in sorted(directory.glob("problems_*.jsonl")):
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
            event = record.get("event")
            if not isinstance(event, dict):
                continue
            event_json = json.dumps(event, sort_keys=True)
            ts = _event_ts(event)
            result = record.get("result")
            if isinstance(result, dict) and "recurrence_pattern" in result:
                key = hashlib.sha1(
                    result["recurrence_pattern"].encode("utf-8")
                ).hexdigest()
                pattern = re.compile(result["recurrence_pattern"])
                entry = mapping.get(key)
                if entry is None:
                    summary = str(result.get("summary") or result.get("impact") or key)
                    entry = _ProblemEntry(
                        summary=summary,
                        occurrences=0,
                        last_seen="",
                        analysis=result,
                        events=[],
                        pattern=pattern,
                    )
                    mapping[key] = entry
                entry.events.append(event_json)
                entry.occurrences = record.get("occurrence", 1)
                if ts:
                    entry.last_seen = ts
                continue
            # match existing problems
            matched: _ProblemEntry | None = None
            for entry in mapping.values():
                if entry.pattern.search(event_json):
                    matched = entry
                    break
            if matched is None:
                continue
            matched.events.append(event_json)
            matched.occurrences = record.get("occurrence", matched.occurrences + 1)
            if ts:
                matched.last_seen = ts
    return mapping


def delete_problem(directory: Path, key: str) -> None:
    """Delete all records for problem ``key`` from ``directory``."""

    problems = _load_problems(directory)
    entry = problems.get(key)
    if entry is None:
        return
    pattern = entry.pattern
    for path in directory.glob("problems_*.jsonl"):
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
            event = record.get("event")
            if isinstance(event, dict):
                event_json = json.dumps(event, sort_keys=True)
                if pattern.search(event_json):
                    changed = True
                    continue
            new_lines.append(line)
        if changed:
            if new_lines:
                path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            else:
                path.unlink(missing_ok=True)


def render_index(entries: list[tuple[str, int, str, str]]) -> bytes:
    """Render a simple HA-style page for problems with details links."""

    items = "\n".join(
        (
            f"<li class='item'><span class='name'>{html.escape(desc)}</span>"
            f"<span class='occurrences'>{occ}</span>"
            f"<span class='timestamp'>{html.escape(last)}</span>"
            f'<a href="details/{html.escape(name)}">View</a></li>'
        )
        for desc, occ, last, name in entries
    )
    template = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    body = Template(template).safe_substitute(items=items)
    return body.encode("utf-8")


def _analysis_html(analysis: dict[str, Any]) -> str:
    parts = ["<ul>"]
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
    return "".join(parts)


def render_details(name: str, entry: _ProblemEntry) -> bytes:
    """Render a problem details page including its analysis."""

    incident_html = (
        "<pre>" + "\n".join(html.escape(line) for line in entry.events) + "</pre>"
    )
    analysis_html = _analysis_html(entry.analysis)
    template = (TEMPLATE_DIR / "details.html").read_text(encoding="utf-8")
    body = Template(template).safe_substitute(
        title=html.escape(entry.summary),
        occurrences=entry.occurrences,
        last_seen=html.escape(entry.last_seen),
        incident=incident_html,
        analysis=analysis_html,
        name=html.escape(name),
    )
    return body.encode("utf-8")


def start_http_server(directory: Path, *, port: int = 8000) -> ThreadingHTTPServer:
    """Start a thread-based HTTP server exposing problem bundles."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: D401 - HTTP handler
            path = self.path.rstrip("/")
            if path == "" or path == "/":
                problems = _load_problems(directory)
                entries = [
                    (p.summary, p.occurrences, p.last_seen, key)
                    for key, p in problems.items()
                ]
                entries.sort(key=lambda x: x[1], reverse=True)
                body = render_index(entries)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif path.startswith("/details/"):
                name = path.split("/", 2)[2]
                problems = _load_problems(directory)
                entry = problems.get(name)
                if entry is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                body = render_details(name, entry)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif path == "/problems":
                body = json.dumps(list_problems(directory)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path.startswith("/problems/"):
                name = path.split("/", 2)[2]
                file_path = directory / name
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

        def do_DELETE(self) -> None:  # noqa: D401 - HTTP handler
            if self.path.startswith("/delete/"):
                name = self.path.split("/", 2)[2]
                delete_problem(directory, name)
                self.send_response(200)
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: D401
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


__all__ = [
    "list_problems",
    "delete_problem",
    "render_index",
    "render_details",
    "start_http_server",
]
