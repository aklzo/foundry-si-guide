"""probe 14: Agent Optimizer は申請・有効化なしで呼べるか(パブリックの basic プロジェクト)。

問い: GA 一覧表(general-availability)は Agent optimizer を「Limited preview」と書くが、Learn の概要
(agent-optimizer-overview)とクイックスタート(quickstart-optimize-prompt-agent)には申請の記述がない。
**何も有効化設定をせずに**、SDK(azure-ai-projects 2.11.0、2026-11-13)の最適化 API で
  (1) 費用見積もり(POST /agent_optimization_jobs:estimate)
  (2) 3 行のデータセットで最小の最適化ジョブ(POST /agent_optimization_jobs、候補 1)
が通るか、申請・許可リストを示すエラーが返るかを記録する。リージョン・モデルの制約で失敗した場合もそのまま残す。

実行(lab 直下。pyproject の azure-ai-projects 下限は 2.8.0 のままにし、この probe だけ 2.11.0 で動かす):
  uv run --with "azure-ai-projects==2.11.0" python probes/14-optimizer-access/probe.py \
      --endpoint <公開プロジェクトのエンドポイント> [--start] [--wait-min 40]
estimate の本文(JSON)は logs/estimate-body.jsonl に保存し、閉域のプロジェクトでも同じ本文で 1 回呼ぶ(vmprobe.py optimizer)。
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentOptimizationCandidateSearchConfiguration,
    AgentOptimizationConfiguration,
    AgentOptimizationEstimateInputs,
    AgentOptimizationEvaluationConfiguration,
    AgentOptimizationEvaluator,
    AgentOptimizationFoundryAgentTargetConfiguration,
    AgentOptimizationJob,
    AgentOptimizationModelConfiguration,
    AgentOptimizationSpace,
    AgentOptimizationTargetCompletionEvaluationSet,
    AgentOptimizationTargetCompletionInlineDataSource,
    AgentOptimizationTargetCompletionTestCase,
    EvaluationModelConfiguration,
    PromptAgentDefinition,
)
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential

HERE = Path(__file__).resolve().parent
AGENT = "a14-opt"


def show(title: str, obj) -> None:
    print(f"\n== {title}")
    if hasattr(obj, "as_dict"):
        obj = obj.as_dict()
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str)[:6000])


def err(title: str, e: Exception) -> None:
    print(f"\n== {title}: {type(e).__name__}")
    if isinstance(e, HttpResponseError):
        print(f"  HTTP {e.status_code} reason={e.reason}")
        try:
            print("  body:", e.response.text()[:3000])
        except Exception:
            print("  message:", str(e)[:3000])
    else:
        print("  ", str(e)[:3000])


def build_config(eval_model: str, evaluator: str, max_candidates: int) -> AgentOptimizationConfiguration:
    cases = [
        AgentOptimizationTargetCompletionTestCase(query="日本の首都はどこ?", ground_truth="東京"),
        AgentOptimizationTargetCompletionTestCase(query="2 + 2 は?", ground_truth="4"),
        AgentOptimizationTargetCompletionTestCase(query="地球で一番大きい海は?", ground_truth="太平洋"),
    ]
    return AgentOptimizationConfiguration(
        evaluation_configuration=AgentOptimizationEvaluationConfiguration(
            training_set=AgentOptimizationTargetCompletionEvaluationSet(
                source=AgentOptimizationTargetCompletionInlineDataSource(test_cases=cases)
            ),
            evaluators=[AgentOptimizationEvaluator(name=evaluator)],
            evaluation_model=EvaluationModelConfiguration(model=eval_model),
        ),
        candidate_search_configuration=AgentOptimizationCandidateSearchConfiguration(max_candidates=max_candidates),
        agent_optimization_space=AgentOptimizationSpace(),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", default="gpt-5.4-mini")
    ap.add_argument("--opt-model", default="gpt-5.4")
    ap.add_argument("--eval-model", default="gpt-5.4-mini", help="deployment 名。{connection}/{deployment} 形式も試す")
    ap.add_argument("--evaluator", default="builtin.coherence")
    ap.add_argument("--max-candidates", type=int, default=1)
    ap.add_argument("--start", action="store_true", help="estimate の後にジョブを開始する")
    ap.add_argument("--max-yen", type=float, default=1000.0, help="estimate の上限がこれを超えたら開始しない(USD は 158 円換算)")
    ap.add_argument("--wait-min", type=int, default=40)
    a = ap.parse_args()

    print(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] endpoint={a.endpoint}")
    project = AIProjectClient(endpoint=a.endpoint, credential=DefaultAzureCredential())

    # 0. 対象の prompt agent(Copilot harness なし)
    try:
        v = project.agents.create_version(
            agent_name=AGENT,
            definition=PromptAgentDefinition(model=a.model, instructions="質問に日本語で一言だけ答える。"),
            description="probe 14 baseline",
        )
        print(f"agent {v.name}:{v.version} created")
    except Exception as e:
        err("create agent", e)
        return 1

    cfg = build_config(a.eval_model, a.evaluator, a.max_candidates)
    target = AgentOptimizationFoundryAgentTargetConfiguration(name=AGENT)
    optm = AgentOptimizationModelConfiguration(model=a.opt_model)
    inputs = AgentOptimizationEstimateInputs(
        target_configuration=target, optimization_model_configuration=optm, optimization_configuration=cfg
    )
    body = inputs.as_dict()
    (HERE / "logs").mkdir(exist_ok=True)
    with open(HERE / "logs" / "estimate-body.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(body, ensure_ascii=False) + "\n")
    show("estimate 要求本文(SDK が送る JSON)", body)

    # 1. 費用見積もり
    est = None
    try:
        est = project.agents.estimate_optimization_job(inputs)
        show("(1) estimate 結果", est)
    except Exception as e:
        err("(1) estimate", e)

    # 既存ジョブ一覧(権限・機能の可否の対照)
    try:
        jobs = list(project.agents.list_optimization_jobs())
        print(f"\n== list_optimization_jobs: {len(jobs)} 件")
    except Exception as e:
        err("list_optimization_jobs", e)

    if not a.start:
        return 0

    # 費用上限の確認(estimate の最大値。通貨は応答に従う)
    if est is not None:
        d = est.as_dict()
        cost = d.get("cost") or {}
        maxv = None
        for k in ("ceiling", "maximum", "max", "upper"):  # 2.11.0 の応答は low / typical / ceiling
            for band in (cost.get("total") or {}, cost):
                if isinstance(band, dict) and isinstance(band.get(k), (int, float)):
                    maxv = band[k]
        cur = (cost.get("currency") or "USD").upper()
        yen = (maxv or 0) * (1 if cur == "JPY" else 158)
        print(f"\n estimate maximum={maxv} {cur} → 約 ¥{yen:.0f}(上限 ¥{a.max_yen:.0f})")
        if maxv is not None and yen > a.max_yen:
            print(" 上限超過のため開始しない")
            return 0

    # 2. 最小の最適化ジョブ
    job = AgentOptimizationJob(
        display_name="probe14-min",
        target_configuration=target,
        optimization_model_configuration=optm,
        optimization_configuration=cfg,
    )
    try:
        poller = project.agents.begin_create_optimization_job(job=job, polling_interval=20)
    except Exception as e:
        err("(2) begin_create_optimization_job", e)
        return 0
    job_id = (getattr(poller, "details", None) or {}).get("job_id")
    print(f"\n== (2) 開始: job_id={job_id} status={poller.status()}")
    t0 = time.time()
    while not poller.done() and time.time() - t0 < a.wait_min * 60:
        time.sleep(30)
        try:
            j = project.agents.get_optimization_job(job_id)
            print(f"  [{int(time.time() - t0)}s] status={j.status} error={j.as_dict().get('error')}")
        except Exception as e:
            err("get_optimization_job", e)
    try:
        j = project.agents.get_optimization_job(job_id)
        show("(2) 最終のジョブ", j)
        if j.status not in ("succeeded", "failed", "cancelled", "skipped"):
            c = project.agents.cancel_optimization_job(job_id)
            show("(2) 待ち時間切れのためキャンセル", c)
        else:
            for cand in project.agents.list_optimization_candidates(job_id=job_id):
                show("candidate", cand)
    except Exception as e:
        err("(2) 結果取得", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
