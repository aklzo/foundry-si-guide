"""Offline checks of the provider → MAF client wiring (no network: client
construction does not call the endpoint)."""

import pytest

pytest.importorskip("agent_framework_openai")

from agent_framework.openai import (  # noqa: E402
    OpenAIChatClient,
    OpenAIChatCompletionClient,
)

from agentic_search_maf.config import Config, LlmProviderKind  # noqa: E402
from agentic_search_maf.errors import ConfigError  # noqa: E402
from agentic_search_maf.llm import build_agents, build_chat_client  # noqa: E402


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        # OpenAI-compatible servers (Ollama, Anthropic's compat layer) only
        # implement Chat Completions; OpenAIChatClient is the Responses client.
        (LlmProviderKind.OLLAMA, OpenAIChatCompletionClient),
        (LlmProviderKind.CLAUDE, OpenAIChatCompletionClient),
        (LlmProviderKind.OPENAI, OpenAIChatClient),
    ],
)
def test_provider_selects_client_class(monkeypatch, provider, expected):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = build_chat_client(Config.from_env(provider).llm)
    assert type(client) is expected


def test_azure_with_key_uses_responses_client_on_v1_endpoint(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    config = Config.from_env(LlmProviderKind.AZURE)
    config.llm.model = "gpt-5.4-mini"
    client = build_chat_client(config.llm)
    assert type(client) is OpenAIChatClient
    assert str(client.client.base_url).endswith("/openai/v1/")


def test_azure_requires_endpoint(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    with pytest.raises(ConfigError):
        build_chat_client(Config.from_env(LlmProviderKind.AZURE).llm)


def test_structured_output_is_skipped_for_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = build_chat_client(Config.from_env(LlmProviderKind.CLAUDE).llm)
    agents = build_agents(client, "日本語", structured_output=False)
    assert "response_format" not in agents.planner.default_options


async def test_azure_route_does_not_forward_openai_org_headers(monkeypatch):
    """agent-framework-openai 1.15 で修正: Azure 経路に OpenAI の組織・プロジェクト
    ヘッダー(OPENAI_ORG_ID / OPENAI_PROJECT_ID 由来)を混ぜない。1.14.4 では
    両ヘッダーが Azure エンドポイントへ送られていた(2026-10-06 確認)。
    HTTP 層(openai 3.x の httpx2)を差し替え、実際に送られるヘッダーを検証する。"""
    import json

    import httpx2

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-key")
    monkeypatch.setenv("OPENAI_ORG_ID", "org-must-not-leak")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "proj-must-not-leak")
    sent: list[httpx2.Request] = []

    async def fake_send(self, request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        body = {
            "id": "resp_1",
            "object": "response",
            "created_at": 0,
            "status": "completed",
            "model": "gpt-5.4-mini",
            "output": [
                {
                    "type": "message",
                    "id": "msg_1",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({"queries": ["q"]}),
                            "annotations": [],
                        }
                    ],
                }
            ],
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
        }
        return httpx2.Response(200, json=body)

    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", fake_send)
    config = Config.from_env(LlmProviderKind.AZURE)
    config.llm.model = "gpt-5.4-mini"
    agents = build_agents(build_chat_client(config.llm), "日本語")

    response = await agents.planner.run("plan")

    (request,) = sent
    assert request.url.path == "/openai/v1/responses"
    assert request.headers["api-key"] == "azure-key"
    assert "openai-organization" not in request.headers
    assert "openai-project" not in request.headers
    assert response.value.queries == ["q"]
