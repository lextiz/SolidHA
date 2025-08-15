"""Build deterministic prompts for RCA analysis."""

from __future__ import annotations

import json
import tomllib
from importlib import metadata
from pathlib import Path
from typing import Any

from .types import ContextBundle, Prompt, RcaOutput

_GUARDRAILS = (
    "You are a Home Assistant diagnostics agent. "
    "Respond only with JSON matching the provided schema. "
    "Do not include explanations or commentary."
)


def _package_version() -> str:
    """Return the installed package version or ``0.0.0``."""

    try:
        return metadata.version("solidha-agent")
    except metadata.PackageNotFoundError:  # pragma: no cover - fallback for tests
        try:
            pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
            data = tomllib.loads(pyproject.read_text())
            return data["project"]["version"]
        except Exception:  # pragma: no cover - final fallback
            return "0.0.0"


def build_prompt(bundle: ContextBundle) -> Prompt:
    """Return a deterministic prompt for ``bundle``.

    The prompt text contains repository/version info, guardrails and the
    incident context. The JSON schema is returned separately to allow
    programmatic validation of LLM responses.
    """

    schema: dict[str, Any] = RcaOutput.model_json_schema()
    schema_text = json.dumps(schema, indent=2, sort_keys=True)

    incident_info = {
        "path": str(bundle.incident.path),
        "start": bundle.incident.start.isoformat(),
        "end": bundle.incident.end.isoformat(),
    }
    context = {"incident": incident_info, "events": bundle.events}
    context_text = json.dumps(context, indent=2, sort_keys=True)

    version = _package_version()
    header = f"SolidHA v{version}\n{_GUARDRAILS}\n\n"

    text = (
        f"{header}"
        f"Schema:\n{schema_text}\n\n"
        f"Context:\n{context_text}\n"
    )
    return Prompt(text=text, schema=schema)


__all__ = ["build_prompt"]
