import importlib.util
import json
import time
from pathlib import Path
from types import ModuleType

import pytest
import requests


def _load_addon_devux() -> ModuleType:
    path = Path(__file__).resolve().parent.parent / "addons/ha-llm-ops/agent/devux.py"
    spec = importlib.util.spec_from_file_location("addon_devux", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["core", "addon"])
def devux(request: pytest.FixtureRequest) -> ModuleType:
    if request.param == "core":
        import agent.devux as module

        return module
    return _load_addon_devux()


def test_http_lists_incident_files(devux: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "incidents_1.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "incidents_2.jsonl").write_text("{}\n", encoding="utf-8")
    server = devux.start_http_server(tmp_path, host="127.0.0.1", port=0)
    try:
        # Allow server thread to start
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/incidents", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == ["incidents_1.jsonl", "incidents_2.jsonl"]
    finally:
        server.shutdown()


def test_http_root_page(devux: ModuleType, tmp_path: Path) -> None:
    inc = tmp_path / "incidents_1.jsonl"
    inc.write_text("{\"time_fired\":\"2024-01-01T00:00:00+00:00\"}\n", encoding="utf-8")
    ana_record = {
        "incident": str(inc),
        "result": {
            "summary": "summary",
            "root_cause": "rc",
            "impact": "system broken",
            "confidence": 0.5,
            "risk": "low",
            "recurrence_pattern": "pattern",
        },
        "event": {"event_type": "trigger"},
    }
    (tmp_path / "analyses_1.jsonl").write_text(json.dumps(ana_record), encoding="utf-8")
    server = devux.start_http_server(
        tmp_path, analysis_dir=tmp_path, host="127.0.0.1", port=0
    )
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        assert resp.status_code == 200
        assert "summary" in resp.text
        assert 'href="details/incidents_1.jsonl"' in resp.text
    finally:
        server.shutdown()


def test_http_details_page(devux: ModuleType, tmp_path: Path) -> None:
    inc = tmp_path / "incidents_1.jsonl"
    inc.write_text("{\"time_fired\":\"2024-01-01T00:00:00+00:00\"}\n", encoding="utf-8")
    ana_record = {
        "incident": str(inc),
        "result": {
            "summary": "summary",
            "root_cause": "rc",
            "impact": "system broken",
            "confidence": 0.5,
            "risk": "low",
            "candidate_actions": [{"action": "act", "rationale": "why"}],
            "tests": ["check"],
            "recurrence_pattern": "pattern",
        },
        "event": {"event_type": "trigger"},
    }
    (tmp_path / "analyses_1.jsonl").write_text(json.dumps(ana_record), encoding="utf-8")
    server = devux.start_http_server(
        tmp_path, analysis_dir=tmp_path, host="127.0.0.1", port=0
    )
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(
            f"http://127.0.0.1:{port}/details/incidents_1.jsonl", timeout=5
        )
        assert resp.status_code == 200
        assert "summary" in resp.text
        assert "system broken" in resp.text
        assert "Occurrences: 1" in resp.text
        assert "Candidate Actions" in resp.text
        assert "why" in resp.text
        assert "time_fired" in resp.text
        assert "trigger" in resp.text
    finally:
        server.shutdown()


def test_http_lists_analysis_files(devux: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "analyses_1.jsonl").write_text("{}\n", encoding="utf-8")
    server = devux.start_http_server(
        tmp_path,
        analysis_dir=tmp_path,
        host="127.0.0.1",
        port=0,
    )
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/analyses", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == ["analyses_1.jsonl"]
    finally:
        server.shutdown()


def test_http_analyses_empty(devux: ModuleType, tmp_path: Path) -> None:
    server = devux.start_http_server(
        tmp_path,
        analysis_dir=tmp_path,
        host="127.0.0.1",
        port=0,
    )
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/analyses", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        server.shutdown()


def test_http_analyses_404(devux: ModuleType, tmp_path: Path) -> None:
    server = devux.start_http_server(tmp_path, host="127.0.0.1", port=0)
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(f"http://127.0.0.1:{port}/analyses", timeout=5)
        assert resp.status_code == 404
    finally:
        server.shutdown()


def test_http_get_incident_file(devux: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "incidents_1.jsonl").write_text("{}", encoding="utf-8")
    server = devux.start_http_server(tmp_path, host="127.0.0.1", port=0)
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(
            f"http://127.0.0.1:{port}/incidents/incidents_1.jsonl", timeout=5
        )
        assert resp.status_code == 200
        assert resp.text == "{}"
    finally:
        server.shutdown()


def test_http_get_incident_file_404(devux: ModuleType, tmp_path: Path) -> None:
    server = devux.start_http_server(tmp_path, host="127.0.0.1", port=0)
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(
            f"http://127.0.0.1:{port}/incidents/missing.jsonl", timeout=5
        )
        assert resp.status_code == 404
    finally:
        server.shutdown()


def test_http_get_analysis_file(devux: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "analyses_1.jsonl").write_text("{}", encoding="utf-8")
    server = devux.start_http_server(
        tmp_path, analysis_dir=tmp_path, host="127.0.0.1", port=0
    )
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(
            f"http://127.0.0.1:{port}/analyses/analyses_1.jsonl", timeout=5
        )
        assert resp.status_code == 200
        assert resp.text == "{}"
    finally:
        server.shutdown()


def test_http_get_analysis_file_404(devux: ModuleType, tmp_path: Path) -> None:
    server = devux.start_http_server(
        tmp_path, analysis_dir=tmp_path, host="127.0.0.1", port=0
    )
    try:
        time.sleep(0.1)
        port = server.server_address[1]
        resp = requests.get(
            f"http://127.0.0.1:{port}/analyses/missing.jsonl", timeout=5
        )
        assert resp.status_code == 404
    finally:
        server.shutdown()
