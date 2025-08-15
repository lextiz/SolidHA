import json
from datetime import datetime
from pathlib import Path

from agent.analysis.prompt_builder import build_prompt
from agent.analysis.types import ContextBundle, IncidentRef


def test_prompt_builder_golden() -> None:
    data = json.loads(Path("tests/golden/prompt_input.json").read_text())
    inc = data["incident"]
    bundle = ContextBundle(
        incident=IncidentRef(
            path=Path(inc["path"]),
            start=datetime.fromisoformat(inc["start"]),
            end=datetime.fromisoformat(inc["end"]),
        ),
        events=data["events"],
    )
    prompt = build_prompt(bundle)
    expected = Path("tests/golden/prompt_output.txt").read_text()
    assert prompt.text == expected
