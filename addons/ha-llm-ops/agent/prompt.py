"""Utilities to build LLM prompts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .contracts import RcaResult


def build_rca_prompt(
    context: Mapping[str, Any], *, max_lines: int | None = None
) -> str:
    """Return a prompt instructing the LLM to produce an :class:`RcaResult`.

    Parameters
    ----------
    context: Mapping[str, Any]
        Problem context gathered from Home Assistant.
    max_lines: int | None
        If provided, truncate the context JSON to at most ``max_lines``.
    """

    schema = json.dumps(RcaResult.model_json_schema(), indent=2)
    ctx = json.dumps(context, sort_keys=True, indent=2)
    if max_lines is not None:
        ctx = "\n".join(ctx.splitlines()[:max_lines])
    return (
        "You are a Home Assistant diagnostics agent. "
        "Analyze the problem and respond with JSON matching the schema below.\n\n"
        f"Schema:\n{schema}\n\n"
        f"Context:\n{ctx}\n"
    )


__all__ = ["build_rca_prompt"]
