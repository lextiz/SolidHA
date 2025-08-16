import json
import time
from pathlib import Path

import requests

from agent.analysis.llm.mock import MockLLM
from agent.analysis.runner import AnalysisRunner
from agent.analysis.types import RcaOutput
from agent.devux import start_http_server


def _make_incident(path: Path) -> None:
    path.write_text('{"time_fired":"2024-01-01T00:00:00+00:00"}\n', encoding="utf-8")


def test_end_to_end_analysis(tmp_path: Path) -> None:
    inc_dir = tmp_path / "inc"
    out_dir = tmp_path / "out"
    inc_dir.mkdir()
    out_dir.mkdir()
    _make_incident(inc_dir / "incidents_1.jsonl")

    runner = AnalysisRunner(
        inc_dir,
        out_dir,
        MockLLM(),
        rate_seconds=0,
        max_lines=5,
        max_bytes=1000,
    )

    server = start_http_server(inc_dir, analysis_dir=out_dir, host="127.0.0.1", port=0)
    try:
        time.sleep(0.1)
        runner.run_once()
        files = list(out_dir.glob("analyses_*.jsonl"))
        assert len(files) == 1
        record = json.loads(files[0].read_text().splitlines()[0])
        RcaOutput.model_validate(record["result"])
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/analyses", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == [files[0].name]
    finally:
        server.shutdown()
