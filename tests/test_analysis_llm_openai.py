import pytest

from agent.analysis.llm import openai


def test_openai_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        openai.OpenAI()


def test_openai_generate(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "token")

    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )

        class Resp:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return {"output": [{"content": [{"text": "{}"}]}]}

        return Resp()

    monkeypatch.setattr(openai.requests, "post", fake_post)

    llm = openai.OpenAI()
    result = llm.generate("prompt", timeout=2.5)

    assert result == "{}"
    assert captured["timeout"] == 2.5
    assert captured["headers"]["Authorization"] == "Bearer token"
    assert "OpenAI-Project" not in captured["headers"]
    assert captured["json"]["model"] == "gpt-5"
    messages = captured["json"]["input"]
    assert messages[0]["content"][0]["text"] == openai._SYSTEM_PROMPT
    assert messages[1]["content"][0]["text"] == "prompt"


def test_openai_generate_with_project(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "token")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "proj")

    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )

        class Resp:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return {"output": [{"content": [{"text": "{}"}]}]}

        return Resp()

    monkeypatch.setattr(openai.requests, "post", fake_post)

    llm = openai.OpenAI()
    llm.generate("prompt", timeout=1.0)

    assert captured["headers"]["OpenAI-Project"] == "proj"


def test_openai_generate_with_project_arg(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "token")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "ignored")

    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )

        class Resp:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return {"output": [{"content": [{"text": "{}"}]}]}

        return Resp()

    monkeypatch.setattr(openai.requests, "post", fake_post)

    llm = openai.OpenAI(project_id="param")
    llm.generate("prompt", timeout=1.0)

    assert captured["headers"]["OpenAI-Project"] == "param"
