"""Agent entrypoint with no-op loop."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path


def main() -> None:
    """Start the agent and run an idle loop."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
    buffer_size = os.environ.get("BUFFER_SIZE", "100")
    incident_dir = os.environ.get("INCIDENT_DIR", "/data/incidents")
    logging.info(
        "Agent starting (log level: %s, buffer size: %s, incident dir: %s)",
        log_level,
        buffer_size,
        incident_dir,
    )
    Path("/tmp/healthy").touch()
    while True:
        logging.debug("agent idle")
        time.sleep(60)


if __name__ == "__main__":  # pragma: no cover - manual entry
    main()
