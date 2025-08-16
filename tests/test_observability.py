import asyncio
import json
from pathlib import Path

import pytest
import websockets

from agent.observability import AuthenticationError, _authenticate, observe


def _event(event_type: str, data: dict) -> dict:
    return {"type": "event", "event": {"event_type": event_type, "data": data}}


async def _serve(events: list[dict]) -> str:
    async def handler(ws):
        await ws.send(json.dumps({"type": "auth_required"}))
        await ws.recv()  # auth
        await ws.send(json.dumps({"type": "auth_ok"}))
        await ws.recv()  # subscribe events
        await ws.recv()  # supervisor subscribe
        for evt in events:
            await ws.send(json.dumps(evt))
        await asyncio.sleep(0.1)

    server = await websockets.serve(handler, "localhost", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://localhost:{port}"


async def _serve_auth_failure() -> str:
    """Server that always fails token authentication."""

    async def handler(ws):
        await ws.send(json.dumps({"type": "auth_required"}))
        msg = json.loads(await ws.recv())
        assert msg == {"type": "auth", "access_token": "t"}
        await ws.send(json.dumps({"type": "auth_invalid"}))

    server = await websockets.serve(handler, "localhost", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://localhost:{port}"


def test_observe_writes_events(tmp_path: Path) -> None:
    events = [
        _event(
            "system_log_event",
            {
                "level": 50,
                "message": "token ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
                "api_key": "supersecret",
            },
        ),
        _event(
            "system_log_event",
            {
                "level": 20,
                "message": "ignored",
                "api_key": "supersecret",
            },
        ),
        _event(
            "trace",
            {
                "result": {"success": False, "error": "boom"},
                "password": "hidden",
            },
        ),
        _event("trace", {"result": {"success": True}}),
        _event(
            "state_changed",
            {
                "entity_id": "sensor.x",
                "new_state": {"state": "unavailable", "token": "ZZZZYYYY"},
            },
        ),
        _event(
            "state_changed",
            {
                "entity_id": "sensor.x",
                "new_state": {"state": "on"},
            },
        ),
    ]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                observe(
                    url,
                    token="t",
                    incident_dir=tmp_path,
                    max_bytes=120,
                    limit=3,
                ),
                timeout=3,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())

    files = sorted(tmp_path.glob("incidents_*.jsonl"))
    assert len(files) >= 2  # rotation happened

    lines = []
    for file in files:
        lines.extend(json.loads(line) for line in file.read_text().splitlines())

    assert len(lines) == 3
    assert {line["event_type"] for line in lines} == {
        "system_log_event",
        "trace",
        "state_changed",
    }


def test_auth_failure_includes_details(tmp_path: Path) -> None:
    async def run_test() -> None:
        server, url = await _serve_auth_failure()
        try:
            async with websockets.connect(url) as ws:
                with pytest.raises(AuthenticationError) as ctx:
                    await _authenticate(ws, "t")
                detail = ctx.value.args[0].split(": ", 1)[1]
                data = json.loads(detail)
                assert data[-1]["type"] == "auth_invalid"
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())


def test_observe_logs_failing_automation_and_script(tmp_path: Path) -> None:
    events = [
        _event(
            "trace",
            {
                "domain": "automation",
                "result": {"sequence": [{"result": {"success": False}}]},
            },
        ),
        _event(
            "trace",
            {
                "domain": "script",
                "result": {"sequence": [{"result": {"error": "boom"}}]},
            },
        ),
    ]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                observe(url, token="t", incident_dir=tmp_path, limit=2),
                timeout=3,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())

    lines = []
    for file in tmp_path.glob("incidents_*.jsonl"):
        lines.extend(json.loads(line) for line in file.read_text().splitlines())

    assert len(lines) == 2
    assert all(line["event_type"] == "trace" for line in lines)


def test_observe_logs_addon_error(tmp_path: Path) -> None:
    events = [
        _event(
            "supervisor_event",
            {
                "event": "addon",
                "data": {"level": "ERROR", "message": "addon crashed"},
            },
        ),
    ]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                observe(url, token="t", incident_dir=tmp_path, limit=1),
                timeout=3,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())

    lines = []
    for file in tmp_path.glob("incidents_*.jsonl"):
        lines.extend(json.loads(line) for line in file.read_text().splitlines())

    assert len(lines) == 1
    assert lines[0]["event_type"] == "supervisor_event"
