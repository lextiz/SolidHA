import asyncio
import json
from pathlib import Path
from typing import Any

import websockets

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
        await asyncio.sleep(0.1)

    server = await websockets.serve(handler, "localhost", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://localhost:{port}"


def test_monitor_analyzes_and_counts(tmp_path: Path) -> None:
    events = [
        _event("trace", {"result": {"success": False}}),
        _event("trace", {"result": {"success": False}}),
    ]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                monitor(url, token="t", problem_dir=tmp_path, llm=MockLLM(), limit=2),
                timeout=3,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())

    files = sorted(tmp_path.glob("problems_*.jsonl"))
    assert files
    lines = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert lines[0]["occurrence"] == 1 and "result" in lines[0]
    assert lines[1]["occurrence"] == 2 and "result" not in lines[1]
