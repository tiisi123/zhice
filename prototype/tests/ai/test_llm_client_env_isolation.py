from __future__ import annotations

import importlib


def _reload_llm_client(monkeypatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.delenv("PREFERRED_AI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ZHICE_AI_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ZHICE_AI_ANTHROPIC_API_KEY", raising=False)

    from apps.api import config as config_module

    importlib.reload(config_module)

    from apps.ai.agents import llm_client

    llm_module = importlib.reload(llm_client)
    llm_module.settings.preferred_ai_api_key = ""
    llm_module.settings.deepseek_api_key = ""
    llm_module.settings.zhice_ai_openai_api_key = ""
    llm_module.settings.zhice_ai_anthropic_api_key = ""
    return llm_module


def test_generic_openai_api_key_is_ignored(monkeypatch):
    """IDE/agent OPENAI_API_KEY must not be consumed by the product LLM client."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ide-key-that-product-must-ignore")
    llm_module = _reload_llm_client(monkeypatch)
    client = llm_module.LLMClient()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("generic OPENAI_API_KEY should not trigger OpenAI calls")

    monkeypatch.setattr(client, "_call_openai", fail_if_called)

    response = client.chat("你好")

    assert "模拟回复模式" in response


def test_product_scoped_openai_key_is_used(monkeypatch):
    """Product AI calls use ZHICE_AI_OPENAI_API_KEY when explicitly configured."""
    llm_module = _reload_llm_client(monkeypatch)
    llm_module.settings.zhice_ai_openai_api_key = "sk-product-key"
    client = llm_module.LLMClient()
    calls: list[tuple[str, str]] = []

    def fake_call(prompt: str, model: str) -> str:
        calls.append((prompt, model))
        return "ok"

    monkeypatch.setattr(client, "_call_openai", fake_call)

    assert client.chat("hello", model="gpt-test") == "ok"
    assert calls == [("hello", "gpt-test")]
