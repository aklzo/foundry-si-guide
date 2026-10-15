"""方式 C のエージェント側(FoundryToolbox + 要求スコープのファクトリ)と、ホスティング層の判断の固定。

2026-10-06 追加。agent-framework-foundry-hosting 1.0.0b261002(プレリリース)を使うので
``toolbox`` extra が要る(``uv sync --all-extras``)。無ければ skip。

1. **呼び出し元文脈の転送**: ``FoundryToolbox`` は現在の要求の ``x-agent-foundry-call-id`` を
   toolbox へ転送し、toolbox のプロキシがそれで利用者を解決する。相手役のプロキシ
   (FastMCP・ステートレス JSON)が受け取ったヘッダーを記録し、
   - 要求スコープのファクトリ: 2 人の要求がそれぞれ自分の call ID で届く
   - エージェントを 1 つ作って使い回す: **2 人目の要求に 1 人目の call ID が付く**
     (MCP の送信タスクが接続時の contextvars を写し取るため。401 / 403 は出ない)
   を再現する。公式のトラブル表「別ユーザーの ID・権限で動く = 呼び出し元文脈の欠落・古さ」の実体
2. **方式 A / B のホスティング層を MAF に置き換えない理由**(README 設計判断 2 の 2026-10-06 注記):
   ファクトリは引数なしで、要求の ``x-client-*`` ヘッダーを読む公開の手段がない
"""

from __future__ import annotations

import inspect
import json
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Self

import httpx
import pytest

pytest.importorskip("agent_framework_foundry_hosting")

from agent_framework_foundry_hosting import HostedResponseRequest, ResponsesHostServer
from azure.ai.agentserver.core import FoundryAgentRequestContext
from azure.ai.agentserver.responses import InMemoryResponseProvider
from azure.core.credentials import AccessToken
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from delegated_access_maf.agent.toolbox import (
    TOOLBOX_TOOL_NAME,
    build_toolbox_agent_factory,
    toolbox_tool_names,
)
from tests.caller_fakes import (
    ModelCall,
    ScriptedChatClient,
    last_tool_result,
    text_reply,
    tool_call_reply,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

TOOLBOX_URL = "https://acct.services.ai.azure.com/api/projects/p/toolboxes/dah/mcp?api-version=v1"
SEARCH_TOOL = "docs.search_documents"


class AgentCredential:
    """エージェント自身の ID(toolbox の入口だけに使う。利用者のトークンではない)。"""

    def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        assert scopes == ("https://ai.azure.com/.default",)
        return AccessToken("agent-identity-token", 4_102_444_800)


@dataclass
class FakeToolboxProxy:
    """toolbox のコンシューマーエンドポイントの相手役。受け取ったヘッダーを記録し、
    call ID から利用者を解決したつもりで、検索結果に「誰として呼ばれたか」を返す。"""

    callers: dict[str, str]  # call ID → 利用者
    seen: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._server = FastMCP(
            "toolbox",
            stateless_http=True,
            json_response=True,
            streamable_http_path="/api/projects/p/toolboxes/dah/mcp",
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        )
        proxy = self

        @self._server.tool(name=SEARCH_TOOL)
        def search_documents(query: str, ctx: Context) -> str:
            call_id = ctx.request_context.request.headers.get("x-agent-foundry-call-id", "")
            return json.dumps({"caller": proxy.callers.get(call_id, "unknown"), "query": query})

        self._app = self._server.streamable_http_app()
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        await self._stack.enter_async_context(self._server.session_manager.run())
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._stack.aclose()

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            self.seen.append(headers)
        await self._app(scope, receive, send)


@pytest.fixture(autouse=True)
def _isolated_state_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTSERVER_STATE_ROOT", str(tmp_path / "agentserver"))


@pytest.fixture
def route_toolbox_to(monkeypatch):
    """FoundryToolbox は自分で httpx.AsyncClient を作るので、transport 未指定の生成だけ相手役へ向ける。"""

    def install(app) -> None:
        original = httpx.AsyncClient

        class Routed(original):  # type: ignore[misc, valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs.setdefault("transport", httpx.ASGITransport(app=app))
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", Routed)

    return install


def search_then_report_caller(index: int, call: ModelCall):
    """要求ごとに: ツール結果がまだ無ければ検索を呼び、あれば「誰として呼ばれたか」を答える。"""
    if not last_tool_result(call):
        return tool_call_reply((SEARCH_TOOL, {"query": "締め日"}))
    return text_reply(f"検索した利用者: {json.loads(last_tool_result(call))['caller']}")


async def ask(host, call_id: str, user_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=host), base_url="http://agent"
    ) as client:
        response = await client.post(
            "/responses",
            json={"input": "経費精算の締め日は?", "stream": False, "store": True},
            # プロトコル 2.0.0 でプラットフォームが付けるヘッダー(テストが代わりに付ける)
            headers={"x-agent-foundry-call-id": call_id, "x-agent-user-id": user_id},
        )
    assert response.status_code == 200
    return response.json()


