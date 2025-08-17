from __future__ import annotations

import html
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def list_problems(directory: Path) -> list[str]:
    """Return sorted problem file names."""
    return sorted(p.name for p in directory.glob("problems_*.jsonl"))


def delete_problem(directory: Path, name: str) -> None:
    """Delete problem file ``name`` from ``directory``."""
    (directory / name).unlink(missing_ok=True)


def render_index(names: list[str]) -> bytes:
    """Render a minimal index page."""
    items = "\n".join(
        f'<li><a href="details/{html.escape(n)}">{html.escape(n)}</a></li>'
        for n in names
    )
    return f"<html><body><ul>{items}</ul></body></html>".encode()


def render_details(path: Path) -> bytes:
    """Render raw problem file content."""
    text = html.escape(path.read_text(encoding="utf-8"))
    return f"<html><body><pre>{text}</pre></body></html>".encode()


def start_http_server(directory: Path, *, port: int = 8000) -> ThreadingHTTPServer:
    """Start a simple thread-based HTTP server for problems.

    The server binds to ``0.0.0.0`` so Home Assistant can access it via ingress.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            if self.path == "/":
                body = render_index(list_problems(directory))
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/details/"):
                name = self.path.split("/", 2)[2]
                body = render_details(directory / name)
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/problems/"):
                name = self.path.split("/", 2)[2]
                try:
                    data = (directory / name).read_bytes()
                except FileNotFoundError:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(404)
            self.end_headers()

        def do_DELETE(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            if self.path.startswith("/delete/"):
                name = self.path.split("/", 2)[2]
                delete_problem(directory, name)
                self.send_response(200)
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

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
