"""Policy models and loading utilities for executor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from yaml import safe_load


class Policy(BaseModel):
    """Describe permissions and restrictions for a specific action."""

    action_id: str = Field(..., description="Identifier of the action")
    allowed: bool = Field(..., description="Whether the action is permitted")
    conditions: dict[str, Any] = Field(
        default_factory=dict, description="Additional conditions to satisfy"
    )
    cooldown_s: int | None = Field(
        default=None, ge=0, description="Cooldown period in seconds"
    )


def load_policies(path: Path) -> list[Policy]:
    """Load policies from ``policy.yaml`` located at ``path`` or its parent."""

    policy_path = path / "policy.yaml" if path.is_dir() else path
    try:
        raw = safe_load(policy_path.read_text()) or []
    except FileNotFoundError:
        return []
    if not isinstance(raw, list):
        raise ValueError("policy.yaml must contain a list of policies")
    return [Policy.model_validate(item) for item in raw]


__all__ = ["Policy", "load_policies"]
