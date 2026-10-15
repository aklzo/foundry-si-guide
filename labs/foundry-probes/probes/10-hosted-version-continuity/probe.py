"""hosted agent の版更新をまたいで会話を続けられるか(2026-09-30 新設)。

本番で hosted agent の新しい版をデプロイしたとき、旧版で始まった会話を続けられるかを
確かめる。公式(manage-hosted-sessions 2026-08-21 版)は「セッション(サンドボックス)は
作成時に 1 つの版に固定される」「会話の続きは previous_response_id か conversation で、
セッション ID とは別」と書いており、**会話のつなぎ方によって版更新後の挙動が変わりうる**。

会話のつなぎ方 3 通り × 版の操作 5 段階を観察する:

  P = previous_response_id だけ(セッション ID は渡さない。Port 15 の中間層と同じ)
  S = previous_response_id + agent_session_id(サンドボックスの $HOME も引き継ぐ)
  C = conversation ID(公式: 会話に安定したセッションが自動で結び付く)

  1. v1 にルーティングして 3 本の会話を 2 ターンずつ始める
  2. v2 をデプロイして 100% を v2 に向ける → 3 本を続ける(+ v2 で新しい会話 N)
     移行の試み: v2 に固定した新しいセッションで S / C を続ける
  3. ロールバック: 100% を v1 に戻す → v2 で始めた N を続ける → v2 に戻す
  4. v1 の版を削除する → 3 本を続ける
  5. 休止: idle_timeout(120 秒)を超えて待ち、v3 をデプロイして 100% を v3 に向ける →
     暗黙に作られたセッション(P / N)と、v2 に明示固定したセッション(S / C の移行先)を再開する

検証用エージェント(agent/main.py)はモデルを呼ばず、応答した版・セッション・受け取った
履歴・$HOME のマーカー・コンテナの起動時刻を JSON で返す。idle_timeout は 120 秒。
2026-09-30 の実測結果と解釈は NOTES.md(5 は当日 3 回に分けて実行した内容を 1 本にまとめたもの)。

``--scenario release``(2026-10-06 追加・未実測): 公式の本番リリース手順(manage-hosted-agent
2026-09-16 版「既存セッションは作成時の版に束縛され、セレクタ変更で移行しない」)と 09-30 の
観察「休止明けは現行のルーティング先」の食い違いを白黒つけるシナリオ。旧版の削除や休止中の
新しい版の作成を挟まずに、production 固定 → 候補作成 → 候補専用セッション → 昇格 → 休止
(idle_timeout 経過と stop_session の 2 通り)→ 再開 → 休止中のロールバック、の順に進め、
再開したターンの版を「公式どおり / 09-30 と同じ」で判定する(別名のエージェントを使い、最後に削除)。

前提: az login 済み・Foundry User(agents/write)・FOUNDRY_PROJECT_ENDPOINT
(infra.bicep の出力。環境変数が lab の .env より優先)。課金は hosted agent の
セッション中の CPU / メモリだけ(モデルは呼ばない)。

    uv run python probes/10-hosted-version-continuity/probe.py 2>&1 | tee logs/10-hosted-version-continuity.log
    uv run python probes/10-hosted-version-continuity/probe.py --scenario release 2>&1 \
        | tee logs/10-hosted-version-continuity-release.log
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from foundry_probes.common import LAB_ROOT, section, show

PROBE_DIR = Path(__file__).resolve().parent
AGENT_DIR = PROBE_DIR / "agent"
AGENT_NAME = "probe-version-continuity"
#: --scenario release 用(09-30 のエージェントのセッションと混ざらないよう別名にする)
RELEASE_AGENT_NAME = "probe-release-binding"
IDLE_TIMEOUT_SECONDS = 120  # --idle-timeout で変更可(release のみ)
#: release の R5 の待ち時間(None = idle_timeout + 60 秒)。--wait で変更可
RELEASE_WAIT_SECONDS: int | None = None
#: セレクタの更新方法。replace = AgentEndpointConfig を組み直して送る(2026-09-30 / 10-06 の既定)、
#: preserve = 既存のエンドポイント設定を読んでセレクタだけ差し替える。--route-mode で変更可
ROUTE_MODE = "replace"
RESULT_PATH = LAB_ROOT / "logs" / "10-hosted-version-continuity.json"
RELEASE_RESULT_PATH = LAB_ROOT / "logs" / "10-hosted-version-continuity-release.json"

records: list[dict[str, Any]] = []


def _zip_agent(tmp: Path) -> Path:
    zip_path = tmp / "agent.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("main.py", "requirements.txt"):
            zf.write(AGENT_DIR / name, name)
    return zip_path


def deploy(project: Any, build: str, agent_name: str = AGENT_NAME) -> str:
    """検証用エージェントの新しい版を作り、active になるまで待つ(ルーティングは別)。"""
    from azure.ai.projects.models import (
        CodeConfiguration,
        CodeDependencyResolution,
        HostedAgentDefinition,
        ProtocolVersionRecord,
        SessionConfiguration,
    )

    definition = HostedAgentDefinition(
        cpu="0.5",
        memory="1Gi",
        code_configuration=CodeConfiguration(
            runtime="python_3_13",
            entry_point=["python", "main.py"],
            dependency_resolution=CodeDependencyResolution.REMOTE_BUILD,
        ),
        environment_variables={"PROBE_BUILD": build},
        protocol_versions=[ProtocolVersionRecord(protocol="responses", version="2.0.0")],
        session_configuration=SessionConfiguration(idle_timeout_seconds=IDLE_TIMEOUT_SECONDS),
    )
    with tempfile.TemporaryDirectory() as tmp, _zip_agent(Path(tmp)).open("rb") as code:
        created = project.agents.create_version_from_code(
            agent_name=agent_name,
            definition=definition,
            code=code,
            description=f"probe 10 build {build}",
        )
    version = created.version
    started = time.monotonic()
    while True:
        details = project.agents.get_version(agent_name=agent_name, agent_version=version)
        status = details["status"]
        if status == "active":
            break
        if status == "failed":
            show("provisioning failed", dict(details))
            raise SystemExit(1)
        if time.monotonic() - started > 900:
            raise SystemExit("provisioning timeout")
        time.sleep(10)
    print(f"  build={build} -> version {version} active ({time.monotonic() - started:.0f}s)")
    return version


def route(project: Any, version: str, agent_name: str = AGENT_NAME) -> None:
    from azure.ai.projects.models import (
        AgentEndpointConfig,
        FixedRatioVersionSelectionRule,
        ProtocolConfiguration,
        ResponsesProtocolConfiguration,
        VersionSelector,
    )

    if ROUTE_MODE == "preserve":
        # 既存のエンドポイント設定(認可スキームなど)を保ち、セレクタだけ差し替える
        # (maf-ports Port 11 / 公式「プロトコルや認可の設定は保ったまま」と同じ形。2026-10-06 追加)
        current = project.agents.get(agent_name=agent_name).agent_endpoint
        body = {k: v for k, v in dict(current or {}).items() if k != "publish_approval_status"}
        before_keys = sorted(body)
        body["version_selector"] = {
            "version_selection_rules": [
                {"type": "FixedRatio", "agent_version": str(version), "traffic_percentage": 100}
            ]
        }
        body.setdefault("protocol_configuration", {"responses": {}})
        project.agents.update_details(agent_name=agent_name, agent_endpoint=AgentEndpointConfig(body))
        print(f"  routed 100% -> version {version}(preserve: 既存の {before_keys} を保持)")
        return
    project.agents.update_details(
        agent_name=agent_name,
        agent_endpoint=AgentEndpointConfig(
            version_selector=VersionSelector(
                version_selection_rules=[
                    FixedRatioVersionSelectionRule(agent_version=version, traffic_percentage=100)
                ]
            ),
            protocol_configuration=ProtocolConfiguration(responses=ResponsesProtocolConfiguration()),
        ),
    )
    print(f"  routed 100% -> version {version}")


def ask(
    client: Any,
    label: str,
    text: str,
    *,
    prev: str | None = None,
    session: str | None = None,
    conversation: str | None = None,
) -> dict[str, Any]:
    """1 ターン送って、応答した版・履歴・セッションを記録する(失敗も記録)。"""
    extra: dict[str, Any] = {}
    if session:
        extra["agent_session_id"] = session
    if conversation:
        extra["conversation"] = conversation
    kwargs: dict[str, Any] = {"input": text, "store": True}
    if prev:
        kwargs["previous_response_id"] = prev
    if extra:
        kwargs["extra_body"] = extra
    sent = {"prev": prev, "session": session, "conversation": conversation}
    started = time.monotonic()
    try:
        resp = client.responses.create(**kwargs)
    except Exception as ex:
        rec = {
            "label": label,
            "ok": False,
            "sent": sent,
            "status_code": getattr(ex, "status_code", None),
            "error": str(getattr(ex, "body", None) or ex)[:600],
            "elapsed_s": round(time.monotonic() - started, 1),
        }
        records.append(rec)
        print(f"  [{label}] ERROR {rec['status_code']}: {rec['error'][:300]}")
        return rec
    extra_fields = dict(resp.model_extra or {})
    try:
        report = json.loads(resp.output_text)
    except Exception:
        report = {"raw": (resp.output_text or "")[:300]}
    history = report.get("history") or []
    first_user = next((h.get("text") for h in history if h.get("role") == "user"), None)
    rec = {
        "label": label,
        "ok": True,
        "sent": sent,
        "response_id": resp.id,
        "status": resp.status,
        "agent_session_id": extra_fields.get("agent_session_id"),
        "extra_keys": sorted(extra_fields),
        "agent_reference": extra_fields.get("agent_reference"),
        "build": report.get("build"),
        "agent_version_env": report.get("agent_version_env"),
        "session_env": report.get("session_env"),
        "history_count": report.get("history_count"),
        "history_first_user": first_user,
        "history_error": report.get("history_error"),
        "marker_before": report.get("marker_before"),
        "appinsights_env_present": report.get("appinsights_env_present"),
        "container_started_at": report.get("container_started_at"),
        "elapsed_s": round(time.monotonic() - started, 1),
    }
    records.append(rec)
    print(
        f"  [{label}] build={rec['build']} v{rec['agent_version_env']} "
        f"session={str(rec['agent_session_id'])[:12]} history={rec['history_count']} "
        f"first_user={rec['history_first_user']!r} marker={rec['marker_before']} "
        f"history_error={rec['history_error']} ({rec['elapsed_s']}s)"
    )
    return rec


def list_sessions(project: Any, title: str, agent_name: str = AGENT_NAME) -> None:
    try:
        items = [s.as_dict() for s in project.agents.list_sessions(agent_name=agent_name)]
    except Exception as ex:
        print(f"  list_sessions failed: {ex}")
        return
    records.append({"label": f"sessions:{title}", "sessions": items})
    show(f"sessions ({title})", items, limit=2500)


def run_continuity(project: Any) -> int:
    """2026-09-30 実測のシナリオ(3 通りのつなぎ方 × 版の操作 5 段階)。"""
    section("1. v1 をデプロイして 3 通りのつなぎ方で会話を始める")
    v1 = deploy(project, "v1")
    route(project, v1)
    client = project.get_openai_client(agent_name=AGENT_NAME)
    p1 = ask(client, "P1@v1", "P: 好きな果物はりんご")
    p2 = ask(client, "P2@v1", "P: 覚えている?", prev=p1.get("response_id"))
    s1 = ask(client, "S1@v1", "S: 好きな果物はみかん")
    s_session = s1.get("agent_session_id")
    s2 = ask(client, "S2@v1", "S: 覚えている?", prev=s1.get("response_id"), session=s_session)
    conv = client.conversations.create()
    print(f"  conversation {conv.id}")
    ask(client, "C1@v1", "C: 好きな果物はもも", conversation=conv.id)
    ask(client, "C2@v1", "C: 覚えている?", conversation=conv.id)
    list_sessions(project, "after v1 turns")

    section("2. v2 をデプロイして 100% を v2 に向け、同じ会話を続ける")
    v2 = deploy(project, "v2")
    route(project, v2)
    p3 = ask(client, "P3@route-v2", "P: まだ覚えている?", prev=p2.get("response_id"))
    s3 = ask(client, "S3@route-v2", "S: まだ覚えている?", prev=s2.get("response_id"), session=s_session)
    ask(client, "C3@route-v2", "C: まだ覚えている?", conversation=conv.id)
    n1 = ask(client, "N1@route-v2", "N: 好きな果物はぶどう")

    section("2b. 移行の試み: v2 に固定した新しいセッションで S / C を続ける")
    from azure.ai.projects.models import VersionRefIndicator

    migrated: dict[str, str | None] = {}
    for key in ("S", "C"):
        try:
            session = project.agents.create_session(
                agent_name=AGENT_NAME, version_indicator=VersionRefIndicator(agent_version=v2)
            )
            migrated[key] = session.agent_session_id
            show(f"create_session pinned v{v2} for {key}", session.as_dict(), limit=600)
        except Exception as ex:
            migrated[key] = None
            print(f"  create_session failed for {key}: {ex}")
    if migrated.get("S"):
        ask(client, "S-mig@v2session", "S: 新しいセッションでも覚えている?",
            prev=s3.get("response_id") or s2.get("response_id"), session=migrated["S"])
    if migrated.get("C"):
        ask(client, "C-mig@v2session", "C: 新しいセッションでも覚えている?",
            conversation=conv.id, session=migrated["C"])
    list_sessions(project, "after routing to v2")

    section("3. ロールバック: 100% を v1 に戻して、v2 で始めた会話 N を続ける")
    route(project, v1)
    ask(client, "N2@route-v1", "N: 覚えている?", prev=n1.get("response_id"))
    route(project, v2)

    section("4. v1 の版を削除して、3 通りの会話を続ける")
    try:
        result = project.agents.delete_version(agent_name=AGENT_NAME, agent_version=v1)
        show("delete_version(v1)", result.as_dict() if hasattr(result, "as_dict") else result)
        records.append({"label": "delete_v1", "ok": True})
    except Exception as ex:
        print(f"  delete_version(v1) failed: {getattr(ex, 'status_code', '')} {str(ex)[:400]}")
        records.append({"label": "delete_v1", "ok": False, "error": str(ex)[:400]})
        try:
            project.agents.delete_version(agent_name=AGENT_NAME, agent_version=v1, force=True)
            print("  delete_version(v1, force=True) ok")
            records.append({"label": "delete_v1_force", "ok": True})
        except Exception as ex2:
            print(f"  delete_version(v1, force=True) failed: {str(ex2)[:400]}")
            records.append({"label": "delete_v1_force", "ok": False, "error": str(ex2)[:400]})
    time.sleep(20)
    p4 = ask(client, "P4@v1-deleted", "P: 版を消した後も覚えている?", prev=p3.get("response_id"))
    ask(client, "S4@v1-deleted", "S: 版を消した後も覚えている?",
        prev=s3.get("response_id") or s2.get("response_id"), session=s_session)
    ask(client, "C4@v1-deleted", "C: 版を消した後も覚えている?", conversation=conv.id)
    list_sessions(project, "after deleting v1")

    section("5. 休止したセッションを、v3 に切り替えた後に再開する")
    wait = IDLE_TIMEOUT_SECONDS + 60
    print(f"  {wait} 秒待って全セッションを休止させる(idle_timeout {IDLE_TIMEOUT_SECONDS} 秒)")
    time.sleep(wait)
    list_sessions(project, "after idle wait")
    v3 = deploy(project, "v3")
    route(project, v3)
    ask(client, "P5@route-v3(idle)", "P: 休止明けでも覚えている?", prev=p4.get("response_id"))
    ask(client, "N3@route-v3(idle)", "N: 休止明けでも覚えている?", prev=n1.get("response_id"))
    if migrated.get("S"):
        ask(client, "Smig2@route-v3(pinned-v2)", "S: 休止明け(v2 固定セッション)",
            prev=s3.get("response_id") or s2.get("response_id"), session=migrated["S"])
    if migrated.get("C"):
        ask(client, "Cmig2@route-v3(pinned-v2)", "C: 休止明け(v2 固定セッション)",
            conversation=conv.id, session=migrated["C"])
    list_sessions(project, "after resuming on v3")

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps({"v1": v1, "v2": v2, "v3": v3, "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    section("まとめ")
    for rec in records:
        if "build" in rec or not rec.get("ok", True):
            print(
                f"  {rec['label']:<26} ok={rec.get('ok')} build={rec.get('build')} "
                f"history={rec.get('history_count')} status={rec.get('status_code', '')}"
            )
    print(f"  詳細: {RESULT_PATH}")
    return 0


def session_state(project: Any, agent_name: str, session_id: str | None) -> dict[str, Any]:
    """セッションの状態(status・version_indicator・最終アクセス・停止時刻)を取る。"""
    if not session_id:
        return {"agent_session_id": None}
    try:
        data = project.agents.get_session(agent_name=agent_name, session_id=session_id).as_dict()
    except Exception as ex:
        return {"agent_session_id": session_id, "error": str(ex)[:300]}
    keys = ("agent_session_id", "status", "version_indicator", "last_accessed_at", "stopped_at")
    return {k: data.get(k) for k in keys}


def snapshot(project: Any, agent_name: str, title: str, sessions: dict[str, str | None]) -> None:
    states = {key: session_state(project, agent_name, sid) for key, sid in sessions.items()}
    records.append({"label": f"states:{title}", "states": states})
    for key, st in states.items():
        indicator = st.get("version_indicator") or {}
        print(
            f"  {key:<5} session={str(st.get('agent_session_id'))[:12]} status={st.get('status')} "
            f"version={indicator.get('agent_version')} stopped_at={st.get('stopped_at')}"
            + (f" error={st['error']}" if st.get("error") else "")
        )


def run_release(project: Any) -> int:
    """公式の本番リリース手順(manage-hosted-agent 2026-09-16 版)に沿って、休止明けの版を確かめる。

    公式: 「既存のセッションは作成時の版に束縛され、セレクタを変えても移行しない」。
    2026-09-30 の実測: 起動中は旧版のまま、休止明けは現行のルーティング先で再開した。
    09-30 の実測は「旧版の force 削除」「休止中の新しい版の作成」を挟んでいたので、
    ここではそれを除き、公式手順どおり(production を固定 → 候補を作成 → 候補専用
    セッションで確認 → セレクタを切り替え)に進めてから、セッションを休止させて再開する。

      A = conversation でつないだ会話(セッションは自動で結び付く)
      B = previous_response_id + agent_session_id(暗黙に作られたセッション)
      P = create_session で v1 に明示固定したセッション
      N = セレクタ切り替え後に始めた会話(v2 で作成)— 休止中にロールバックする対照

    判定(R6・R7 の まとめ): 再開したターンの版が「作成時の版」なら公式どおり、
    「その時点のルーティング先」なら 09-30 の実測どおり。休止は idle_timeout の経過(B)と
    stop_session(A・P・N)の 2 通りで作る(stop は 2.7.0 以降の SDK にある)。
    """
    from azure.ai.projects.models import VersionRefIndicator

    agent = RELEASE_AGENT_NAME
    expectations: list[dict[str, Any]] = []

    def expect(rec: dict[str, Any], official: str, observed_0930: str) -> None:
        # 版の比較はコンテナに注入される FOUNDRY_AGENT_VERSION(= サービスの版番号)で行う
        expectations.append({
            "label": rec["label"],
            "build": rec.get("build"),
            "version": rec.get("agent_version_env"),
            "official": official,
            "0930": observed_0930,
        })

    def create_pinned(version: str) -> str | None:
        try:
            created = project.agents.create_session(
                agent_name=agent, version_indicator=VersionRefIndicator(agent_version=version)
            )
            return created.agent_session_id
        except Exception as ex:
            print(f"  create_session(v{version}) failed: {str(ex)[:300]}")
            return None

    def stop(key: str, session_id: str | None) -> None:
        if not session_id:
            return
        try:
            project.agents.stop_session(agent_name=agent, session_id=session_id)
            print(f"  stop_session({key}) ok")
        except Exception as ex:
            print(f"  stop_session({key}) failed: {getattr(ex, 'status_code', '')} {str(ex)[:300]}")

    section("R1. v1 をデプロイし、production を v1 に固定(FixedRatio 100%)")
    v1 = deploy(project, "v1", agent_name=agent)
    route(project, v1, agent_name=agent)
    client = project.get_openai_client(agent_name=agent)

    section("R2. v1 で A / B / P の会話を始める")
    conv = client.conversations.create()
    a1 = ask(client, "A1@v1", "A: 好きな色は赤", conversation=conv.id)
    b1 = ask(client, "B1@v1", "B: 好きな色は青")
    p_session = create_pinned(v1)
    p1 = ask(client, "P1@v1(pinned)", "P: 好きな色は緑", session=p_session)
    sessions: dict[str, str | None] = {
        "A": a1.get("agent_session_id"),
        "B": b1.get("agent_session_id"),
        "P": p_session,
    }
    snapshot(project, agent, "after v1 turns", sessions)

    section("R3. 候補 v2 を作成(セレクタは v1 のまま)→ 新しい会話は v1、候補専用セッションは v2")
    v2 = deploy(project, "v2", agent_name=agent)
    expect(ask(client, "N0@selector-v1", "N0: 新しい会話"), official=v1, observed_0930=v1)
    cand = create_pinned(v2)
    expect(ask(client, "Cand@v2(pinned)", "Cand: 候補の確認", session=cand), official=v2, observed_0930=v2)

    section("R4. 昇格: セレクタを v2 へ → 起動中の A / B / P は作成時の版のまま(公式と 09-30 で一致)")
    route(project, v2, agent_name=agent)
    a2 = ask(client, "A2@selector-v2(active)", "A: 覚えている?", conversation=conv.id)
    b2 = ask(client, "B2@selector-v2(active)", "B: 覚えている?",
             prev=b1.get("response_id"), session=sessions["B"])
    p2 = ask(client, "P2@selector-v2(active)", "P: 覚えている?",
             prev=p1.get("response_id"), session=p_session)
    for rec in (a2, b2, p2):
        expect(rec, official=v1, observed_0930=v1)
    n1 = ask(client, "N1@selector-v2", "N: 好きな色は黄")
    expect(n1, official=v2, observed_0930=v2)
    sessions["N"] = n1.get("agent_session_id")
    snapshot(project, agent, "after promotion", sessions)

    section("R5. 休止させる: A / P は stop_session、B は idle_timeout の経過を待つ")
    stop("A", sessions["A"])
    stop("P", sessions["P"])
    wait = RELEASE_WAIT_SECONDS or IDLE_TIMEOUT_SECONDS + 60
    print(f"  {wait} 秒待つ(idle_timeout {IDLE_TIMEOUT_SECONDS} 秒)。この間 N は使わない"
          f"({'N と B も休止する' if wait > IDLE_TIMEOUT_SECONDS else 'B と N は起動中のまま = 対照'})")
    time.sleep(wait)
    snapshot(project, agent, "suspended", sessions)

    section("R6. 再開(新しい版は作らない): 公式どおりなら v1、09-30 の実測どおりなら v2")
    a3 = ask(client, "A3@selector-v2(resumed)", "A: 休止明けでも覚えている?", conversation=conv.id)
    b3 = ask(client, "B3@selector-v2(resumed)", "B: 休止明けでも覚えている?",
             prev=b2.get("response_id") or b1.get("response_id"), session=sessions["B"])
    p3 = ask(client, "P3@selector-v2(resumed)", "P: 休止明けでも覚えている?",
             prev=p2.get("response_id") or p1.get("response_id"), session=p_session)
    for rec in (a3, b3, p3):
        expect(rec, official=v1, observed_0930=v2)
    snapshot(project, agent, "after resume", sessions)

    section("R7. 休止中のロールバック: N(v2 で作成)を止めてセレクタを v1 に戻し、N を再開")
    stop("N", sessions["N"])
    route(project, v1, agent_name=agent)
    n2 = ask(client, "N2@selector-v1(resumed)", "N: 覚えている?",
             prev=n1.get("response_id"), session=sessions["N"])
    expect(n2, official=v2, observed_0930=v1)
    snapshot(project, agent, "after rollback resume", sessions)

    section("R8. 後片付け(エージェントごと削除。セッションが残るので force)")
    try:
        project.agents.delete(agent_name=agent, force=True)
        print(f"  delete({agent}, force=True) ok")
    except Exception as ex:
        print(f"  delete({agent}) failed: {str(ex)[:300]}")

    RELEASE_RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RELEASE_RESULT_PATH.write_text(
        json.dumps(
            {"v1": v1, "v2": v2, "expectations": expectations, "records": records},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    section("まとめ(公式 = 作成時の版に束縛 / 0930 = 休止明けは現行のルーティング先)")
    for exp in expectations:
        version = str(exp["version"])
        verdict = (
            "両方と一致" if version == exp["official"] == exp["0930"]
            else "公式どおり" if version == exp["official"]
            else "09-30 と同じ" if version == exp["0930"]
            else "どちらとも違う"
        )
        print(
            f"  {exp['label']:<26} 応答した版=v{exp['version']}({exp['build']}) "
            f"公式=v{exp['official']} 0930=v{exp['0930']} -> {verdict}"
        )
    print(f"  詳細: {RELEASE_RESULT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="probe 10: hosted agent の版更新と会話の継続")
    parser.add_argument(
        "--scenario",
        choices=("continuity", "release"),
        default="continuity",
        help="continuity = 2026-09-30 実測のシナリオ(既定)/ release = 公式のリリース手順で休止明けの版を確かめる",
    )
    parser.add_argument(
        "--idle-timeout", type=int, default=120,
        help="版の idle_timeout_seconds(120〜3600。既定 120。サービス既定は 900)",
    )
    parser.add_argument(
        "--wait", type=int, default=None,
        help="release の R5 で待つ秒数(既定 idle_timeout+60。idle_timeout より短くすると B は起動中のまま)",
    )
    parser.add_argument(
        "--route-mode", choices=("replace", "preserve"), default="replace",
        help="セレクタの更新方法(replace = 組み直して送る / preserve = 既存設定を保ってセレクタだけ差し替え)",
    )
    args = parser.parse_args()
    global IDLE_TIMEOUT_SECONDS, RELEASE_WAIT_SECONDS, ROUTE_MODE
    IDLE_TIMEOUT_SECONDS = args.idle_timeout
    RELEASE_WAIT_SECONDS = args.wait
    ROUTE_MODE = args.route_mode
    load_dotenv(LAB_ROOT / ".env")  # 既存の環境変数は上書きしない
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        print("FOUNDRY_PROJECT_ENDPOINT が未設定(infra.bicep の出力 projectEndpoint)", file=sys.stderr)
        return 2
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    if args.scenario == "release":
        return run_release(project)
    return run_continuity(project)


if __name__ == "__main__":
    sys.exit(main())
