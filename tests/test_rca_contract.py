import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.contracts import RcaResult


def test_schema_matches_export() -> None:
    schema_path = Path("agent/contracts/rca_v1.json")
    exported = json.loads(schema_path.read_text())
    assert exported == RcaResult.model_json_schema()


@pytest.mark.parametrize(
    "sample_path,expect_valid",
    [
        ("tests/golden/rca_valid.json", True),
        ("tests/golden/rca_invalid.json", False),
    ],
)
def test_vectors(sample_path: str, expect_valid: bool) -> None:
    data = json.loads(Path(sample_path).read_text())
    if expect_valid:
        RcaResult.model_validate(data)
    else:
        with pytest.raises(ValidationError):
            RcaResult.model_validate(data)

