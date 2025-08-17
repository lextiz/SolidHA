from pathlib import Path

from agent.prompt import build_rca_prompt


def test_build_rca_prompt_snapshot() -> None:
    context = {"events": [{"event_type": "system_log_event", "message": "boom"}]}
    prompt = build_rca_prompt(context)
    snapshot = Path("tests/snapshots/rca_prompt.txt").read_text()
    assert prompt == snapshot
