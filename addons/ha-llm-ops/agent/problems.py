"""WebSocket observability utilities for Home Assistant."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

import websockets
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from .llm import LLM, create_llm
from .parse import parse_result
from .prompt import build_rca_prompt


class AuthenticationError(RuntimeError):
    """Raised when Home Assistant authentication fails."""


class ProblemLogger:
    """Write problems to rotating JSONL files."""

    def __init__(self, directory: Path, max_bytes: int = 1_000_000) -> None:
        self.directory = directory
        self.max_bytes = max_bytes
        self.directory.mkdir(parents=True, exist_ok=True)
        self._counter = 0
        self._file = self._open_file()

    def _open_file(self) -> TextIO:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = self.directory / f"problems_{timestamp}_{self._counter}.jsonl"
        self._counter += 1
        return path.open("a", encoding="utf-8")

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, sort_keys=True)
        if self._file.tell() + len(line) + 1 > self.max_bytes:
            self._file.close()
            self._file = self._open_file()
        self._file.write(line + "\n")
        self._file.flush()


def _contains_failure(obj: Any) -> bool:
    """Recursively detect failure markers in ``obj``.

    Home Assistant trace events for automations and scripts can nest results
    deeply. A failure may appear anywhere in the structure via an ``error``
    field or a ``success`` flag set to ``False``. This helper walks the object
    to find any such markers.
    """

    if isinstance(obj, dict):
        if obj.get("error") or obj.get("success") is False:
            return True
        return any(_contains_failure(v) for v in obj.values())
    if isinstance(obj, Iterable) and not isinstance(obj, (str | bytes)):
        return any(_contains_failure(v) for v in obj)
    return False


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


async def monitor(
    url: str,
    token: str,
    problem_dir: Path,
    *,
    max_bytes: int = 1_000_000,
    limit: int | None = None,
    llm: LLM | None = None,
    analysis_rate_seconds: float = 0.0,
    analysis_max_lines: int | None = None,
) -> None:
    """Observe events and analyze problems in a single loop."""

    logger = ProblemLogger(problem_dir, max_bytes=max_bytes)
    llm = llm or create_llm()
    problems: list[dict[str, Any]] = []
    backoff = 1
    processed = 0

    headers = {"Authorization": f"Bearer {token}"}
    kwargs: dict[str, Any] = {"subprotocols": ["homeassistant"]}
    if "extra_headers" in inspect.signature(websockets.connect).parameters:
        kwargs["extra_headers"] = headers
    else:
        kwargs["additional_headers"] = headers

    last_analysis = 0.0
    while True:
        try:
            async with websockets.connect(url, **kwargs) as ws:
                await _authenticate(ws, token)
                await ws.send(json.dumps({"id": 1, "type": "subscribe_events"}))
                await ws.send(json.dumps({"type": "supervisor/subscribe"}))
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
                        if _contains_failure(edata):
                            should_log = True
                    elif etype == "state_changed":
                        new_state = edata.get("new_state") or {}
                        if (
                            isinstance(new_state, dict)
                            and new_state.get("state") == "unavailable"
                        ):
                            should_log = True
                    elif etype == "supervisor_event":
                        if edata.get("event") == "addon":
                            log = edata.get("data", {})
                            level = log.get("level")
                            if isinstance(level, int):
                                should_log = level >= 40
                            elif isinstance(level, str):
                                should_log = level.upper() in {"ERROR", "CRITICAL"}

                    if not should_log:
                        continue

                    event_json = json.dumps(event, sort_keys=True)
                    matched: dict[str, Any] | None = None
                    for problem in problems:
                        if problem["pattern"].search(event_json):
                            matched = problem
                            break

                    if matched is None:
                        record: dict[str, Any] = {"event": event, "occurrence": 1}
                        now = asyncio.get_event_loop().time()
                        delay = last_analysis + analysis_rate_seconds - now
                        if delay > 0:
                            await asyncio.sleep(delay)
                        prompt = build_rca_prompt(event, max_lines=analysis_max_lines)
                        raw = llm.generate(prompt, timeout=300)
                        result = parse_result(raw)
                        last_analysis = asyncio.get_event_loop().time()
                        record["result"] = result.model_dump()
                        try:
                            pattern = re.compile(result.recurrence_pattern)
                        except re.error:  # pragma: no cover - defensive
                            pattern = re.compile(re.escape(result.recurrence_pattern))
                        problems.append({"pattern": pattern, "count": 1})
                    else:
                        matched["count"] += 1
                        record = {"event": event, "occurrence": matched["count"]}

                    logger.write(record)
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


__all__ = ["AuthenticationError", "monitor"]
