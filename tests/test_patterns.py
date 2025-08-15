import json
from pathlib import Path

from agent.analysis.patterns import PatternStore, validate_pattern


def test_pattern_store_loads_existing_and_handles_bad_regex(tmp_path: Path) -> None:
    path = tmp_path / "patterns.json"
    data = [{"pattern": "(", "occurrences": 1, "last_occurred": "2024-01-01T00:00:00"}]
    path.write_text(json.dumps(data), encoding="utf-8")
    store = PatternStore(path)
    assert store.records[0].pattern == "("
    assert store.match("anything") is None


def test_validate_pattern_cases() -> None:
    assert not validate_pattern("abcd")  # too short
    assert not validate_pattern(".*")
    assert not validate_pattern("^.*$")
    assert not validate_pattern(".*error.*")
    assert not validate_pattern("error 1234")  # digits
    assert not validate_pattern("([abc")  # invalid regex
    assert validate_pattern("foo.*bar")
