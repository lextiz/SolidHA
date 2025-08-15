"""WebSocket observability utilities for Home Assistant."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

import websockets

from .redact import load_secret_keys, redact


class IncidentLogger:
    """Write events to rotating JSONL files."""

    def __init__(self, directory: Path, max_bytes: int = 1_000_000) -> None:
        self.directory = directory
        self.max_bytes = max_bytes
        self.directory.mkdir(parents=True, exist_ok=True)
        self._counter = 0
        self._file = self._open_file()

    def _open_file(self) -> TextIO:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = self.directory / f"incidents_{timestamp}_{self._counter}.jsonl"
        self._counter += 1
        return path.open("a", encoding="utf-8")

    def write(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, sort_keys=True)
        if self._file.tell() + len(line) + 1 > self.max_bytes:
            self._file.close()
            self._file = self._open_file()
        self._file.write(line + "\n")
        self._file.flush()


async def _authenticate(ws: Any, token: str) -> None:
    """Perform Home Assistant WebSocket authentication.

    The HA Supervisor proxies the WebSocket API and authenticates via the
    ``Authorization`` header rather than an ``access_token`` message. When
    connecting directly to Home Assistant, an ``access_token`` message is still
    required.  To support both cases we first try token-based auth and, on
    failure, retry without the token which allows header-based auth to succeed.
    """

    msg = json.loads(await ws.recv())
    if msg.get("type") != "auth_required":  # pragma: no cover - defensive
        raise RuntimeError("unexpected auth sequence")

    await ws.send(json.dumps({"type": "auth", "access_token": token}))
    msg = json.loads(await ws.recv())

    if msg.get("type") == "auth_invalid":
        # Some environments (e.g. HA Supervisor proxy) authenticate via the
        # Authorization header and expect an empty auth message.
        await ws.send(json.dumps({"type": "auth"}))
        msg = json.loads(await ws.recv())

    if msg.get("type") != "auth_ok":  # pragma: no cover - defensive
        raise RuntimeError("authentication failed")


async def observe(
    url: str,
    token: str,
    incident_dir: Path,
    *,
    max_bytes: int = 1_000_000,
    limit: int | None = None,
    secrets_path: Path = Path("/config/secrets.yaml"),
) -> None:
    """Connect to the HA WebSocket API and persist selected events."""
    secret_keys = load_secret_keys(secrets_path)
    logger = IncidentLogger(incident_dir, max_bytes=max_bytes)
    backoff = 1
    processed = 0

    headers = {"Authorization": f"Bearer {token}"}
    kwargs: dict[str, Any] = {"subprotocols": ["homeassistant"]}
    if "extra_headers" in inspect.signature(websockets.connect).parameters:
        kwargs["extra_headers"] = headers
    else:
        kwargs["additional_headers"] = headers
    while True:
        try:
            async with websockets.connect(url, **kwargs) as ws:
                await _authenticate(ws, token)
                await ws.send(json.dumps({"id": 1, "type": "subscribe_events"}))
                async for message in ws:
                    data = json.loads(message)
                    if data.get("type") != "event":
                        continue
                    event = data.get("event", {})
                    etype = event.get("event_type")
                    edata = event.get("data", {})

                    should_log = False

                    if etype == "system_log_event":
                        level = edata.get("level")
                        if isinstance(level, int):
                            should_log = level >= 40
                        elif isinstance(level, str):
                            should_log = level.upper() in {"ERROR", "CRITICAL"}
                    elif etype == "trace":
                        result = edata.get("result")
                        if isinstance(result, dict):
                            if result.get("success") is False or result.get("error"):
                                should_log = True
                        elif edata.get("error"):
                            should_log = True
                    elif etype == "state_changed":
                        new_state = edata.get("new_state") or {}
                        if (
                            isinstance(new_state, dict)
                            and new_state.get("state") == "unavailable"
                        ):
                            should_log = True

                    if not should_log:
                        continue

                    redacted = redact(event, secret_keys)
                    logger.write(redacted)
                    processed += 1
                    if limit is not None and processed >= limit:
                        return
        except Exception as err:  # pragma: no cover - network error path
            logging.exception("WebSocket error: %s", err)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
        else:  # pragma: no cover - connection closed gracefully
            backoff = 1
        if limit is not None and processed >= limit:
            break
