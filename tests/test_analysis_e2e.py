import asyncio
import copy
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
import websockets

from agent.contracts import RcaResult
from agent.devux import start_http_server
from agent.llm.mock import MockLLM
from agent.problems import monitor


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
    base_event = {
        "context": {
            "id": "01K2TCSVD6Y6367NV7ERZSCVE4",
            "parent_id": None,
            "user_id": None,
        },
        "data": {
            "entity_id": "sensor.wiz_rgbww_tunable_f8f860_power",
            "new_state": {
                "attributes": {
                    "device_class": "power",
                    "friendly_name": "WiZ RGBWW Tunable F8F860 Power",
                    "state_class": "measurement",
                    "unit_of_measurement": "W",
                },
                "context": {
                    "id": "01K2TCSVD6Y6367NV7ERZSCVE4",
                    "parent_id": None,
                    "user_id": None,
                },
                "entity_id": "sensor.wiz_rgbww_tunable_f8f860_power",
                "last_changed": "2025-08-16T21:33:05.830408+00:00",
                "last_reported": "2025-08-16T21:33:05.830408+00:00",
                "last_updated": "2025-08-16T21:33:05.830408+00:00",
                "state": "unavailable",
            },
            "old_state": {
                "attributes": {
                    "device_class": "power",
                    "friendly_name": "WiZ RGBWW Tunable F8F860 Power",
                    "state_class": "measurement",
                    "unit_of_measurement": "W",
                },
                "context": {
                    "id": "01K2TBD3KCDCGKQQAANBATWSD7",
                    "parent_id": None,
                    "user_id": None,
                },
                "entity_id": "sensor.wiz_rgbww_tunable_f8f860_power",
                "last_changed": "2025-08-16T21:08:39.660497+00:00",
                "last_reported": "2025-08-16T21:08:39.660497+00:00",
                "last_updated": "2025-08-16T21:08:39.660497+00:00",
                "state": "unknown",
            },
        },
        "event_type": "state_changed",
        "origin": "LOCAL",
        "time_fired": "2025-08-16T21:33:05.830408+00:00",
    }

    second_event = copy.deepcopy(base_event)
    second_event["context"]["id"] = "01K2TCSVD6Y6367NV7ERZSCVF5"
    second_event["time_fired"] = "2025-08-16T21:34:05.830408+00:00"
    second_event["data"]["new_state"]["context"]["id"] = (
        "01K2TCSVD6Y6367NV7ERZSCVF5"
    )
    second_event["data"]["new_state"]["last_changed"] = (
        "2025-08-16T21:34:05.830408+00:00"
    )
    second_event["data"]["new_state"]["last_reported"] = (
        "2025-08-16T21:34:05.830408+00:00"
    )
    second_event["data"]["new_state"]["last_updated"] = (
        "2025-08-16T21:34:05.830408+00:00"
    )

    class CountingLLM(MockLLM):
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, prompt: str, *, timeout: float) -> str:
            self.calls += 1
            resp = json.loads(super().generate(prompt, timeout=timeout))
            resp["recurrence_pattern"] = "wiz_rgbww_tunable_f8f860_power.*unavailable"
            return json.dumps(resp)

    key = os.getenv("OPENAI_API_KEY")
    llm = None if key else CountingLLM()
    events = [
        {"type": "event", "event": base_event},
        {"type": "event", "event": second_event},
    ]

    async def run_test() -> None:
        server, url = await _serve(events)
        try:
            await asyncio.wait_for(
                monitor(url, token="t", problem_dir=tmp_path, llm=llm, limit=2),
                timeout=360,
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_test())

    files = list(tmp_path.glob("problems_*.jsonl"))
    assert len(files) == 1
    lines = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert len(lines) == 2
    first, second = lines
    result = RcaResult.model_validate(first["result"])
    assert result.summary and result.root_cause and result.recurrence_pattern
    pattern = re.compile(result.recurrence_pattern)
    assert pattern.search(json.dumps(second_event, sort_keys=True))
    assert second["occurrence"] == 2 and "result" not in second
    if llm is not None:
        assert llm.calls == 1

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
        assert served == lines[0]
    finally:
        server.shutdown()
