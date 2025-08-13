import subprocess
import tempfile
import time
from pathlib import Path

import requests


def _start_homeassistant() -> subprocess.Popen[str]:
    config_dir = tempfile.mkdtemp()
    Path(config_dir, "configuration.yaml").write_text("\n")
    proc = subprocess.Popen(
        [
            "python",
            "-m",
            "homeassistant",
            "--config",
            config_dir,
            "--skip-pip",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url = "http://127.0.0.1:8123"
    for _ in range(60):
        try:
            resp = requests.get(url, timeout=1)
            if resp.status_code in {200, 401, 404}:
                break
        except requests.RequestException:
            time.sleep(1)
    else:
        proc.terminate()
        proc.wait(timeout=10)
        raise RuntimeError("Home Assistant did not start in time")
    return proc


def test_homeassistant_runs_and_responds() -> None:
    proc = _start_homeassistant()
    try:
        resp = requests.get("http://127.0.0.1:8123", timeout=5)
        assert resp.status_code in {200, 401, 404}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
