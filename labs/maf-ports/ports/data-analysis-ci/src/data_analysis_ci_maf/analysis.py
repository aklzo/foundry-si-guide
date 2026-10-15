"""1 クエリの実行と応答からのコード/結果抽出。

元アプリは ``agent.run(user_query)`` → ``response.content`` を表示するだけ
だった(実行された SQL はターミナルの agno ログ頼み)。移植版では Responses
API の ``code_interpreter_call`` 出力アイテムが MAF によって

- ``code_interpreter_tool_call``(``inputs`` = 実行された Python コードの
  text Content)
- ``code_interpreter_tool_result``(``outputs`` = logs の text Content /
  画像の Content)

画像は MAF が ``Content.from_uri(url, media_type="image")`` で作るが、Foundry の
Responses API は画像を **``data:image/png;base64,...`` の data URI** で返すため、
Content の type は ``uri`` ではなく ``data`` になる(2026-10-06 ライブで確認。
旧実装は ``uri`` だけを拾っていて画像を取りこぼしていた)。どちらも拾う。
また ``outputs`` 自体はリクエストの ``include`` に ``code_interpreter_call.outputs``
を指定しないと null で返る(agents.CODE_INTERPRETER_OUTPUTS_INCLUDE)。

の Content として応答メッセージに残る(agent_framework_openai
_chat_client.py 2685 行)ため、**何が実行されどう出力されたか**を構造的に
取り出せる。抽出は実 Content 型に依存しない duck-typing(type 属性の文字列
比較 + getattr)で行い、オフラインテストは実 ``Message`` / ``Content`` を
組んで固定する。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from .agents import SupportsRun

#: 全体タイムアウト秒。元アプリ(同期 run)には無かったが、Code Interpreter は
#: サーバー側でコンテナ起動+コード実行が走るため上限を設ける(CLI で変更可)
DEFAULT_TIMEOUT_SECONDS = 300.0


def build_analysis_prompt(question: str, filename: str) -> str:
    """per-run プロンプト — 元アプリの「'uploaded_data' テーブル」指定に対応。

    元アプリは対象を system_message 内のテーブル名で固定していた。移植版は
    アップロードごとに変わるファイル名を run プロンプト側で伝える
    (コンテナ内では /mnt/data 配下にアップロード時の名前で見える)。
    """
    return (
        f"The data file '{filename}' has been uploaded to the code interpreter "
        f"container (look under /mnt/data).\n\nQuestion: {question}"
    )


@dataclass
class AnalysisResult:
    """回答テキストと、サンドボックスで実行されたコード・出力の抽出結果。"""

    text: str
    code_blocks: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    image_uris: list[str] = field(default_factory=list)


def extract_analysis(response: Any) -> AnalysisResult:
    """AgentResponse から回答と code_interpreter の活動を取り出す(純関数)。"""
    result = AnalysisResult(text=getattr(response, "text", "") or "")
    for message in getattr(response, "messages", None) or []:
        for content in getattr(message, "contents", None) or []:
            content_type = getattr(content, "type", None)
            if content_type == "code_interpreter_tool_call":
                for item in getattr(content, "inputs", None) or []:
                    code = getattr(item, "text", None)
                    if code:
                        result.code_blocks.append(code)
            elif content_type == "code_interpreter_tool_result":
                for item in getattr(content, "outputs", None) or []:
                    if getattr(item, "type", None) == "text" and getattr(item, "text", None):
                        result.logs.append(item.text)
                    elif getattr(item, "type", None) in ("uri", "data") and _is_image(item):
                        result.image_uris.append(item.uri)
    return result


def _is_image(item: Any) -> bool:
    """画像出力か(MAF は media_type="image" を付ける。data URI なら MIME でも判定)。"""
    uri = getattr(item, "uri", None) or ""
    media_type = getattr(item, "media_type", None) or ""
    return bool(uri) and (media_type.startswith("image") or uri.startswith("data:image/"))


def describe_image_uri(uri: str) -> str:
    """CLI 表示用。data URI は base64 本体を出さず MIME と概算サイズだけにする。"""
    if not uri.startswith("data:"):
        return uri
    header, _, payload = uri.partition(",")
    mime = header.removeprefix("data:").split(";")[0] or "application/octet-stream"
    size_kb = len(payload) * 3 / 4 / 1024
    return f"{mime}(data URI で埋め込み・約 {size_kb:.0f} KB)"


async def run_analysis(
    agent: SupportsRun,
    prompt: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> AnalysisResult:
    """エージェントを 1 回実行し、回答+コード/結果の抽出まで行う。

    タイムアウト時は TimeoutError が送出される(CLI がエラーメッセージに
    変換する)。空応答は例外にしない — 元アプリは response.content を
    そのまま表示していた。
    """
    response = await asyncio.wait_for(agent.run(prompt), timeout)
    return extract_analysis(response)
