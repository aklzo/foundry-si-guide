"""トレース本文(gen_ai.* の機微属性)が App Insights のどのテーブルに入るか(2026-10-06 新設)。

公式 traces-sensitive-content(プレビュー、ms.date 2026-07-21): 機微な GenAI 属性 7 つ
(gen_ai.input.messages / output.messages / system_instructions / tool.definitions /
tool.call.arguments / tool.call.result / evaluation.explanation)を専用テーブル
``AppGenAIContent`` に振り分け、テーブルを Protected にして Privileged Monitoring Data
Reader だけに読ませる。移行日 2026-09-30 より前は従来テーブル(AppDependencies /
AppTraces / AppEvents)と専用テーブルの**二重書き**、移行日以降の新しいデータは従来テーブル
の値が「AppGenAIContent への短いポインタ」に置き換わる、と書かれている。

振り分けるのは Application Insights の取り込み側なので、発生源を変えて同じ KQL で見比べる:

  A1. 合成スパン(モデルを呼ばない): chat スパンに gen_ai.input/output.messages・
      system_instructions・tool.definitions、execute_tool スパンに tool.call.arguments / result
  A2. 対照: 同じ本文を gen_ai.* ではない属性名(probe.input_text)で持つスパン
  A3. ログレコード(AppTraces)に gen_ai.input.messages を属性として付ける
  B.  prompt agent のプラットフォーム側スパン(エージェントエンドポイント経由の Responses)
  C.  MAF のクライアント側スパン(Agent.run、sensitive data 有効。``--extra maf`` が必要)

各発生源の本文に固有の目印(``<run>-<source>``)を入れ、AppDependencies / AppTraces /
AppEvents / AppRequests / AppGenAIContent を目印で引いて、テーブルごとの行数・本文の値が
残っているか・``_MS.GenAIContentId`` の有無と AppGenAIContent.Id との一致を見る。
AppGenAIContent の着信は従来テーブルより数分遅い(親の予備実測で約 5 分)ので最大 20 分待つ。

前提: az login 済み・main.bicep の基盤(App Insights をプロジェクトに接続済み)・
環境変数 APPLICATIONINSIGHTS_CONNECTION_STRING / LOG_ANALYTICS_WORKSPACE_ID(customerId)/
FOUNDRY_PROJECT_ENDPOINT / FOUNDRY_OPENAI_V1_ENDPOINT / FOUNDRY_MODEL。
サブスクリプションの preview feature flag(protectGenAISensitiveData)は登録しない
(サブスクリプション全体の設定変更になるため。状態は D で表示だけする)。

    uv sync --extra maf
    uv run python probes/11-trace-content-routing/probe.py 2>&1 | tee logs/11-trace-content-routing.log
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from foundry_probes.common import (
    LAB_ROOT,
    Settings,
    bearer_token,
    make_project_client,
    section,
    show,
)

RUN = f"p11{uuid.uuid4().hex[:8]}"
AGENT_NAME = "probe-trace-content-agent"
MAF_AGENT_NAME = "probe-maf-trace-agent"
TABLES = ("AppDependencies", "AppTraces", "AppEvents", "AppRequests", "AppGenAIContent")
SENSITIVE_KEYS = (
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.system_instructions",
    "gen_ai.tool.definitions",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
)
POLL_SECONDS = 1200
RESULT_PATH = LAB_ROOT / "logs" / "11-trace-content-routing.json"


def _msgs(role: str, text: str) -> str:
    return json.dumps([{"role": role, "parts": [{"type": "text", "content": text}]}], ensure_ascii=False)


def emit_synthetic() -> None:
    """A1〜A3: モデルを呼ばずに gen_ai.* 属性を持つスパンとログを送る。"""
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind

    tracer = trace.get_tracer("foundry-probes.p11")
    m = f"{RUN}-a1"
    with tracer.start_as_current_span("chat probe-synthetic", kind=SpanKind.CLIENT) as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", "azure.ai.openai")
        span.set_attribute("gen_ai.request.model", "probe-synthetic")
        span.set_attribute("gen_ai.input.messages", _msgs("user", f"{m} 入力: 社員番号 E-1234 の残業申請"))
        span.set_attribute("gen_ai.output.messages", _msgs("assistant", f"{m} 出力: 承認しました"))
        span.set_attribute("gen_ai.system_instructions", json.dumps([{"type": "text", "content": f"{m} 指示: 丁寧に"}], ensure_ascii=False))
        span.set_attribute("gen_ai.tool.definitions", json.dumps([{"type": "function", "name": "lookup", "description": f"{m} 定義"}], ensure_ascii=False))
        span.set_attribute("probe.marker", m)
        with tracer.start_as_current_span("execute_tool lookup", kind=SpanKind.INTERNAL) as tool:
            tool.set_attribute("gen_ai.operation.name", "execute_tool")
            tool.set_attribute("gen_ai.tool.name", "lookup")
            tool.set_attribute("gen_ai.tool.call.arguments", json.dumps({"q": f"{m} 引数"}, ensure_ascii=False))
            tool.set_attribute("gen_ai.tool.call.result", json.dumps({"r": f"{m} 結果"}, ensure_ascii=False))
            tool.set_attribute("probe.marker", m)
    m2 = f"{RUN}-a2"
    with tracer.start_as_current_span("chat probe-control", kind=SpanKind.CLIENT) as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "probe-synthetic")
        span.set_attribute("probe.input_text", f"{m2} 入力: 社員番号 E-1234 の残業申請(gen_ai.* ではない属性名)")
        span.set_attribute("probe.marker", m2)
    m3 = f"{RUN}-a3"
    logging.getLogger("foundry_probes.p11").warning(
        "probe log %s", m3,
        extra={"gen_ai.input.messages": _msgs("user", f"{m3} ログの本文"), "probe.marker": m3},
    )
    print(f"  A1={m} A2={m2} A3={m3} を送信")


def call_prompt_agent(settings: Settings) -> None:
    """B: prompt agent のプラットフォーム側スパン(プロジェクトに接続した App Insights へサービスが送る)。"""
    from azure.ai.projects.models import PromptAgentDefinition

    m = f"{RUN}-b"
    project = make_project_client(settings)
    try:
        project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(model=settings.model, instructions=f"{m} 指示: 一文で答える。"),
        )
        client = project.get_openai_client(agent_name=AGENT_NAME)
        r = client.responses.create(input=f"{m} 入力: 再帰関数を一文で説明して。")
        print(f"  B={m} response={r.id} output={r.output_text[:60]!r}")
    except Exception as ex:
        print(f"!! B 失敗: {type(ex).__name__}: {str(ex)[:300]}")
    finally:
        try:
            project.agents.delete(agent_name=AGENT_NAME)
        except Exception as ex:
            print(f"  agent 削除失敗: {str(ex)[:150]}")


def call_maf(settings: Settings) -> None:
    """C: MAF のクライアント側スパン(invoke_agent / chat。sensitive data 有効)。"""
    try:
        from agent_framework import Agent
        from agent_framework.observability import enable_instrumentation
        from agent_framework.openai import OpenAIChatClient
    except ImportError:
        print("!! C スキップ: agent-framework 未導入(uv sync --extra maf)")
        return
    enable_instrumentation(enable_sensitive_data=True, force=True)
    m = f"{RUN}-c"
    client = OpenAIChatClient(
        model=settings.model, api_key=bearer_token(), base_url=settings.openai_v1_endpoint
    )
    agent = Agent(client, instructions=f"{m} 指示: 一文で答える。", name=MAF_AGENT_NAME)
    try:
        r = asyncio.run(agent.run(f"{m} 入力: 二分探索を一文で説明して。"))
        print(f"  C={m} output={str(r.text)[:60]!r}")
    except Exception as ex:
        print(f"!! C 失敗: {type(ex).__name__}: {str(ex)[:300]}")


KQL = """
union withsource=T AppDependencies, AppTraces, AppEvents, AppRequests, AppGenAIContent
| where TimeGenerated > datetime({since})
| where * has "{run}"
| extend props = column_ifexists("Properties", dynamic(null))
| extend src = extract("{run}-(a1|a2|a3|b|c)", 1, tostring(pack_all()))
| extend ContentId = tostring(props["_MS.GenAIContentId"])
| extend RowId = column_ifexists("Id", "")
| project TimeGenerated, IngestedAt = ingestion_time(), T, src, Name = column_ifexists("Name", ""),
          ContentId, RowId, props,
          InputMessages = column_ifexists("InputMessages", ""), OutputMessages = column_ifexists("OutputMessages", ""),
          SystemInstructions = column_ifexists("SystemInstructions", ""),
          ToolCallArguments = column_ifexists("ToolCallArguments", ""), ToolCallResult = column_ifexists("ToolCallResult", ""),
          ToolDefinitions = column_ifexists("ToolDefinitions", ""), Message = column_ifexists("Message", "")
