"""WebSocket observability utilities for Home Assistant."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import logging
import re
from collections.abc import Callable, Coroutine, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

import websockets
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from .llm import LLM, create_llm
from .parse import parse_result
from .prompt import build_rca_prompt

LOGGER = logging.getLogger(__name__)


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


def _load_problems(directory: Path) -> list[dict[str, Any]]:
    """Load previously seen problems from ``directory``."""

    loaded: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("problems_*.jsonl")):
        try:
            for line in path.read_text().splitlines():
                data = json.loads(line)
                result = data.get("result") or {}
                pattern = result.get("recurrence_pattern")
                if not isinstance(pattern, str):
                    continue
                occ = data.get("occurrence")
                if isinstance(occ, int):
                    entry = loaded.setdefault(pattern, {"count": 0})
                    entry["count"] = max(entry["count"], occ)
        except OSError:  # pragma: no cover - defensive
            continue
    problems: list[dict[str, Any]] = []
    for pattern, entry in loaded.items():
        try:
            compiled = re.compile(pattern, re.DOTALL)
        except re.error:  # pragma: no cover - defensive
            compiled = re.compile(re.escape(pattern), re.DOTALL)
        problems.append({"pattern": compiled, "count": entry["count"]})
    return problems


class EventBatcher:
    """Group events occurring within a time window."""

    def __init__(
        self,
        window: float,
        callback: Callable[[list[dict[str, Any]]], Coroutine[Any, Any, None]],
    ) -> None:
        self.window = window
        self.callback = callback
        self._events: list[dict[str, Any]] = []
        self._task: asyncio.Task[None] | None = None
        self._immediate: list[asyncio.Task[None]] = []

    def add(self, event: dict[str, Any]) -> None:
        if self.window <= 0:
            loop = asyncio.get_event_loop()
            self._immediate.append(loop.create_task(self.callback([event])))
            return
        self._events.append(event)
        if self._task is None:
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._run())

    async def _run(self) -> None:
        await asyncio.sleep(self.window)
        events = self._events
        self._events = []
        await self.callback(events)
        if self._events:
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._run())
        else:
            self._task = None

    async def flush(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._events:
            events = self._events
            self._events = []
            await self.callback(events)
        if self._immediate:
            await asyncio.gather(*self._immediate)
            self._immediate.clear()


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
    batch_seconds: float = 1.0,
) -> None:
    """Observe events and analyze problems in a single loop."""

    problem_logger = ProblemLogger(problem_dir, max_bytes=max_bytes)
    llm = llm or create_llm()
    problems = _load_problems(problem_dir)
    backoff = 1
    processed = 0
    stop = False

    headers = {"Authorization": f"Bearer {token}"}
    kwargs: dict[str, Any] = {"subprotocols": ["homeassistant"]}
    if "extra_headers" in inspect.signature(websockets.connect).parameters:
        kwargs["extra_headers"] = headers
    else:
        kwargs["additional_headers"] = headers

    last_analysis = 0.0
    last_time_fired: datetime | None = None

    async def handle_batch(events: list[dict[str, Any]]) -> None:
        nonlocal last_analysis, processed, stop
        event_ctx: dict[str, Any] = (
            events[0] if len(events) == 1 else {"events": events}
        )
        event_json = json.dumps(event_ctx, sort_keys=True, indent=2)
        event_json_compact = json.dumps(
            event_ctx, sort_keys=True, separators=(",", ":")
        )
        matched: dict[str, Any] | None = None
        for problem in problems:
            if problem["pattern"].search(event_json) or problem["pattern"].search(
                event_json_compact
            ):
                matched = problem
                break

        etype = events[0].get("event_type")
        edata = events[0].get("data", {})
        triggers_set: set[str] = set()
        for e in events:
            t = e.get("trigger_type")
            if isinstance(t, str):
                triggers_set.add(t)
        triggers = sorted(triggers_set)
        trigger = ",".join(triggers) if triggers else None
        if matched is None:
            LOGGER.warning("New problem found: type=%s data=%s", etype, edata)
            record: dict[str, Any] = {
                "event": event_ctx,
                "occurrence": 1,
            }
            if trigger:
                record["trigger_type"] = trigger
            now = asyncio.get_event_loop().time()
            delay = last_analysis + analysis_rate_seconds - now
            if delay > 0:
                await asyncio.sleep(delay)
            LOGGER.debug("Sending problem for analysis: event=%s", event_json)
            try:
                prompt = build_rca_prompt(event_ctx, max_lines=analysis_max_lines)
                raw = llm.generate(prompt, timeout=300)
                result = parse_result(raw)
            except Exception:  # pragma: no cover - error path
                LOGGER.exception("Analysis failed for event %s", event_json)
                record["error"] = "analysis_failed"
            else:
                last_analysis = asyncio.get_event_loop().time()
                record["result"] = result.model_dump()
                LOGGER.info(
                    "Analysis successful: summary=%s pattern=%s",
                    result.summary,
                    result.recurrence_pattern,
                )
                try:
                    pattern = re.compile(result.recurrence_pattern, re.DOTALL)
                except re.error:  # pragma: no cover - defensive
                    pattern = re.compile(
                        re.escape(result.recurrence_pattern), re.DOTALL
                    )
                problems.append({"pattern": pattern, "count": 1})
        else:
            matched["count"] += 1
            LOGGER.info(
                "Existing problem occurred again: pattern=%s occurrence=%s type=%s",
                matched["pattern"].pattern,
                matched["count"],
                etype,
            )
            record = {
                "event": event_ctx,
                "occurrence": matched["count"],
            }
            if trigger:
                record["trigger_type"] = trigger

        problem_logger.write(record)
        processed += 1
        if limit is not None and processed >= limit:
            stop = True

    batcher = EventBatcher(batch_seconds, handle_batch)

    while True:
        try:
            async with websockets.connect(url, **kwargs) as ws:
                await _authenticate(ws, token)
                await ws.send(json.dumps({"id": 1, "type": "subscribe_events"}))
                await ws.send(json.dumps({"id": 2, "type": "supervisor/subscribe"}))
                async for message in ws:
                    if stop:
                        break
                    data = json.loads(message)
                    if data.get("type") != "event":
                        continue
                    event = data.get("event", {})
                    etype = event.get("event_type")
                    edata = event.get("data", {})
                    time_str = event.get("time_fired")
                    evt_time = None
                    if isinstance(time_str, str):
                        with contextlib.suppress(ValueError):
                            evt_time = datetime.fromisoformat(time_str)

                    trigger_type: str | None = None

                    if etype == "system_log_event":
                        level = edata.get("level")
                        if isinstance(level, int):
                            if level >= 40:
                                trigger_type = "error_log"
                        elif isinstance(level, str):
                            if level.upper() in {"ERROR", "CRITICAL"}:
                                trigger_type = "error_log"
                    elif etype == "trace":
                        if _contains_failure(edata):
                            trigger_type = "automation_failure"
                    elif etype == "state_changed":
                        new_state = edata.get("new_state") or {}
                        if (
                            isinstance(new_state, dict)
                            and new_state.get("state") == "unavailable"
                        ):
                            trigger_type = "entity_unavailable"
                    elif etype == "supervisor_event":
                        if edata.get("event") == "addon":
                            log = edata.get("data", {})
                            level = log.get("level")
                            if isinstance(level, int):
                                if level >= 40:
                                    trigger_type = "error_log"
                            elif isinstance(level, str):
                                if level.upper() in {"ERROR", "CRITICAL"}:
                                    trigger_type = "error_log"

                    if trigger_type is None:
                        continue

                    if evt_time is not None and last_time_fired is not None:
                        if (evt_time - last_time_fired).total_seconds() > batch_seconds:
                            await batcher.flush()
                    if evt_time is not None:
                        last_time_fired = evt_time

                    event["trigger_type"] = trigger_type
                    batcher.add(event)
                await batcher.flush()
                if stop or limit == 0:
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
        if stop or limit == 0:
            break


__all__ = ["AuthenticationError", "monitor"]
