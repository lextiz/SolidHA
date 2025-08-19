import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest
import websockets

import agent.problems as problems
from agent.llm.mock import MockLLM
from agent.problems import monitor


def _event(event_type: str, data: dict) -> dict:
    return {"type": "event", "event": {"event_type": event_type, "data": data}}


async def _serve(events: list[dict]) -> tuple[Any, str]:
    async def handler(ws):
        await ws.send(json.dumps({"type": "auth_required"}))
        await ws.recv()  # auth
        await ws.send(json.dumps({"type": "auth_ok"}))
        await ws.recv()  # subscribe events
        await ws.recv()  # supervisor subscribe
        for evt in events:
            await ws.send(json.dumps(evt))
            await asyncio.sleep(0)
        await asyncio.sleep(0.1)

    server = await websockets.serve(handler, "localhost", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://localhost:{port}"


def test_monitor_analyzes_and_counts(tmp_path: Path) -> None:
    class CountingLLM(MockLLM):
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, prompt: str, *, timeout: float) -> str:
            self.calls += 1
            resp = json.loads(super().generate(prompt, timeout=timeout))
            resp["recurrence_pattern"] = '"success":false'
            return json.dumps(resp)

    llm = CountingLLM()
    events = [
        _event("trace", {"result": {"success": False}}),
        _event("trace", {"result": {"success": False, "extra": 1}}),
        _event("trace", {"result": {"success": False, "extra": 2}}),
    ]

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
    files = sorted(tmp_path.glob("problems_*.jsonl"))
    assert files
    lines = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert lines[0]["occurrence"] == 1 and "result" in lines[0]
    assert lines[0]["trigger_type"] == "automation_failure"
    assert lines[1]["occurrence"] == 2 and "result" not in lines[1]
    assert lines[1]["trigger_type"] == "automation_failure"


def test_monitor_batches_events(tmp_path: Path) -> None:
    class CountingLLM(MockLLM):
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, prompt: str, *, timeout: float) -> str:
            self.calls += 1
            resp = json.loads(super().generate(prompt, timeout=timeout))
            resp["recurrence_pattern"] = ".*"
            return json.dumps(resp)

    llm = CountingLLM()
    events = [
        _event("trace", {"result": {"success": False}}),
        _event("state_changed", {"new_state": {"state": "unavailable"}}),
    ]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                monitor(
                    url,
                    token="t",
                    problem_dir=tmp_path,
                    llm=llm,
                    limit=1,
                    batch_seconds=0.05,
                ),
                timeout=5,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())
    assert llm.calls == 1
    files = sorted(tmp_path.glob("problems_*.jsonl"))
    lines = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert len(lines[0]["event"]["events"]) == 2


def test_monitor_records_trigger_types(tmp_path: Path) -> None:
    events = [
        _event("trace", {"result": {"success": False}}),
        _event("system_log_event", {"level": 40}),
        _event("state_changed", {"new_state": {"state": "unavailable"}}),
    ]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                monitor(
                    url,
                    token="t",
                    problem_dir=tmp_path,
                    llm=MockLLM(),
                    limit=3,
                    batch_seconds=0,
                ),
                timeout=5,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())
    files = sorted(tmp_path.glob("problems_*.jsonl"))
    lines = [json.loads(line) for line in files[0].read_text().splitlines()]
    triggers = [line["trigger_type"] for line in lines]
    assert triggers == [
        "automation_failure",
        "error_log",
        "entity_unavailable",
    ]


def test_monitor_uses_saved_patterns(tmp_path: Path) -> None:
    record = {
        "event": {},
        "occurrence": 1,
        "result": {
            "summary": "s",
            "root_cause": "c",
            "impact": "i",
            "confidence": 0.5,
            "candidate_actions": [],
            "risk": "r",
            "tests": [],
            "recurrence_pattern": '"success":false',
        },
    }
    (tmp_path / "problems_0.jsonl").write_text(json.dumps(record) + "\n")

    class CountingLLM(MockLLM):
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, prompt: str, *, timeout: float) -> str:
            self.calls += 1
            return super().generate(prompt, timeout=timeout)

    llm = CountingLLM()
    events = [_event("trace", {"result": {"success": False}})]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                monitor(
                    url,
                    token="t",
                    problem_dir=tmp_path,
                    llm=llm,
                    limit=1,
                    batch_seconds=0,
                ),
                timeout=5,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())
    assert llm.calls == 0
    files = sorted(tmp_path.glob("problems_*.jsonl"))
    lines = [json.loads(line) for line in files[-1].read_text().splitlines()]
    assert lines[0]["occurrence"] == 2 and "result" not in lines[0]


