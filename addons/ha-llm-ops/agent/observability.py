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
from websockets.exceptions import ConnectionClosed, InvalidHandshake


class AuthenticationError(RuntimeError):
    """Raised when Home Assistant authentication fails."""


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

    Always send the access token in the auth message. Some Home Assistant
    versions also accept the token via the ``Authorization`` header, but
    providing it in the message ensures compatibility across versions.
    """

    messages: list[dict[str, Any]] = []

    msg = json.loads(await ws.recv())
    messages.append(msg)
    if msg.get("type") != "auth_required":  # pragma: no cover - defensive
        pretty = json.dumps(messages, indent=2)
        raise AuthenticationError(f"unexpected auth sequence: {pretty}")

    await ws.send(json.dumps({"type": "auth", "access_token": token}))
    msg = json.loads(await ws.recv())
    messages.append(msg)

    if msg.get("type") != "auth_ok":  # pragma: no cover - defensive
        pretty = json.dumps(messages, indent=2)
        raise AuthenticationError(f"authentication failed: {pretty}")


async def observe(
    url: str,
    token: str,
    incident_dir: Path,
    *,
    max_bytes: int = 1_000_000,
    limit: int | None = None,
) -> None:
    """Connect to the HA WebSocket API and persist selected events."""
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

                    logger.write(event)
                    processed += 1
                    if limit is not None and processed >= limit:
                        return
        except InvalidHandshake:  # pragma: no cover - handshake retry path
            kwargs.pop("subprotocols", None)
            continue
        except ConnectionClosed as err:  # pragma: no cover - network error path
            logging.exception("WebSocket error: %s", err)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
        except AuthenticationError as err:  # pragma: no cover - auth error path
            logging.exception("WebSocket error: %s", err)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
        except Exception as err:  # pragma: no cover - network error path
            logging.exception("WebSocket error: %s", err)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
        else:  # pragma: no cover - connection closed gracefully
            backoff = 1
        if limit is not None and processed >= limit:
            break
