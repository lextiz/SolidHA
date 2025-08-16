import json
from pathlib import Path

from agent.executor.contracts import (
    ActionExecution,
    ActionProposal,
    ExecutionResult,
)


def test_schema_matches_export() -> None:
    base = Path("agent/executor")
    cases = [
        (ActionProposal, "action_proposal_v1.json"),
        (ActionExecution, "action_execution_v1.json"),
        (ExecutionResult, "execution_result_v1.json"),
    ]
    for model, name in cases:
        exported = json.loads((base / name).read_text())
        assert exported == model.model_json_schema()


def test_roundtrip() -> None:
    proposal = ActionProposal(action_id="restart", params={"id": 1})
    execution = ActionExecution(proposal=proposal, dry_run=True)
    result = ExecutionResult(
        action_id="restart", success=True, detail="ok", snapshot_id="1"
    )

    for model, instance in [
        (ActionProposal, proposal),
        (ActionExecution, execution),
        (ExecutionResult, result),
    ]:
        data = json.loads(instance.model_dump_json())
        model.model_validate(data)