def output_text(body: dict[str, Any]) -> str:
    return "".join(
        part.get("text", "")
        for item in body.get("output") or []
        if item.get("type") == "message"
        for part in item.get("content") or []
    )


def make_factory(chat: ScriptedChatClient):
    return build_toolbox_agent_factory(chat, credential=AgentCredential(), toolbox_url=TOOLBOX_URL)


# --- 1. 呼び出し元文脈の転送 -----------------------------------------------------------------


async def test_request_scoped_factory_forwards_each_callers_call_id(route_toolbox_to) -> None:
    proxy = FakeToolboxProxy(callers={"call-employee": "employee", "call-finance": "finance"})
    route_toolbox_to(proxy)
    chat = ScriptedChatClient(search_then_report_caller)
    host = ResponsesHostServer(
        make_factory(chat), response_store=InMemoryResponseProvider(), configure_observability=None
    )

    async with proxy:
        first = await ask(host, "call-employee", "user-employee")
        seen_first = len(proxy.seen)
        second = await ask(host, "call-finance", "user-finance")

    assert output_text(first) == "検索した利用者: employee"
    assert output_text(second) == "検索した利用者: finance"
    first_calls = {h.get("x-agent-foundry-call-id") for h in proxy.seen[:seen_first]}
    second_calls = {h.get("x-agent-foundry-call-id") for h in proxy.seen[seen_first:]}
    assert first_calls == {"call-employee"} and second_calls == {"call-finance"}
    for headers in proxy.seen:
        # 入口はエージェント自身の ID。利用者のトークンも x-agent-user-id も送らない
        assert headers["authorization"] == "Bearer agent-identity-token"
        assert "x-agent-user-id" not in headers
        # Toolboxes は GA(GA 一覧表)だが、SDK はプレビューのフィーチャーヘッダーを必ず付ける
        assert "Toolboxes=V1Preview" in headers["foundry-features"]


async def test_shared_agent_instance_leaks_the_first_callers_context(route_toolbox_to) -> None:
    """アンチパターンの再現: エージェント(と toolbox の接続)を 1 つ作って使い回す。"""
    proxy = FakeToolboxProxy(callers={"call-employee": "employee", "call-finance": "finance"})
    route_toolbox_to(proxy)
    chat = ScriptedChatClient(search_then_report_caller)
    shared_agent = make_factory(chat)()
    host = ResponsesHostServer(
        shared_agent, response_store=InMemoryResponseProvider(), configure_observability=None
    )

    async with proxy:
        first = await ask(host, "call-employee", "user-employee")
        seen_first = len(proxy.seen)
        second = await ask(host, "call-finance", "user-finance")
        await host._cleanup_agent()  # 共有した接続を閉じる(サーバー停止時の処理)

    assert output_text(first) == "検索した利用者: employee"
    # 2 人目(経理担当)の要求なのに、1 人目(一般社員)の call ID で toolbox を呼んでいる
    assert output_text(second) == "検索した利用者: employee"
    assert {h.get("x-agent-foundry-call-id") for h in proxy.seen[seen_first:]} == {"call-employee"}


def test_factory_exposes_only_the_contract_tools_with_server_label_prefix() -> None:
    created: list[dict[str, Any]] = []

    class RecordingToolbox:
        def __init__(self, credential, **kwargs: Any) -> None:
            created.append(kwargs)

    factory = build_toolbox_agent_factory(
        ScriptedChatClient([]),
        credential=AgentCredential(),
        toolbox_url=TOOLBOX_URL,
        toolbox_cls=RecordingToolbox,
    )
    factory()
    factory()
    assert len(created) == 2  # 呼ぶたびに新しい toolbox(要求ごとに接続し直す)
    assert created[0]["url"] == TOOLBOX_URL
    assert created[0]["name"] == TOOLBOX_TOOL_NAME
    assert created[0]["allowed_tools"] == toolbox_tool_names() == [
        "docs.search_documents",
        "suppliers.list_suppliers",
        "suppliers.get_supplier",
        "supplier-admin.update_payment_terms",
    ]
    assert created[0]["approval_mode"] == "never_require"


# --- 2. 方式 A / B のホスティング層を MAF に置き換えない理由 -----------------------------------


def test_maf_hosting_cannot_hand_client_headers_to_a_request_scoped_factory() -> None:
    """b261002 の要求スコープのファクトリは引数なし。要求の文脈として公開されているのは
    プラットフォームの ID 3 つだけで、``x-client-*``(委任トークン)には届かない。"""
    with pytest.raises(TypeError, match="no arguments"):
        ResponsesHostServer(lambda request: None, configure_observability=None)
    assert FoundryAgentRequestContext.__slots__ == ("call_id", "user_id", "session_id")
    # prepare_options フックに渡る要求オブジェクトにもヘッダーの公開アクセサはない
    # (ResponseContext は非公開属性 _context に入っている)
    public = {name for name in dir(HostedResponseRequest) if not name.startswith("_")}
    assert not {name for name in public if "header" in name}
    assert "client_headers" not in inspect.signature(HostedResponseRequest.__init__).parameters