def test_monitor_recurs_with_whitespace_pattern(tmp_path: Path) -> None:
    class CountingLLM(MockLLM):
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, prompt: str, *, timeout: float) -> str:
            self.calls += 1
            resp = json.loads(super().generate(prompt, timeout=timeout))
            resp["recurrence_pattern"] = r'"result":\s*\{[\s\S]*"success": false'
            return json.dumps(resp)

    llm = CountingLLM()
    events = [
        _event("trace", {"result": {"success": False}}),
        _event("trace", {"result": {"success": False, "extra": 1}}),
    ]

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
    files = sorted(tmp_path.glob("problems_*.jsonl"))
    lines = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert lines[1]["occurrence"] == 2


def test_monitor_filters_events(tmp_path: Path) -> None:
    msgs = [
        {"type": "pong"},
        _event("system_log_event", {"level": 20}),
        _event("trace", {"result": {"success": False}}),
        _event("system_log_event", {"level": 40}),
        _event("system_log_event", {"level": "ERROR"}),
        _event("state_changed", {"new_state": {"state": "unavailable"}}),
        _event("supervisor_event", {"event": "addon", "data": {"level": 40}}),
        _event(
            "supervisor_event",
            {"event": "addon", "data": {"level": "ERROR"}},
        ),
    ]

    async def run_test() -> None:
        server, url = await _serve(msgs)
        try:
            await asyncio.wait_for(
                monitor(
                    url,
                    token="t",
                    problem_dir=tmp_path,
                    llm=MockLLM(),
                    limit=6,
                    batch_seconds=0,
                ),
                timeout=3,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())

    files = sorted(tmp_path.glob("problems_*.jsonl"))
    lines = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert len(lines) == 6


def test_monitor_extra_headers_and_break(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FakeConn:
        def __init__(self) -> None:
            self._msgs = iter(
                [
                    json.dumps({"type": "auth_required"}),
                    json.dumps({"type": "auth_ok"}),
                ]
            )

        async def send(self, msg: str) -> None:  # pragma: no cover - no behavior
            pass

        async def recv(self) -> str:
            return next(self._msgs)

        async def __aenter__(self) -> "FakeConn":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        def __aiter__(self) -> "FakeConn":
            return self

        async def __anext__(self) -> str:
            raise StopAsyncIteration

    def fake_connect(
        url: str, *, subprotocols: list[str], extra_headers: dict[str, str]
    ) -> FakeConn:
        assert "Authorization" in extra_headers
        return FakeConn()

    monkeypatch.setattr("agent.problems.websockets.connect", fake_connect)

    asyncio.run(
        monitor(
            "ws://example",
            token="t",
            problem_dir=tmp_path,
            llm=MockLLM(),
            limit=0,
            batch_seconds=0,
        )
    )


def test_monitor_breaks_on_connection_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FailingConnect:
        async def __aenter__(self) -> None:
            raise websockets.exceptions.ConnectionClosed(1000, "boom")

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    def fake_connect(*args: Any, **kwargs: Any) -> FailingConnect:
        return FailingConnect()

    async def fast_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(problems.websockets, "connect", fake_connect)
    monkeypatch.setattr(problems.asyncio, "sleep", fast_sleep)

    asyncio.run(
        monitor(
            "ws://example",
            token="t",
            problem_dir=tmp_path,
            llm=MockLLM(),
            limit=0,
        )
    )


def test_monitor_rate_limit(tmp_path: Path) -> None:
    timestamps: list[float] = []

    class TimeLLM(MockLLM):
        def generate(self, prompt: str, *, timeout: float) -> str:
            timestamps.append(time.monotonic())
            return super().generate(prompt, timeout=timeout)

    events = [
        _event("trace", {"result": {"success": False}}),
        _event("trace", {"result": {"success": False, "x": 1}}),
    ]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                monitor(
                    url,
                    token="t",
                    problem_dir=tmp_path,
                    llm=TimeLLM(),
                    limit=2,
                    analysis_rate_seconds=0.2,
                    batch_seconds=0,
                ),
                timeout=5,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())
    assert timestamps[1] - timestamps[0] >= 0.2


def test_monitor_truncates_context(tmp_path: Path) -> None:
    captured: list[str] = []

    class CaptureLLM(MockLLM):
        def generate(self, prompt: str, *, timeout: float) -> str:
            captured.append(prompt)
            return super().generate(prompt, timeout=timeout)

    payload = {"lines": [str(i) for i in range(10)]}
    events = [_event("trace", {"result": {"success": False, **payload}})]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                monitor(
                    url,
                    token="t",
                    problem_dir=tmp_path,
                    llm=CaptureLLM(),
                    limit=1,
                    analysis_max_lines=5,
                    batch_seconds=0,
                ),
                timeout=5,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())
    prompt = captured[0]
    ctx = prompt.split("Context:\n", 1)[1]
    assert len(ctx.splitlines()) <= 5
