"""実 MAF ``Agent`` + 実ツール dict の配線オフラインテスト(ネットワーク不要)。

MCP ツール(github-mcp ポート)とは対照的に、code_interpreter の dict は
**通常ツール**として ``agent.default_options["tools"]`` に載る(dict は
normalize_tools をそのまま通過 — agent_framework _tools.py 990 行)。
クライアント側に接続ライフサイクルは無い(サーバー側ツール)。"""

import pytest

pytest.importorskip("agent_framework")

from data_analysis_ci_maf.agents import INSTRUCTIONS, build_analyst_agent, build_chat_client
from data_analysis_ci_maf.config import FoundrySettings
from data_analysis_ci_maf.tools import build_code_interpreter_tool

SETTINGS = FoundrySettings(
    openai_v1_endpoint="https://example.openai.azure.com/openai/v1",
    model="gpt-5.4-mini",
    api_key="dummy",
    app_insights_connection_string=None,
)


def test_agent_holds_code_interpreter_as_plain_tool() -> None:
    chat_client = build_chat_client(SETTINGS)
    tool = build_code_interpreter_tool(chat_client, ["file-abc123"])

    agent = build_analyst_agent(chat_client, tool)

    # dict ツールは default_options["tools"] へ(mcp_tools ではない)
    assert agent.default_options.get("tools") == [tool]
    assert agent.mcp_tools == []
    assert callable(agent.run)


def test_agent_instructions_keep_original_skeleton() -> None:
    """元 system_message の骨格(expert data analyst / 対象データ / 手段 /
    簡潔な回答)を保ち、手段だけ DuckDB SQL → Code Interpreter の Python。"""
    chat_client = build_chat_client(SETTINGS)
    tool = build_code_interpreter_tool(chat_client, ["file-abc123"])

    agent = build_analyst_agent(chat_client, tool)

    instructions = agent.default_options.get("instructions")
    assert instructions == INSTRUCTIONS
    assert instructions.startswith("You are an expert data analyst.")
    assert "code interpreter" in instructions
    assert "DuckDB" not in instructions  # 手段の置き換えが完了している


def test_chat_client_targets_foundry_v1_endpoint() -> None:
    chat_client = build_chat_client(SETTINGS)

    assert chat_client.model == "gpt-5.4-mini"
    # アップロードに再利用する内包 AsyncOpenAI(cli.py の chat_client.client.files)
    assert hasattr(chat_client.client, "files")


def test_agent_requests_code_interpreter_outputs() -> None:
    """``code_interpreter_call.outputs`` を include しないと Responses API は
    outputs を null で返し、実行ログ・画像が抽出できない(2026-10-06 ライブで
    付けないとログ 0 件・付けると 1 件を実測)。"""
    from data_analysis_ci_maf.agents import CODE_INTERPRETER_OUTPUTS_INCLUDE

    chat_client = build_chat_client(SETTINGS)
    agent = build_analyst_agent(chat_client, build_code_interpreter_tool(chat_client, ["f"]))

    assert CODE_INTERPRETER_OUTPUTS_INCLUDE == "code_interpreter_call.outputs"
    assert agent.default_options.get("include") == [CODE_INTERPRETER_OUTPUTS_INCLUDE]


async def test_request_wire_carries_include_and_logs_are_extracted() -> None:
    """実 Agent → 実 OpenAIChatClient → openai SDK の HTTP 層だけを差し替え、
    POST /openai/v1/responses に include(MAF が自動で足す
    reasoning.encrypted_content と併存)と code_interpreter ツールが載ること、
    返ってきた logs が extract_analysis で取り出せることを固定する。"""
    import json

    import httpx2
    from openai import AsyncOpenAI

    from data_analysis_ci_maf.analysis import run_analysis

    requests: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append({"url": str(request.url), "body": json.loads(request.content)})
        return httpx2.Response(
            200,
            json={
                "id": "resp_1",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "gpt-5.4-mini",
                "output": [
                    {
                        "type": "code_interpreter_call",
                        "id": "ci_1",
                        "status": "completed",
                        "code": "print(df['revenue'].sum())",
                        "container_id": "cntr_1",
                        "outputs": [{"type": "logs", "logs": "3225050\n"}],
                    },
                    {
                        "type": "message",
                        "id": "msg_1",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "合計は 3,225,050", "annotations": []}],
                    },
                ],
                "parallel_tool_calls": True,
                "tool_choice": "auto",
                "tools": [],
            },
        )

    chat_client = build_chat_client(SETTINGS)
    chat_client.client = AsyncOpenAI(
        base_url=SETTINGS.openai_v1_endpoint,
        api_key=SETTINGS.api_key,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    agent = build_analyst_agent(chat_client, build_code_interpreter_tool(chat_client, ["f-1"]))

    result = await run_analysis(agent, "q")

    assert len(requests) == 1
    assert requests[0]["url"] == "https://example.openai.azure.com/openai/v1/responses"
    body = requests[0]["body"]
    assert "code_interpreter_call.outputs" in body["include"]
    assert "reasoning.encrypted_content" in body["include"]  # MAF の自動付与と併存
    assert body["tools"][0]["type"] == "code_interpreter"
    assert body["tools"][0]["container"]["file_ids"] == ["f-1"]
    assert result.code_blocks == ["print(df['revenue'].sum())"]
    assert result.logs == ["3225050\n"]
    assert "3,225,050" in result.text
