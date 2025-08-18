import json

import pytest
from agent.llm.mock import MockLLM
from agent.parse import ParseError, parse_result


def test_parse_valid() -> None:
    llm = MockLLM()
    text = llm.generate("prompt", timeout=1)
    result = parse_result(text)
    assert result.root_cause == "mock root cause"


def test_parse_invalid_json() -> None:
    with pytest.raises(ParseError):
        parse_result("not json")


def test_parse_invalid_schema() -> None:
    bad = json.dumps({"impact": "x"})
    with pytest.raises(ParseError):
        parse_result(bad)
