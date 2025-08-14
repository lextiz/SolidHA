"""Integration test that talks to a real Home Assistant container."""

from __future__ import annotations

import shutil
import subprocess
import time

import pytest


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
    import requests

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
        # Wait for the onboarding endpoint to come up
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

        # Create the initial user and exchange the auth code for a token
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

        resp = requests.get(
            f"{base_url}/api/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        assert resp.json().get("message") == "API running."
    finally:
        subprocess.run(["docker", "stop", container_name], check=False)
