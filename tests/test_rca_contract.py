import json
from pathlib import Path

import pytest
from agent.contracts import RcaResult
from agent.contracts.rca import export_schema
from pydantic import ValidationError


def test_schema_matches_export() -> None:
    schema_path = Path("addons/ha-llm-ops/agent/contracts/rca_v1.json")
    exported = json.loads(schema_path.read_text())
    assert exported == RcaResult.model_json_schema()


@pytest.mark.parametrize(
    "payload,expect_valid",
    [
        (
            {
                "summary": "s",
                "root_cause": "r",
                "impact": "i",
                "confidence": 0.5,
                "risk": "low",
                "recurrence_pattern": "a.*",
            },
            True,
        ),
        ({"summary": "s", "root_cause": "r"}, False),
    ],
)
def test_vectors(payload: dict, expect_valid: bool) -> None:
    if expect_valid:
        RcaResult.model_validate(payload)
    else:
        with pytest.raises(ValidationError):
            RcaResult.model_validate(payload)


def test_export_schema(tmp_path: Path) -> None:
    out = export_schema(tmp_path / "rca.json")
    assert out.exists()
    # Ensure default path is also handled without writing
    export_schema()
