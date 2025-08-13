"""Integration test that talks to a real Home Assistant container."""

from __future__ import annotations

import shutil
import subprocess
import time

import pytest
import requests


def _docker_available() -> bool:
    """Return True if Docker CLI and daemon are available."""
    if shutil.which("docker") is None:
        return False
    result = subprocess.run([
        "docker",
        "info",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return result.returncode == 0


@pytest.mark.integration
@pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available")
def test_home_assistant_container() -> None:
    """Start a Home Assistant container and verify the API responds."""
    container_name = "ha-test"
    port = "8123"
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "-p",
            f"{port}:{port}",
            "--name",
            container_name,
            "ghcr.io/home-assistant/home-assistant:stable",
        ],
        check=True,
    )
    base_url = f"http://localhost:{port}"
    try:
        resp: requests.Response | None = None
        for _ in range(180):
            try:
                resp = requests.get(f"{base_url}/api/", timeout=1)
                if resp.status_code in (200, 401):
                    break
            except requests.ConnectionError:
                pass
            time.sleep(1)
        else:
            pytest.fail("Home Assistant API did not respond in time")

        assert resp is not None
        if resp.status_code == 200:
            assert resp.json().get("message") == "API running."
        else:
            assert "Unauthorized" in resp.text
    finally:
        subprocess.run(["docker", "stop", container_name], check=False)
