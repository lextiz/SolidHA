import asyncio
from pathlib import Path

import agent.__main__ as agent_main
from agent.analysis.llm.mock import MockLLM


def test_main_starts_runner(monkeypatch, tmp_path: Path) -> None:
    called = {"runner": False, "observe": False}

    class DummyRunner:
        def __init__(self, *a, **k):
            pass

        async def run_forever(self):
            called["runner"] = True
            await asyncio.sleep(0)

    async def fake_observe(*args, **kwargs):
        called["observe"] = True
        await asyncio.sleep(0)

    monkeypatch.setattr(agent_main, "AnalysisRunner", DummyRunner)
    monkeypatch.setattr(agent_main, "observe", fake_observe)
    monkeypatch.setattr(agent_main, "start_http_server", lambda *a, **k: None)
    monkeypatch.setattr(agent_main, "create_llm", lambda backend: MockLLM())

    monkeypatch.setenv("INCIDENT_DIR", str(tmp_path))
    monkeypatch.setenv("HA_WS_URL", "ws://test")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "t")

    agent_main.main()

    assert called["runner"]
    assert called["observe"]
