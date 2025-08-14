import asyncio
import json
from pathlib import Path

import websockets

from agent.observability import observe


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


def test_observe_writes_redacted_events(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets.yaml"
    secrets.write_text("api_key: supersecret\npassword: hidden\n")

    events = [
        _event(
            "system_log_event",
            {
                "message": "token ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
                "api_key": "supersecret",
            },
        ),
        _event(
            "trace",
            {"details": "something secret", "password": "hidden"},
        ),
        _event(
            "system_log_event",
            {
                "message": "another token ZZZZYYYYXXXXWWWWVVVVUUUUTTTT",
                "api_key": "supersecret",
            },
        ),
    ]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await observe(
                url,
                token="t",
                incident_dir=tmp_path,
                max_bytes=120,
                limit=3,
                secrets_path=secrets,
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
    for line in lines:
        dumped = json.dumps(line)
        assert "supersecret" not in dumped
        assert "hidden" not in dumped
        assert "[redacted]" in dumped
