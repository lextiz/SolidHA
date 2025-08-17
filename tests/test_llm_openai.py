from typing import Any

import pytest

from agent.llm.openai import OpenAI


class DummyResponse:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def json(self) -> dict[str, Any]:
        return self.payload

    def raise_for_status(self) -> None:  # pragma: no cover - no failure path
        pass


def test_generate_uses_output_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> DummyResponse:
        assert headers["Authorization"] == "Bearer key"
        assert json["input"][1]["content"][0]["text"] == "hi"
        return DummyResponse({"output_text": "result"})

    monkeypatch.setattr("agent.llm.openai.requests.post", fake_post)
    llm = OpenAI(api_key="key")
    out = llm.generate("hi", timeout=1)
    assert out == "result"


def test_generate_falls_back_to_message(monkeypatch: pytest.MonkeyPatch) -> None:
    data = {
        "output": [
            {"type": "message", "content": [{"text": "fallback"}]}
        ]
    }

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> DummyResponse:
        return DummyResponse(data)

    monkeypatch.setattr("agent.llm.openai.requests.post", fake_post)
    llm = OpenAI(api_key="key")
    assert llm.generate("hi", timeout=1) == "fallback"


def test_generate_requires_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> DummyResponse:
        return DummyResponse({})

    monkeypatch.setattr("agent.llm.openai.requests.post", fake_post)
    llm = OpenAI(api_key="key")
    with pytest.raises(RuntimeError):
        llm.generate("hi", timeout=1)


def test_openai_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        OpenAI()


def test_openai_uses_open_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPEN_API_KEY", "k")
    llm = OpenAI()
    assert llm.api_key == "k"


def test_generate_includes_project_header(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> DummyResponse:
        assert headers["OpenAI-Project"] == "proj"
        return DummyResponse({"output_text": "ok"})

    monkeypatch.setattr("agent.llm.openai.requests.post", fake_post)
    llm = OpenAI(api_key="key", project_id="proj")
    assert llm.generate("hi", timeout=1) == "ok"
