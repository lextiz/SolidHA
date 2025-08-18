import json
from pathlib import Path

from agent.executor.contracts import (
    ActionExecution,
    ActionProposal,
    ExecutionResult,
    export_schemas,
)


def _normalize(schema: dict) -> dict:
    """Fill in implicit JSON Schema defaults for stable comparisons."""

    params = schema.get("properties", {}).get("params")
    if isinstance(params, dict) and "additionalProperties" not in params:
        params["additionalProperties"] = True
    return schema


def test_schema_matches_export() -> None:
    base = Path("addons/ha-llm-ops/agent/executor")
    cases = [
        (ActionProposal, "action_proposal_v1.json"),
        (ActionExecution, "action_execution_v1.json"),
        (ExecutionResult, "execution_result_v1.json"),
    ]
    for model, name in cases:
        exported = _normalize(json.loads((base / name).read_text()))
        assert exported == _normalize(model.model_json_schema())


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


def test_export_schemas(tmp_path: Path) -> None:
    paths = export_schemas(tmp_path)
    names = {p.name for p in paths}
    assert names == {
        "action_proposal_v1.json",
        "action_execution_v1.json",
        "execution_result_v1.json",
    }
    for path in paths:
        json.loads(path.read_text())


def test_export_schemas_default() -> None:
    paths = export_schemas()
    assert {p.name for p in paths} == {
        "action_proposal_v1.json",
        "action_execution_v1.json",
        "execution_result_v1.json",
    }
