"""Utilities for redacting sensitive information from Home Assistant events."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SECRET_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "password",
    "api_key",
    "authorization",
    "client_secret",
}

TOKEN_PATTERNS = [re.compile(r"[A-Za-z0-9_-]{32,}")]


def load_secret_keys(path: Path) -> set[str]:
    """Load secret keys from a ``secrets.yaml`` file."""
    try:
        data = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        return set()
    if not isinstance(data, dict):  # pragma: no cover - defensive
        return set()
    return {str(k) for k in data.keys()}


def _redact_str(value: str) -> str:
    redacted = value
    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub("[redacted]", redacted)
    return redacted


def redact(data: Any, secret_keys: Iterable[str]) -> Any:
    """Recursively redact secrets from ``data``."""
    secrets = set(DEFAULT_SECRET_KEYS).union(set(secret_keys))
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            if key in secrets:
                result[key] = "[redacted]"
            else:
                result[key] = redact(value, secrets)
        return result
    if isinstance(data, list):
        return [redact(item, secrets) for item in data]
    if isinstance(data, str):
        return _redact_str(data)
    return data
