from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.executor.policy import load_policies


def test_load_policy_valid(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(
        """
        - action_id: restart_integration
          allowed: true
          conditions:
            integration: zha
          cooldown_s: 60
        """
    )
    policies = load_policies(policy_file)
    assert len(policies) == 1
    p = policies[0]
    assert p.action_id == "restart_integration"
    assert p.allowed is True
    assert p.conditions == {"integration": "zha"}
    assert p.cooldown_s == 60


def test_load_policy_invalid(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(
        """
        - action_id: restart_integration
          allowed: maybe
        """
    )
    with pytest.raises(ValidationError):
        load_policies(policy_file)


def test_load_policy_non_list(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text("action: test\n")
    with pytest.raises(ValueError):
        load_policies(policy_file)


def test_load_policy_missing(tmp_path: Path) -> None:
    assert load_policies(tmp_path / "missing.yaml") == []
