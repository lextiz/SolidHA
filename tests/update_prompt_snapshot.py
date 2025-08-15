"""Utility to regenerate the prompt builder golden file."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent.analysis.prompt_builder import build_prompt
from agent.analysis.types import ContextBundle, IncidentRef


def main() -> None:  # pragma: no cover - manual utility
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
    Path("tests/golden/prompt_output.txt").write_text(prompt.text)


if __name__ == "__main__":
    main()
