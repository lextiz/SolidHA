import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import pytest
import websockets

from agent.llm.mock import MockLLM
from agent.problems import monitor


def _event(event_type: str, data: dict) -> dict:
    return {"type": "event", "event": {"event_type": event_type, "data": data}}


async def _serve(events: list[dict]) -> tuple[Any, str]:
    async def handler(ws):
        await ws.send(json.dumps({"type": "auth_required"}))
        await ws.recv()
        await ws.send(json.dumps({"type": "auth_ok"}))
        await ws.recv()
        msg = json.loads(await ws.recv())
        assert "id" in msg
        for evt in events:
            await ws.send(json.dumps(evt))
        await asyncio.sleep(0.1)

    server = await websockets.serve(handler, "localhost", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://localhost:{port}"


def test_logging_success_and_existing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    class CountingLLM(MockLLM):
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, prompt: str, *, timeout: float) -> str:
            self.calls += 1
            resp = json.loads(super().generate(prompt, timeout=timeout))
            resp["recurrence_pattern"] = '"success": false'
            return json.dumps(resp)

    llm = CountingLLM()
    events = [
        _event("trace", {"result": {"success": False}}),
        _event("trace", {"result": {"success": False, "extra": 1}}),
    ]

    caplog.set_level(logging.DEBUG)

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                monitor(
                    url,
                    token="t",
                    problem_dir=tmp_path,
                    llm=llm,
                    limit=2,
                    batch_seconds=0,
                ),
                timeout=3,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())

    assert llm.calls == 1
    assert any(
        r.levelno == logging.WARNING and "New problem found" in r.message
        for r in caplog.records
    )
    assert any(
        r.levelno == logging.DEBUG and "Sending problem for analysis" in r.message
        for r in caplog.records
    )
    assert any(
        r.levelno == logging.INFO and "Analysis successful" in r.message
        for r in caplog.records
    )
    assert any(
        r.levelno == logging.INFO and "Existing problem occurred again" in r.message
        for r in caplog.records
    )
    assert not any(
        "Existing problem occurred again" in r.message and "extra" in r.message
        for r in caplog.records
    )


def test_logging_analysis_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    class FailingLLM(MockLLM):
        def generate(self, prompt: str, *, timeout: float) -> str:  # type: ignore[override]
            raise RuntimeError("boom")

    events = [_event("trace", {"result": {"success": False}})]
    caplog.set_level(logging.DEBUG)

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                monitor(
                    url,
                    token="t",
                    problem_dir=tmp_path,
                    llm=FailingLLM(),
                    limit=1,
                    batch_seconds=0,
                ),
                timeout=3,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())

    assert any(
        r.levelno == logging.WARNING and "New problem found" in r.message
        for r in caplog.records
    )
    assert any(
        r.levelno == logging.DEBUG and "Sending problem for analysis" in r.message
        for r in caplog.records
    )
    assert any(
        r.levelno == logging.ERROR and "Analysis failed" in r.message
        for r in caplog.records
    )