"""


def query_rows(workspace_id: str, since: datetime) -> list[dict[str, Any]]:
    from azure.identity import DefaultAzureCredential
    from azure.monitor.query import LogsQueryClient

    logs_client = LogsQueryClient(DefaultAzureCredential())
    kql = KQL.format(since=since.strftime("%Y-%m-%dT%H:%M:%SZ"), run=RUN)
    res = logs_client.query_workspace(workspace_id, kql, timespan=timedelta(hours=3))
    rows: list[dict[str, Any]] = []
    for table in getattr(res, "tables", []) or []:
        cols = [c if isinstance(c, str) else getattr(c, "name", str(c)) for c in table.columns]
        rows.extend(dict(zip(cols, r)) for r in table.rows)
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """発生源 × テーブルの行数、従来テーブルに本文の値が残っているか、ポインタの一致。"""
    out: dict[str, Any] = {}
    content_ids = {r["RowId"] for r in rows if r["T"] == "AppGenAIContent" and r["RowId"]}
    for r in rows:
        src = r["src"] or "?"
        t = out.setdefault(src, {}).setdefault(r["T"], {"rows": 0, "names": set(), "values_present": set(),
                                                         "pointer_rows": 0, "pointer_matches": 0, "columns_with_marker": set()})
        t["rows"] += 1
        if r["Name"]:
            t["names"].add(r["Name"])
        props = r["props"]
        if isinstance(props, str):
            try:
                props = json.loads(props)
            except Exception:
                props = {}
        props = props or {}
        for key in SENSITIVE_KEYS:
            val = props.get(key)
            if val is None:
                continue
            text = str(val)
            # 移行後は値が AppGenAIContent への「短いポインタ」に置き換わる(公式)。本文が
            # 残っているか(目印入り / 目印なしでも JSON の本文)と、短い値かを分けて記録する
            if RUN in text:
                kind = "本文(目印あり)"
            elif text[:1] in "[{" and len(text) > 30:
                kind = "本文(モデル出力など目印なし)"
            else:
                kind = f"短い値:{text[:60]}"
            t["values_present"].add(f"{key}={kind}")
        if r["ContentId"]:
            t["pointer_rows"] += 1
            t["pointer_matches"] += r["ContentId"] in content_ids
        for col in ("InputMessages", "OutputMessages", "SystemInstructions", "ToolCallArguments",
                    "ToolCallResult", "ToolDefinitions", "Message"):
            if RUN in str(r.get(col) or ""):
                t["columns_with_marker"].add(col)
    for src in out.values():
        for t in src.values():
            for k in ("names", "values_present", "columns_with_marker"):
                t[k] = sorted(t[k])
    return out


def ingestion_lag(rows: list[dict[str, Any]]) -> dict[str, str]:
    lag: dict[str, list[datetime]] = {}
    for r in rows:
        if r.get("IngestedAt"):
            lag.setdefault(r["T"], []).append(r["IngestedAt"])
    return {t: f"{min(v):%H:%M:%S}〜{max(v):%H:%M:%S}" for t, v in lag.items()}


def show_flags_and_table() -> None:
    """D: サブスクリプションの feature flag とテーブルの保護レベル(表示だけ。変更しない)。"""
    for name in ("protectGenAISensitiveData", "optOutProtectGenAISensitiveData"):
        out = subprocess.run(
            ["az", "feature", "show", "--namespace", "Microsoft.Insights", "--name", name,
             "--query", "properties.state", "-o", "tsv"], capture_output=True, text=True, check=False,
        )
        print(f"  feature {name}: {(out.stdout or out.stderr).strip()[:120]}")
    ws = os.environ.get("LOG_ANALYTICS_WORKSPACE_RESOURCE_ID", "").strip()
    if ws:
        out = subprocess.run(
            ["az", "rest", "--method", "get", "--url",
             f"https://management.azure.com{ws}/tables/AppGenAIContent?api-version=2025-07-01"],
            capture_output=True, text=True, check=False,
        )
        try:
            props = json.loads(out.stdout).get("properties", {})
            print(f"  AppGenAIContent: plan={props.get('plan')} retention={props.get('retentionInDays')} "
                  f"protectionLevel={props.get('protectionLevel')}")
        except Exception:
            print(f"  table show 失敗: {out.stderr.strip()[:200]}")


def main() -> int:
    settings = Settings.from_env()
    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    workspace_id = os.environ.get("LOG_ANALYTICS_WORKSPACE_ID", "").strip()
    if not (conn and workspace_id):
        print("APPLICATIONINSIGHTS_CONNECTION_STRING と LOG_ANALYTICS_WORKSPACE_ID(customerId)が必要", file=sys.stderr)
        return 2
    from azure.monitor.opentelemetry import configure_azure_monitor

    # azure-monitor-opentelemetry 1.8.x の既定サンプラーは rate-limited(5 spans/秒)で、短時間に
    # 出るスパンが間引かれうる(maf-ports Port 1 で実例)。件数を比べる probe なので全件送る
    configure_azure_monitor(
        connection_string=conn, logger_name="foundry_probes.p11", sampling_ratio=1.0
    )
    since = datetime.now(UTC) - timedelta(minutes=2)
    print(f"  run={RUN} since={since:%Y-%m-%dT%H:%M:%SZ}")

    section("D. 前提の状態(feature flag・テーブルの保護レベル。表示だけ)")
    show_flags_and_table()

    section("A. 合成スパン・対照スパン・ログ(モデルを呼ばない)")
    emit_synthetic()
    section("B. prompt agent(プラットフォーム側スパン)")
    call_prompt_agent(settings)
    section("C. MAF のクライアント側スパン(sensitive data 有効)")
    call_maf(settings)

    from opentelemetry import _logs, trace

    trace.get_tracer_provider().force_flush()
    _logs.get_logger_provider().force_flush()

    section(f"E. テーブルごとの着信(最大 {POLL_SECONDS // 60} 分ポーリング)")
    t0 = time.monotonic()
    rows: list[dict[str, Any]] = []
    expected = {"a1", "b", "c"}
    while time.monotonic() - t0 < POLL_SECONDS:
        time.sleep(60)
        try:
            rows = query_rows(workspace_id, since)
        except Exception as ex:
            print(f"  query 失敗: {type(ex).__name__}: {str(ex)[:200]}")
            continue
        got = {r["src"] for r in rows if r["T"] == "AppGenAIContent"}
        counts = {}
        for r in rows:
            counts[f"{r['src']}:{r['T']}"] = counts.get(f"{r['src']}:{r['T']}", 0) + 1
        print(f"  {time.monotonic() - t0:5.0f}s rows={len(rows)} AppGenAIContent の発生源={sorted(got)} {counts}")
        if expected <= got:
            time.sleep(60)  # 遅れて届く行を拾う
            rows = query_rows(workspace_id, since)
            break

    section("F. まとめ(発生源 × テーブル)")
    summary = summarize(rows)
    show("summary", summary, limit=6000)
    show("ingestion time (UTC)", ingestion_lag(rows))
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps({"run": RUN, "since": since.isoformat(), "summary": summary,
                    "rows": [{k: (str(v) if isinstance(v, datetime) else v) for k, v in r.items()} for r in rows]},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"  詳細: {RESULT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
