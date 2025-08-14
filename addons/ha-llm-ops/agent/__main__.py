"""Agent entrypoint with no-op loop."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from .devux import start_http_server
from .observability import observe


def main() -> None:
    """Start the agent and run an idle loop."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
    buffer_size = os.environ.get("BUFFER_SIZE", "100")
    incident_dir = os.environ.get("INCIDENT_DIR", "/data/incidents")
    ws_url = os.environ.get("HA_WS_URL", "ws://localhost:8123/api/websocket")
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    logging.info(
        "Agent starting (log level: %s, buffer size: %s, incident dir: %s, ws: %s)",
        log_level,
        buffer_size,
        incident_dir,
        ws_url,
    )
    Path("/tmp/healthy").touch()
    start_http_server(Path(incident_dir))
    asyncio.run(observe(ws_url, token, Path(incident_dir)))


if __name__ == "__main__":  # pragma: no cover - manual entry
    main()
