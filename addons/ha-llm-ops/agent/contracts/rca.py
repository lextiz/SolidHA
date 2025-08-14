"""Root cause analysis contract and JSON schema."""

from __future__ import annotations

import json
from pathlib import Path

from typing import Annotated

from pydantic import BaseModel, Field


class CandidateAction(BaseModel):
    """A potential action to mitigate the incident."""

    action: str = Field(..., description="Short description of the action")
    rationale: str = Field(..., description="Why the action may help")


class RcaResult(BaseModel):
    """LLM-provided root cause analysis result."""

    root_cause: str = Field(..., description="Primary reason for the incident")
    impact: str = Field(..., description="Observed impact on the system")
    confidence: Annotated[
        float, Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    ]
    candidate_actions: list[CandidateAction] = Field(
        default_factory=list, description="Proposed remediation steps"
    )
    risk: str = Field(..., description="Overall risk assessment of acting")
    tests: list[str] = Field(
        default_factory=list,
        description="Checks to verify the issue is resolved",
    )


def export_schema(path: Path | None = None) -> Path:
    """Export the JSON schema to ``rca_v1.json`` and return its path."""

    schema = RcaResult.model_json_schema()
    if path is None:
        path = Path(__file__).with_name("rca_v1.json")
    content = json.dumps(schema, indent=2) + "\n"
    existing = path.read_text() if path.exists() else ""
    if existing != content:
        path.write_text(content)
    return path


if __name__ == "__main__":  # pragma: no cover - manual utility
    export_schema()

