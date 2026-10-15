# maf-ports — awesome-llm-apps を MAF + Foundry へ移植する検証ラボ

[awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps)(ローカル: `~/oss/awesome-llm-apps`)のエージェント構成を **Microsoft Agent Framework (MAF)** に書き換え、**Foundry のトレーシング・評価**を組み込み、**Bicep でデプロイ可能**にする長期ラボ。

目的は網羅移植ではなく、**「MAF/Foundry で楽になること・苦しくなること」の境界を、多様な協調パターンで体感して記録する**こと(→ [docs/learning-plan.md](../../docs/learning-plan.md) の技術選定判断力)。

## ドキュメント

| ファイル | 内容 |
| --- | --- |
| [INVENTORY.md](./INVENTORY.md) | 元リポジトリ 156 プロジェクトの棚卸しと移植ロードマップ(Wave 1/2) |
| [PORTING.md](./PORTING.md) | 移植規約(FW 対応表、テスト・トレース・評価・Bicep の必須要件、1サイクル手順) |
| [infra/shared.bicep](./infra/shared.bicep) | 共有基盤(Foundry リソース+プロジェクト+モデル+App Insights)。**課金あり・1回だけデプロイ** |
| [infra/docs/architecture.png](./infra/docs/architecture.png) | 共有基盤のアーキテクチャ図(各ポートの図は `ports/<port>/docs/architecture.png`。再生成手順は [tools/README.md](./tools/README.md)) |

## 進捗(Wave 1: #1-7 / Wave 2: #8-12 / Wave 3: #13-14 / 新規パターン: #15)

**実行ガイド(runbook):** 各ポートの実行手順と確認観点は `ports/<port>/docs/runbook.md`(人間用 HTML は同じディレクトリの `runbook.html`、全ラボの索引は [../runbooks.md](../runbooks.md))。**2026-10-06 に全ポートを agent-framework 1.20 / openai 3.24 で再検証**(オフライン 15 ポート計 829 件 passed。**ライブも Port 15 以外の 14 ポートで再実施** — 共有基盤 `baseName=mafp1006` を新規構築して並行実行し、検証後に削除。Port 15 はオフラインのみで、ライブ再実施は Entra 側の作成・権限付与を伴うため保留。改修点・ライブ結果は各 README の「検証結果(2026-10-06 …)」)。前回は 2026-09-29(1.19 / 3.20、オフラインのみ)。

