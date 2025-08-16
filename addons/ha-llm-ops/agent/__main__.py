"""Agent entrypoint with no-op loop."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from .devux import start_http_server
from .llm import create_llm
from .problems import monitor


def main() -> None:
    """Start the agent and run an idle loop."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
    buffer_size = os.environ.get("BUFFER_SIZE", "100")
    problem_dir = os.environ.get("INCIDENT_DIR", "/data/incidents")
    backend = os.environ.get("LLM_BACKEND")
    ws_url = os.environ.get(
        "HA_WS_URL", "ws://supervisor/core/websocket"
    )
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    logging.info(
        "Agent starting (log level: %s, buffer size: %s, problem dir: %s, ws: %s)",
        log_level,
        buffer_size,
        problem_dir,
        ws_url,
    )
    Path("/tmp/healthy").touch()
    start_http_server(Path(problem_dir))
    llm = create_llm(backend)

    async def _run() -> None:
        await monitor(ws_url, token, Path(problem_dir), llm=llm)

    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover - manual entry
    main()
