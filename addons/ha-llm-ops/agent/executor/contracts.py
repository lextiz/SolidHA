"""Contracts for executor actions and results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ActionProposal(BaseModel):
    """LLM-provided proposal for an action."""

    action_id: str = Field(..., description="Identifier of the proposed action")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the action"
    )


class ActionExecution(BaseModel):
    """Request to execute a previously proposed action."""

    proposal: ActionProposal
    dry_run: bool = Field(False, description="Whether to simulate without applying")


class ExecutionResult(BaseModel):
    """Outcome of executing an action."""

    action_id: str = Field(..., description="Identifier of the executed action")
    success: bool = Field(..., description="Whether the action succeeded")
    detail: str | None = Field(None, description="Additional execution details")
    snapshot_id: str | None = Field(
        None, description="Snapshot ID used for backup before execution"
    )


def export_schemas(base_path: Path | None = None) -> list[Path]:
    """Export JSON schemas for executor contracts and return their paths."""

    if base_path is None:
        base_path = Path(__file__).resolve().parent
    models: list[tuple[type[BaseModel], str]] = [
        (ActionProposal, "action_proposal_v1.json"),
        (ActionExecution, "action_execution_v1.json"),
        (ExecutionResult, "execution_result_v1.json"),
    ]
    paths: list[Path] = []
    for model, name in models:
        schema = model.model_json_schema()
        path = base_path / name
        content = json.dumps(schema, indent=2) + "\n"
        existing = path.read_text() if path.exists() else ""
        if existing != content:
            path.write_text(content)
        paths.append(path)
    return paths


if __name__ == "__main__":  # pragma: no cover - manual utility
    export_schemas()


__all__ = [
    "ActionProposal",
    "ActionExecution",
    "ExecutionResult",
    "export_schemas",
]
