import asyncio
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from agent.llm.mock import MockLLM
from agent.problems import monitor


def _docker_available() -> bool:
    """Return True if Docker CLI and daemon are available."""
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available")
def test_monitor_automation_failure(tmp_path: Path) -> None:
    """Ensure monitor logs an automation failure from a real HA container."""
    import requests

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "secrets.yaml").write_text("")
    (config_dir / "configuration.yaml").write_text(
        "system_log:\n  fire_event: true\nautomation: !include automations.yaml\n"
    )
    (config_dir / "automations.yaml").write_text(
        """
- id: fail_test
  alias: Fail Test
  trigger:
    - platform: time_pattern
      seconds: "/1"
  action:
    - service: nonexistent.does_not_exist
"""
    )

    container_name = "ha-observe-test"
    port = "8125"
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "-p",
            f"{port}:8123",
            "-v",
            f"{config_dir}:/config",
            "--name",
            container_name,
            "ghcr.io/home-assistant/home-assistant:stable",
        ],
        check=True,
    )
    base_url = f"http://localhost:{port}"
    ws_url = f"ws://localhost:{port}/api/websocket"
    try:
        for _ in range(300):
            try:
                resp = requests.get(f"{base_url}/api/onboarding", timeout=1)
                if resp.status_code == 200:
                    break
            except requests.ConnectionError:
                pass
            time.sleep(1)
        else:
            pytest.fail("Home Assistant API did not respond in time")

        client_id = "http://example"
        resp = requests.post(
            f"{base_url}/api/onboarding/users",
            json={
                "client_id": client_id,
                "name": "Test Name",
                "username": "test-user",
                "password": "test-pass",
                "language": "en",
            },
            timeout=10,
        )
        resp.raise_for_status()
        auth_code = resp.json()["auth_code"]

        resp = requests.post(
            f"{base_url}/auth/token",
            data={
                "client_id": client_id,
                "grant_type": "authorization_code",
                "code": auth_code,
            },
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]

        problem_dir = tmp_path / "problems"
        try:
            asyncio.run(
                asyncio.wait_for(
                    monitor(
                        ws_url,
                        token=token,
                        problem_dir=problem_dir,
                        llm=MockLLM(),
                        limit=3,
                        batch_seconds=0,
                    ),
                    timeout=60,
                )
            )
        except TimeoutError:
            pass

        files = list(problem_dir.glob("problems_*.jsonl"))
        assert files, "No problem files created"
        lines = [
            json.loads(line) for file in files for line in file.read_text().splitlines()
        ]
        assert any(
            "nonexistent.does_not_exist" in json.dumps(line) for line in lines
        ), lines
    finally:
        subprocess.run(["docker", "stop", container_name], check=False)
