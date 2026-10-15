"""hosted 面の往復検証(実デプロイなし・2026-10-06 追加)。

``ResponsesHostServer``(agent-framework-foundry-hosting 1.0.0b261002 で BREAKING 再設計)に
hosted.py の実エージェントを載せ、ASGI のまま ``POST /responses`` を送る(コンテナの :8088 と
同じ入口)。モデルだけ ``ScriptedChatClient`` で台本化し、MAF の関数呼び出しループ・ツール・
ホスティング層は本物のまま回す。HN は MockTransport。

- 同期の呼び出し(playground / ``--invoke`` 相当): ツールの digest がモデルに渡り、応答本文になる
- **background の呼び出し(Routines の Responses API アクション相当)**: Routines は 2026-09-24 版の
  Learn で「Responses API アクションは background モード。30 秒のタイムアウトは受付まで」と
  明記された。ホスティング層が background を受け付けて即座に返し、後から完了することを固定する

ホスティング層は store=true の会話状態をローカルでは ``~/.agentserver`` に書くため、
``AGENTSERVER_STATE_ROOT`` を tmp_path に向ける。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

pytest.importorskip("agent_framework_foundry_hosting")

from agent_framework import (
    BaseChatClient,
    ChatMiddlewareLayer,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    FunctionInvocationLayer,
    Message,
    ResponseStream,
)
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.ai.agentserver.responses import InMemoryResponseProvider
from conftest import algolia_client

from hn_briefing_maf.hosted import build_hosted_briefing_agent

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


class ScriptedChatClient(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
    """1 回目はツール collect_ranked_stories を呼び、2 回目はツール結果の先頭行で答える。

    ホスティング層は要求の ``stream`` に関係なく内側のエージェントをストリーミングで回すため
    (b261002 で確認)、ストリーミングと非ストリーミングの両方に答える。
    """

    OTEL_PROVIDER_NAME = "scripted"
    STORES_BY_DEFAULT = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.calls: list[list[Message]] = []

    def _reply(self, messages) -> ChatResponse:
        self.calls.append(list(messages))
        tool_results = [
            content.result
            for message in messages
            for content in message.contents
            if content.type == "function_result"
        ]
        if not tool_results:
            call = Content.from_function_call(
                call_id="call-1", name="collect_ranked_stories", arguments=json.dumps({"top_n": 3})
            )
            return ChatResponse(messages=[Message("assistant", [call])])
        first_story = next(
            line for line in str(tool_results[-1]).splitlines() if line.startswith("1. ")
        )
        return ChatResponse(messages=[Message("assistant", [f"Top story: {first_story[3:]}"])])

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
        reply = self._reply(messages)
        if stream:

            async def updates():
                for message in reply.messages:
                    yield ChatResponseUpdate(role=message.role, contents=list(message.contents))

            return ResponseStream(updates(), finalizer=ChatResponse.from_updates)

        async def response() -> ChatResponse:
            return reply

        return response()


@pytest.fixture(autouse=True)
def _isolated_state_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTSERVER_STATE_ROOT", str(tmp_path / "agentserver"))


def make_host() -> tuple[ResponsesHostServer, ScriptedChatClient, httpx.AsyncClient]:
    chat = ScriptedChatClient()
    http, _ = algolia_client()
    host = ResponsesHostServer(
        build_hosted_briefing_agent(chat, http),
        response_store=InMemoryResponseProvider(),
        configure_observability=None,
    )
    return host, chat, http


def output_text(body: dict[str, Any]) -> str:
    return "".join(
        part.get("text", "")
        for item in body.get("output") or []
        if item.get("type") == "message"
        for part in item.get("content") or []
    )


async def test_hosted_server_answers_through_the_collect_tool() -> None:
    host, chat, http = make_host()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=host), base_url="http://agent"
        ) as client:
            response = await client.post(
                "/responses",
                json={"input": "Give me today's brief (top 3).", "stream": False, "store": True},
            )
    finally:
        await http.aclose()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert output_text(body) == (
        "Top story: Show HN: An open-source framework for reliable AI agent workflows"
    )
    # 関数呼び出しループが本物のまま回った: 2 回目のモデル呼び出しに digest(ツール結果)が渡る
    assert len(chat.calls) == 2
    item_types = [item["type"] for item in body["output"]]
    assert "function_call" in item_types and "function_call_output" in item_types


async def test_hosted_server_accepts_background_requests_like_routines() -> None:
    """Routines の Responses API アクションは background。受付は即時、完了は後から GET で見える。"""
    host, chat, http = make_host()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=host), base_url="http://agent"
        ) as client:
            accepted = await client.post(
                "/responses",
                json={
                    "input": "Give me today's brief (top 3).",
                    "background": True,
                    "store": True,
                    "stream": False,
                },
            )
            assert accepted.status_code == 200
            first = accepted.json()
            # 受付の応答は完了を待たない(Routines の 30 秒は「受付まで」)
            assert first["status"] in ("queued", "in_progress")

            body = first
            for _ in range(200):
                if body["status"] in ("completed", "failed", "incomplete", "cancelled"):
                    break
                await asyncio.sleep(0.01)
                body = (await client.get(f"/responses/{first['id']}")).json()
    finally:
        await http.aclose()

    assert body["status"] == "completed"
    assert output_text(body).startswith("Top story: Show HN")
    assert len(chat.calls) == 2
