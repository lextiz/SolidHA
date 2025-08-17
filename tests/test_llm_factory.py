from typing import Any

from agent.llm import MockLLM, OpenAI, create_llm


def test_create_llm_uses_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert isinstance(create_llm(), OpenAI)


def test_create_llm_defaults_to_mock(monkeypatch: Any) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = create_llm()
    assert isinstance(llm, MockLLM)


def test_create_llm_explicit_backend(monkeypatch: Any) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(create_llm("mock"), MockLLM)
