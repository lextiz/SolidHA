from datetime import datetime
from pathlib import Path

from agent.analysis.types import ContextBundle, IncidentRef, Prompt, RcaOutput


def test_incident_ref_constructor() -> None:
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)
    ref = IncidentRef(Path("incidents_1.jsonl"), start, end)
    assert ref.path.name == "incidents_1.jsonl"
    assert ref.start == start
    assert ref.end == end


def test_context_bundle() -> None:
    ref = IncidentRef(Path("file"), datetime(2024, 1, 1), datetime(2024, 1, 1, 0, 1))
    bundle = ContextBundle(incident=ref, events=[{"event_type": "x"}])
    assert bundle.incident == ref
    assert bundle.events[0]["event_type"] == "x"


def test_prompt_and_rca_output_alias() -> None:
    prompt = Prompt(text="hello", schema={"type": "object"})
    assert "type" in prompt.schema
    assert RcaOutput.__name__ == "RcaResult"