| # | ポート | 元 | パターン | 実装 | オフラインテスト | Bicep | ライブスモーク | 学び記録 | 実行ガイド |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 共有基盤 | — | — | — | — | 済 | 2026-07-31 / 2026-09-30 / **2026-10-06**(`mafp1006`、gpt-5.4-mini 容量 100 で 14 ポートを並行ライブ)に構築し、検証後に削除(コスト停止。Bicep+スクリプトで再現可) | — | [runbook](./infra/docs/runbook.md) |
| 1 | trend-analysis | starter/ai_startup_trend_analysis_agent | 逐次WF | 済 | 済(9件) | 済 | 済(2026-10-06 再: CLI 30.5s・3 節そろう。既定サンプラーの間引きを `sampling_ratio=1.0` で解消) | [済](./ports/trend-analysis/README.md) | [runbook](./ports/trend-analysis/docs/runbook.md) |
| 2 | mixture-of-agents | starter/mixture_of_agents | 並列+集約 | 済 | 済(13件) | 済 | 済(2026-10-06 再: 4 並列の開始差 0.3s 以内・fan-in 順は定義順) | [済](./ports/mixture-of-agents/README.md) | [runbook](./ports/mixture-of-agents/docs/runbook.md) |
| 3 | research-handoff | starter/openai_research_agent | handoff | 済 | 済(31件) | 済 | 済(2026-10-06 再: 6 トピックとも期待ルート) | [済](./ports/research-handoff/README.md) | [runbook](./ports/research-handoff/docs/runbook.md) |
| 4 | corrective-rag | rag/corrective_rag | 補正ループ+AI Search | 済 | 済(42件。2026-10-06: 埋め込みを MAF の `OpenAIEmbeddingClient` に) | 済(AI Search Free+埋め込み) | 済(2026-10-06 再: 両経路+埋め込みスパン) | [済](./ports/corrective-rag/README.md) | [runbook](./ports/corrective-rag/docs/runbook.md) |
| 5 | travel-memory | memory/ai_travel_agent_memory | Foundry Memory | 済 | 済(25件) | 済 | 済(2026-10-06 再: 記憶往復 136.9s) | [済](./ports/travel-memory/README.md) | [runbook](./ports/travel-memory/docs/runbook.md) |
| 6 | github-mcp | mcp/github_mcp_agent | リモート MCP | 済 | 済(23件) | 済 | 済(2026-10-06 再: `static_headers` で初ライブ 12.1s) | [済](./ports/github-mcp/README.md) | [runbook](./ports/github-mcp/docs/runbook.md) |
| 7 | game-design-team | agent_teams/ai_game_design_agent_team | Swarm ハンドオフ | 済 | 済(30件) | 済 | 済(2026-10-06 再: 主実装 49s。HandoffBuilder 変種を初ライブ — 順序は正しいが本文欠落の崩れ方) | [済](./ports/game-design-team/README.md) | [runbook](./ports/game-design-team/docs/runbook.md) |
| 8 | data-analysis-ci | starter/ai_data_analysis_agent | Code Interpreter | 済 | 済(31件。2026-10-06: `include` で実行ログ・data URI 画像・アップロード削除) | 済 | 済(2026-10-06 再: 正答 3,225,050 / Electronics) | [済](./ports/data-analysis-ci/README.md) | [runbook](./ports/data-analysis-ci/docs/runbook.md) |
| 9 | critique-loop | advanced_llm/gpt_oss_critique_improvement_loop | 評価駆動ループ | 済 | 済(47件。2026-10-06: ルーブリックに `pass_threshold`) | 済 | 済(2026-10-06 再: **ルーブリック込みのクラウド評価が初めて完走**) | [済](./ports/critique-loop/README.md) | [runbook](./ports/critique-loop/docs/runbook.md) |
| 10 | db-routing-iq | rag/rag_database_routing | Foundry IQ | 済 | 済(56件) | 済(AI Search Basic。Free も選択可・ライブ確認済み) | 済(2026-10-06 再: Basic・**Free とも** 4 問正答) | [済](./ports/db-routing-iq/README.md) | [runbook](./ports/db-routing-iq/docs/runbook.md) |
| 11 | hn-briefing-hosted | always_on/hn_briefing | hosted agent+Routines | 済 | 済(60件。2026-10-06: foundry-hosting b261002・`--candidate` / `--promote`) | 済 | 済(2026-10-06 再: 候補→昇格・既存会話は作成時の版のまま・Routine の受付 8s・トレース本文は二重書き) | [済](./ports/hn-briefing-hosted/README.md) | [runbook](./ports/hn-briefing-hosted/docs/runbook.md) |
| 12 | claim-voice-live | voice/insurance_claim_live_agent_team | Voice Live | 済 | 済(77件) | 済 | 済(2026-10-06 再: 3 passed。移行経路 gpt-realtime-2.1-mini も通過 — Global 処理) | [済](./ports/claim-voice-live/README.md) | [runbook](./ports/claim-voice-live/docs/runbook.md) |
| 13 | services-agency | agent_teams/ai_services_agency | 通信グラフ制約(agent-as-tool) | 済 | 済(71件) | 済 | 済(2026-10-06 再: 深度上限の BLOCKED をライブで初観察。必須の相談は 12 件中 5 件しか発生せず) | [済](./ports/services-agency/README.md) | [runbook](./ports/services-agency/docs/runbook.md) |
| 14 | governed-agent | advanced_ai_agents/single_agent_apps/ai_agent_governance + multi_agent_apps/trust_gated_agent_team | ガバナンス(middleware 3 種+監査) | 済 | 済(71件) | 済 | 済(2026-10-06 再: デモ 4 件が期待ステータス・監査連鎖 OK) | [済](./ports/governed-agent/README.md) | [runbook](./ports/governed-agent/docs/runbook.md) |
| 15 | delegated-access-hosted | なし(新規パターン — hosted agent の OBO 公式手順 2026-09-28 に基づく) | 利用者の委任権限でのアクセス制御(アプリ管理 OBO+`x-client-*` 転送、判定点 APIM / MCP サーバーの比較) | 済 | 済(243件。2026-10-06: 方式 C〈toolbox 委任〉の設計メモと配線) | 済 | 済(2026-09-30: 方式 A / B × 利用者 2 人の出し分け+迂回 403+会話分離 404。検証後に全削除)。**2026-10-06 の再実施は保留**(Entra 側の作成・権限付与を伴うため利用者判断待ち) | [済](./ports/delegated-access-hosted/README.md) | [runbook](./ports/delegated-access-hosted/docs/runbook.md) |

## 実行の前提

1. **共有基盤デプロイ(課金発生。Wave 1 検証後に削除済み — 再実行時は新しい RG 名で)**: `az group create -n rg-maf-ports -l japaneast` → `az deployment group create -g rg-maf-ports -f infra/shared.bicep -p baseName=... modelName=... modelVersion=...`(モデルは [features/02-models.md](../../docs/survey/features/02-models.md) で現行の安価 GA モデルを確認して指定)
2. 各ポートは `uv sync` → `uv run pytest`(オフライン)→ `.env` 設定後 `uv run pytest -m live`(ライブスモーク)
3. 使わない期間は `az group delete -n rg-maf-ports` で全撤去可(ステートレス設計)

共有基盤の詳細な実行手順と確認観点(第 2 段 roles.bicep・RBAC 伝播待ち・`.env` への転記・soft delete の purge)は [infra/docs/runbook.md](./infra/docs/runbook.md)(人間用 HTML: `infra/docs/runbook.html`)。

## 関連

- 実装パターンの先行例: [labs/agentic-search-maf](../agentic-search-maf/)(Rust 製リサーチエージェントの MAF 移植。ScriptedAgent テストパターンの出典)
- Foundry 機能の可否判断: [docs/survey/features/](../../docs/survey/features/README.md)
