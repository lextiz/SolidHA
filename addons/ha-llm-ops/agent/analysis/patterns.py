from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class PatternRecord:
    """Stored recurring incident pattern."""

    pattern: str
    occurrences: int
    last_occurred: str


class PatternStore:
    """Manage persistence of recurring incident patterns."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.records: list[PatternRecord] = []
        if path.exists():
            data = json.loads(path.read_text())
            self.records = [PatternRecord(**item) for item in data]

    def _save(self) -> None:
        data = [asdict(r) for r in self.records]
        self.path.write_text(json.dumps(data, indent=2))

    def match(self, text: str) -> PatternRecord | None:
        for record in self.records:
            try:
                if re.search(record.pattern, text, re.MULTILINE):
                    return record
            except re.error:
                continue
        return None

    def get(self, pattern: str) -> PatternRecord | None:
        for record in self.records:
            if record.pattern == pattern:
                return record
        return None

    def add(self, pattern: str, occurred: datetime) -> PatternRecord:
        existing = self.get(pattern)
        if existing:
            self.update(existing, occurred)
            return existing
        record = PatternRecord(
            pattern=pattern, occurrences=1, last_occurred=occurred.isoformat()
        )
        self.records.append(record)
        self._save()
        return record

    def update(self, record: PatternRecord, occurred: datetime) -> None:
        record.occurrences += 1
        record.last_occurred = occurred.isoformat()
        self._save()


def validate_pattern(pattern: str) -> bool:
    """Return ``True`` if ``pattern`` is neither too specific nor too generic."""

    text = pattern.strip()
    if len(text) < 5:
        return False
    if text in {".*", "^.*$", ".*error.*"}:
        return False
    if re.search(r"\d{4,}", text):
        return False
    try:
        re.compile(text)
    except re.error:
        return False
    return True


__all__ = ["PatternStore", "PatternRecord", "validate_pattern"]
