"""方式 C(エージェント側の配線のみ・ライブ未検証): Foundry Toolbox の OAuth ID パススルー。

2026-10-06 に公式の推奨が「MCP などのユーザー委任は toolbox 経由。MAF の hosted agent では
``FoundryToolbox`` を使う」になった(Learn: tool-authentication / use-toolbox-hosted-agent /
concepts/hosted-agents)。方式 A / B との違いは**委任トークンの運び方**で、判定点(APIM か
MCP サーバーか)とは直交する:

- 方式 A / B: 中間層が OBO で取った委任トークンを ``x-client-tools-access-token`` でコンテナへ
  転送し、コンテナのコードが ``Authorization`` に載せて MCP を呼ぶ(トークンがコンテナに入る)
- 方式 C: コンテナはエージェント自身の ID(``https://ai.azure.com/.default``)で toolbox の
  コンシューマーエンドポイントに入るだけ。``FoundryToolbox`` が現在の要求の
  ``x-agent-foundry-call-id`` を転送し、toolbox のプロキシが呼び出し元(利用者)を解決して、
  接続(``oauth2``)に保存された利用者の委任トークンで MCP サーバーを呼ぶ。**利用者の
  トークンはコンテナに入らない**(中間層・OBO・``x-ms-user-identity`` のカスタムロールも要らない)

**FoundryToolbox は要求ごとに作る**(``ResponsesHostServer(agent=factory)`` の要求スコープの
ファクトリ — agent-framework-foundry-hosting 1.0.0b261002 の BREAKING 再設計で入った形)。
MCP の送信タスクは接続した時点の contextvars を写し取るので、エージェントを 1 つ作って
使い回すと、2 人目以降の要求に**最初の要求の call ID** が付く = 401 / 403 を出さずに別の
利用者の権限で動く(公式のトラブル表の「呼び出し元文脈の欠落・古さ」)。テスト
(``tests/test_agent_toolbox.py``)で両方を再現して固定した。

ここにあるのはエージェント側だけ。接続(``oauth2``)・toolbox の作成・Entra のリダイレクト
URI・利用者の同意・中間層を通さない CLI は未実装(README「方式 C の設計メモ」)。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from ..contracts import MCP_SERVERS, MSG_FORBIDDEN, McpServerSpec

AGENT_NAME = "delegated-access-toolbox-agent"

#: エージェントがローカルで持つツール名(MAF の MCP ツールの名前)
TOOLBOX_TOOL_NAME = "dah_toolbox"

TOOLBOX_INSTRUCTIONS = f"""\
あなたは社内アシスタントです。サインイン中の利用者の権限で、toolbox のツールを使って回答します。
ツール名は「<MCP サーバー名>.<ツール名>」(例: docs.search_documents)です。

守ること:
- 事実はツールの結果だけから答え、推測で補わない。文書を根拠にするときは文書のタイトルを示す。
- 検索結果に無い情報は「見つかりませんでした」と答える(閲覧権限のない文書は結果に出ない)。
- ツールが権限エラーを返したときは「{MSG_FORBIDDEN}」とだけ伝える。別のツールや別の手段で回避しない。
- 更新(supplier-admin.update_payment_terms)は、利用者が対象の取引先と値をはっきり指定したときだけ実行する。
- 認証情報やトークンを尋ねたり、出力したりしない。
- 回答は日本語で簡潔に。
"""


def toolbox_tool_names(servers: Sequence[McpServerSpec] = MCP_SERVERS) -> list[str]:
    """toolbox の ``tools/list`` に現れる名前(MCP は ``{server_label}.{tool_name}``)。

    toolbox の MCP ツールは ``server_label`` で名前空間が付く(Learn: toolbox.md の
    tools/list の確認表)。server_label は契約のサーバー名(docs / suppliers / supplier-admin)に
    揃える前提。MAF は MCP の名前の ``.`` を残す(``_normalize_mcp_name``)ので、
    ドット入りの関数名をモデル API が受け付けるかはライブで確かめる。
    """
    return [f"{spec.name}.{tool}" for spec in servers for tool in spec.tools]


def build_toolbox_agent_factory(
    chat_client: Any,
    *,
    credential: Any,
    toolbox_url: str,
    instructions: str = TOOLBOX_INSTRUCTIONS,
    toolbox_cls: Callable[..., Any] | None = None,
    timeout: float = 120.0,
) -> Callable[[], Any]:
    """``ResponsesHostServer(agent=...)`` に渡す要求スコープのファクトリ(引数なし)。

    要求ごとに ``FoundryToolbox`` と ``Agent`` を新しく作る。共有するのはモデル用の
    ``chat_client`` と、toolbox の入口に使うエージェント自身の ``credential`` だけ。
    ``toolbox_url`` はコンシューマーエンドポイント
    (``{project}/toolboxes/{name}/mcp?api-version=v1`` = 既定版に追従)。
    """
    if toolbox_cls is None:
        from agent_framework_foundry_hosting import FoundryToolbox

        toolbox_cls = FoundryToolbox
    allowed = toolbox_tool_names()

    def create_agent() -> Any:
        from agent_framework import Agent

        toolbox = toolbox_cls(
            credential,
            url=toolbox_url,
            name=TOOLBOX_TOOL_NAME,
            timeout=timeout,
            # 契約にないツールを toolbox が広告しても、モデルには見せない
            allowed_tools=allowed,
            # toolbox の require_approval はランタイムが強制する(MCP 側は止めない)。
            # このラボは方式 A / B と同じく承認なし(更新系の承認は今後の課題)
            approval_mode="never_require",
            tool_result_content="content_first",
        )
        return Agent(
            chat_client,
            name=AGENT_NAME,
            instructions=instructions,
            tools=[toolbox],
            # 会話履歴はホスティング層(history_source="agent_server")が持つ
            default_options={"store": False},
        )

    return create_agent
