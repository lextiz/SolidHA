"""Agent entrypoint with no-op loop."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from pathlib import Path

from .analysis.runner import AnalysisRunner, create_llm
from .devux import start_http_server
from .observability import observe


def main() -> None:
    """Start the agent and run an idle loop."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
    buffer_size = os.environ.get("BUFFER_SIZE", "100")
    incident_dir = os.environ.get("INCIDENT_DIR", "/data/incidents")
    analysis_dir = Path("/data/analyses")
    rate = float(os.environ.get("ANALYSIS_RATE_SECONDS", "60"))
    max_lines = int(os.environ.get("ANALYSIS_MAX_LINES", "50"))
    backend = os.environ.get("LLM_BACKEND")
    ws_url = os.environ.get(
        "HA_WS_URL", "ws://supervisor/core/websocket"
    )
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    logging.info(
        "Agent starting (log level: %s, buffer size: %s, incident dir: %s, ws: %s)",
        log_level,
        buffer_size,
        incident_dir,
        ws_url,
    )
    Path("/tmp/healthy").touch()
    start_http_server(Path(incident_dir), analysis_dir=analysis_dir)
    llm = create_llm(backend)
    runner = AnalysisRunner(
        Path(incident_dir), analysis_dir, llm, rate_seconds=rate, max_lines=max_lines
    )

    async def _run() -> None:
        task = asyncio.create_task(runner.run_forever())
        try:
            await observe(ws_url, token, Path(incident_dir))
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover - manual entry
    main()
