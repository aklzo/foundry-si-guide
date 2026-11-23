# Agent Optimizer の利用可否 — 実測メモ(2026-11-22)

問い: GA 一覧表(concepts/general-availability、updated 2026-11-17)は Agent optimizer を **「Limited preview」** と書くが、概要(agent-optimizer-overview、2026-11-10)とクイックスタート(quickstart-optimize-prompt-agent、2026-11-17)には申請・許可リストの記述がない。**有効化の設定を何もせずに** API で費用見積もりと最小ジョブが通るか。

環境: RG `rg-ignite26-verify`(**実測後に削除済み**)。公開側 = 13 の `infra.bicep` のパブリックの basic 構成(`aif-…p/pub`、gpt-5.4-mini・gpt-5.4・text-embedding-3-small を GlobalStandard 10)、閉域側 = 12 のプロジェクト(gpt-5.4 を追加デプロイ)。SDK `azure-ai-projects` 2.11.0(PyPI 最新、2026-11-13)を `uv run --with` で使い、呼び出しは実行者の Entra トークン(Foundry User @アカウント)。閉域側は VM 内から同じ本文を REST で送った。`Foundry-Features` ヘッダー・機能登録(`az feature register`)・プレビューの申請は**どれもしていない**。

ジョブの中身: 対象 = prompt agent(Copilot harness なし、gpt-5.4-mini、指示「質問に日本語で一言だけ答える。」)、データ = インラインの 3 行(質問+正解)、評価器 `builtin.coherence`、評価モデル gpt-5.4-mini(デプロイ名をそのまま。SDK の docstring の `{connectionName}/{deploymentName}` 形式でなくても通った)、最適化モデル gpt-5.4、`max_candidates=1`。要求本文は `logs/estimate-body.jsonl`。

## 結果(公式の記述 / 実測 / 一致・不一致)

| # | 項目 | 公式の記述 | 実測 | 判定 |
| --- | --- | --- | --- | --- |
| C1 | 費用見積もり(公開) | agent-optimizer-costs:「estimate はジョブを作らずモデルも呼ばない。agent 2,000 / 400、judge 3,000 / 120、reflection 6,000 / 2,000 トークンの静的仮定」 | `POST /agent_optimization_jobs:estimate?api-version=v1` → **200**。呼び出し回数 agent 6 / 16.2 / 54、evaluation 6 / 16.2 / 54、optimization 0 / 1.5 / 5(low / typical / ceiling)、費用 USD **0.0365 / 0.166 / 0.554**、`prices_as_of` = 2026-11-16T00:00Z。1 回あたりの単価を逆算すると agent $0.0033 = 2,000 × $0.75/1M+400 × $4.5/1M(gpt-5.4-mini)、evaluation $0.00279 = 3,000 × $0.75/1M+120 × $4.5/1M、optimization $0.045 = 6,000 × $2.5/1M+2,000 × $15/1M(gpt-5.4)で、静的仮定どおり | **一致**(申請なしで通る) |
| C2 | 最小ジョブ(公開) | GA 一覧表「Limited preview」/ 概要「prompt agent の最適化はポータルのウィザードで開始」 | `begin_create_optimization_job` → **201、queued → in_progress → 約 2 分で succeeded**。baseline 0.833 → candidate_1 0.917(変更は instructions)。候補は `agent_version: draft-…` としてエージェントの下書き版で評価された。インラインのデータは `opt-inline-…` という dataset に変換され、評価器名は `coherence` に正規化。実測トークン: agent 666 / 51、evaluation 12,177 / 845、optimization 891 / 152(≈ ¥2.9) | GA 一覧表の「Limited」とは**不一致**(申請・許可リストのエラーは出ない)。ポータル以外(SDK / REST)からも prompt agent を最適化できる |
| C3 | 閉域のプロジェクト | 記載なし(Optimizer の文書にネットワークの記述はない) | VM 内から同じ本文で estimate **200**(公開と同じ値)、ジョブ **201 → 約 3.6 分で succeeded**(baseline 0.75 → 0.833、トークン agent 1,621 / 229・evaluation 28,590 / 1,795・optimization 2,677 / 405 ≈ ¥7)。閉域のプロジェクトでも評価・最適化が動いた | 記載なし(**閉域でも動く**) |
| C4 | 対応モデル・リージョン | 概要: 最適化モデルは gpt-5 / 5.1 / 5.2 / 5.4 / 5.5 / DeepSeek-V4-Pro / DeepSeek-V-3.2。hosted 版は Norway East 以外の hosted 対応リージョン | japaneast・gpt-5.4 で制約のエラーなし(対応外のモデルでの失敗は試していない) | 一致(試した範囲) |

`list_optimization_jobs` は実行前 0 件(200)。API キーでも一覧は 200 だった(13 の B2)。

## SI 判断メモ

- **2026-11-22・japaneast では、Agent Optimizer は申請なしで prompt agent に使える。** GA 一覧表の「Limited preview」を根拠に「申請が要る」と顧客に説明しない(ただし GA ではない。プレビューの規約・SLA なしの前提は残る)。
- 実際の消費は estimate の low に近い(3 行・候補 1 で数円)。estimate の ceiling は low の 15 倍で、上限ではなく見積もりの幅。
- 候補はエージェントの**下書き版**として作られ、評価のためにエージェントが実際に呼ばれる。ツールが本番の系に書き込むエージェントでは、公式の警告どおり読み取り専用か検証用の資源に向けてから流す。
- 閉域のプロジェクトでも動くので、閉域案件の改善サイクル(評価 → 最適化)に組み込める。評価モデル・最適化モデルは同じアカウントにデプロイしておく(閉域側は gpt-5.4 を追加して実測した)。

## 再実行

```bash
cd labs/foundry-probes
uv run --with "azure-ai-projects==2.11.0" python probes/14-optimizer-access/probe.py --endpoint <公開プロジェクト>            # estimate のみ
uv run --with "azure-ai-projects==2.11.0" python probes/14-optimizer-access/probe.py --endpoint <公開プロジェクト> --start    # ジョブも開始(estimate の ceiling が ¥1,000 を超えたら開始しない)
probes/12-closed-network/vmrun.sh run optimizer start                                                                        # 閉域側(VM 内から同じ本文)
```
