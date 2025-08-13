"""No-op agent loop for HA LLM Ops."""

from __future__ import annotations

import logging
import os
import time


def main() -> None:
    """Run a no-op loop, logging heartbeats."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
    logger = logging.getLogger("ha_llm_ops.agent")
    logger.info("agent starting")

    try:
        while True:
            logger.debug("heartbeat")
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("agent stopping")


if __name__ == "__main__":
    main()
