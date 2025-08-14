"""Utilities to build LLM prompts."""

from __future__ import annotations

import json

from .contracts import RcaResult


def build_rca_prompt(context: dict) -> str:
    """Return a prompt instructing the LLM to produce an :class:`RcaResult`.

    Parameters
    ----------
    context: dict
        Incident context gathered from Home Assistant.
    """

    schema = json.dumps(RcaResult.model_json_schema(), indent=2)
    ctx = json.dumps(context, indent=2)
    return (
        "You are a Home Assistant diagnostics agent. "
        "Analyze the incident and respond with JSON matching the schema below.\n\n"
        f"Schema:\n{schema}\n\n"
        f"Context:\n{ctx}\n"
    )


__all__ = ["build_rca_prompt"]

