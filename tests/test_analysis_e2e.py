import asyncio
import json
import time
from pathlib import Path
from typing import Any

import requests
import websockets

from agent.contracts import RcaResult
from agent.devux import start_http_server
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


def test_end_to_end_problem_flow(tmp_path: Path) -> None:
    events = [_event("trace", {"result": {"success": False}})]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                monitor(url, token="t", problem_dir=tmp_path, llm=MockLLM(), limit=1),
                timeout=3,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())

    files = list(tmp_path.glob("problems_*.jsonl"))
    assert len(files) == 1
    record = json.loads(files[0].read_text().splitlines()[0])
    RcaResult.model_validate(record["result"])

    server = start_http_server(tmp_path, port=0)
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        assert files[0].name in resp.text
        resp = requests.get(
            f"http://127.0.0.1:{port}/problems/{files[0].name}", timeout=5
        )
        served = json.loads(resp.text.splitlines()[0])
        assert served == record
    finally:
        server.shutdown()
