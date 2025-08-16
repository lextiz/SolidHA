from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.executor.policy import load_policies


def test_load_policy_valid() -> None:
    policies = load_policies(Path("tests/golden/policy_valid.yaml"))
    assert len(policies) == 1
    p = policies[0]
    assert p.action_id == "restart_integration"
    assert p.allowed is True
    assert p.conditions == {"integration": "zha"}
    assert p.cooldown_s == 60


def test_load_policy_invalid() -> None:
    with pytest.raises(ValidationError):
        load_policies(Path("tests/golden/policy_invalid.yaml"))


def test_load_policy_non_list(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text("action: test\n")
    with pytest.raises(ValueError):
        load_policies(policy_file)
