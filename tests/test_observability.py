import asyncio
import json
from pathlib import Path

import pytest
import websockets

from agent.observability import _authenticate, observe


def _event(event_type: str, data: dict) -> dict:
    return {"type": "event", "event": {"event_type": event_type, "data": data}}


async def _serve(events: list[dict]) -> str:
    async def handler(ws):
        await ws.send(json.dumps({"type": "auth_required"}))
        await ws.recv()  # auth
        await ws.send(json.dumps({"type": "auth_ok"}))
        await ws.recv()  # subscribe
        for evt in events:
            await ws.send(json.dumps(evt))
        await asyncio.sleep(0.1)

    server = await websockets.serve(handler, "localhost", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://localhost:{port}"


async def _serve_header_auth() -> str:
    """Server that requires header-based authentication and forces a retry."""

    call_count = 0

    async def handler(ws):
        nonlocal call_count
        call_count += 1
        # Ensure we received the Authorization header
        headers = getattr(ws, "request_headers", None)
        if headers is None:  # websockets >=15
            headers = ws.request.headers
        assert headers["Authorization"] == "Bearer t"
        await ws.send(json.dumps({"type": "auth_required"}))

        msg = json.loads(await ws.recv())
        if call_count == 1:
            # Token-based attempt should trigger reconnect
            assert msg == {"type": "auth", "access_token": "t"}
            await ws.close()
            return

        # Second connection uses header auth
        assert msg == {"type": "auth"}
        await ws.send(json.dumps({"type": "auth_invalid"}))
        msg = json.loads(await ws.recv())
        assert msg == {"type": "auth", "access_token": "t"}
        await ws.send(json.dumps({"type": "auth_ok"}))
        await ws.recv()  # subscribe
        await ws.close()

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


def test_observe_writes_redacted_events(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets.yaml"
    secrets.write_text("api_key: supersecret\npassword: hidden\n")

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
                    secrets_path=secrets,
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
    for line in lines:
        dumped = json.dumps(line)
        assert "supersecret" not in dumped
        assert "hidden" not in dumped
        assert "ZZZZYYYY" not in dumped
        assert "[redacted]" in dumped


def test_observe_falls_back_to_header_auth(tmp_path: Path) -> None:
    """Ensure observer reconnects and retries with header auth."""

    async def run_test() -> None:
        server, url = await _serve_header_auth()
        try:
            await asyncio.wait_for(
                observe(
                    url,
                    token="t",
                    incident_dir=tmp_path,
                    limit=0,
                    secrets_path=tmp_path / "secrets.yaml",
                ),
                timeout=1,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())


def test_auth_failure_includes_details(tmp_path: Path) -> None:
    async def run_test() -> None:
        server, url = await _serve_auth_failure()
        try:
            async with websockets.connect(url, subprotocols=["homeassistant"]) as ws:
                with pytest.raises(RuntimeError) as ctx:
                    await _authenticate(ws, "t")
                detail = ctx.value.args[0].split(": ", 1)[1]
                data = json.loads(detail)
                assert data[-1]["type"] == "auth_invalid"
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())
