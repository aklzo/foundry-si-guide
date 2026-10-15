# labs 実行ガイド索引

> **最終更新:** 2026-10-06(全ラボを agent-framework 1.20 / openai 3.24 で再検証し、**Port 15 以外はライブも再実施**。foundry-probes に probe 11〈トレース本文の振り分け〉を追加、cu-video-rag に 4 本のスモーク手順を追加)/ 2026-09-30(Port 15 delegated-access-hosted を追加し、同日ライブ検証。foundry-probes に probe 10 を追加)/ 2026-09-29(全ラボに実行ガイドを新設。同日に全ラボを agent-framework 1.19 / openai 3.20 系でオフライン再検証)
> **正は各 `docs/runbook.md`(Markdown)。** 人間用 HTML(同じディレクトリの `runbook.html`、本ページは `runbooks.html`)は `python3 labs/tools/build_runbooks.py` で生成する。HTML は直接編集しない。

各ラボ・ポートの「どう動かすか」と「何が確認できれば OK か」をまとめた実行ガイドの一覧。設計判断や移植の学びは各 README にあり、実行ガイドはそこから**手順と確認観点だけ**を切り出している。

## 使い方

- **HTML で読む**: ブラウザで各 `runbook.html` を開く。「確認観点」の表と一覧のチェックボックスは**ブラウザ内に保存**される(ページ右上に「確認済み n / N」)。確認作業の途中経過用で、共有はされない
- **まずオフライン**: どのラボも Azure なしのオフラインテスト(またはオフライン検証)から始められる。ライブ実行は Azure リソースの再作成が必要で**課金が発生する**(検証後に全リソースを削除済みのため)
- **Markdown と HTML の同期確認**: `python3 labs/tools/build_runbooks.py --check`(差分があれば終了コード 1)

## 共通の前提

| 項目 | 内容 |
| --- | --- |
| ツール | [uv](https://docs.astral.sh/uv/)(Python は uv が取得)。ライブ実行は Azure CLI(`az login`)も |
| Azure | maf-ports は**共有基盤を先に作る**([共有基盤の実行ガイド](./maf-ports/infra/docs/runbook.md))。他のラボは各ラボの `infra/` で個別に作る。検証後は RG ごと削除する運用(ステートレス設計) |
| 接続情報 | maf-ports は `labs/maf-ports/.env`(雛形 `.env.example`。git 管理外)。他のラボは各ラボの README / 実行ガイドを参照 |
| 検証状態 | **2026-10-06 に全ラボを最新依存(agent-framework 1.20 / openai 3.24 / azure-ai-projects 2.8.0〈MAF の Foundry 連携を使うポートは 2.7.0〉)で再検証**: オフラインは全件 passed、ライブは maf-ports 14 ポート(Port 15 を除く)・agentic-search-maf(初)・foundry-probes 11 本・cu-video-rag(4 本のスモーク)で実施し、検証後に全リソースを削除。**Port 15 のライブ再実施は保留**(Entra のアプリ登録・テスト用ユーザー・権限付与を伴うため利用者判断待ち。前回ライブは 2026-09-30) |

## 一覧

### maf-ports(awesome-llm-apps の MAF + Foundry 移植 14 パターン+新規パターン 1)

| # | 対象 | パターン | Azure 固有リソース(共有基盤以外) | オフライン検証 | 実行ガイド |
| --- | --- | --- | --- | --- | --- |
| 0 | 共有基盤 | Foundry+プロジェクト+モデル+App Insights | —(これ自体が共有基盤) | `az bicep build` | [runbook](./maf-ports/infra/docs/runbook.md) |
| 1 | trend-analysis | 逐次ワークフロー | なし | 9 passed | [runbook](./maf-ports/ports/trend-analysis/docs/runbook.md) |
| 2 | mixture-of-agents | 並列+集約(fan-out / fan-in) | なし | 13 passed | [runbook](./maf-ports/ports/mixture-of-agents/docs/runbook.md) |
| 3 | research-handoff | ルーティング(構造化出力+switch-case) | なし | 31 passed | [runbook](./maf-ports/ports/research-handoff/docs/runbook.md) |
| 4 | corrective-rag | 補正ループ RAG | AI Search(Free)+埋め込みデプロイ | 42 passed | [runbook](./maf-ports/ports/corrective-rag/docs/runbook.md) |
| 5 | travel-memory | Foundry Memory | Memory ストア(スクリプトで作成) | 25 passed | [runbook](./maf-ports/ports/travel-memory/docs/runbook.md) |
| 6 | github-mcp | リモート MCP | なし(GitHub PAT) | 23 passed | [runbook](./maf-ports/ports/github-mcp/docs/runbook.md) |
| 7 | game-design-team | Swarm 型ハンドオフ | なし | 30 passed(orchestrations extra 込み) | [runbook](./maf-ports/ports/game-design-team/docs/runbook.md) |
| 8 | data-analysis-ci | Code Interpreter | なし | 31 passed | [runbook](./maf-ports/ports/data-analysis-ci/docs/runbook.md) |
| 9 | critique-loop | 評価駆動ループ+クラウド評価 | なし(評価はプロジェクト上) | 47 passed | [runbook](./maf-ports/ports/critique-loop/docs/runbook.md) |
| 10 | db-routing-iq | Foundry IQ(ナレッジベース) | AI Search(Basic。Free も可 — 2026-10-06 ライブ確認)+ナレッジベース | 56 passed | [runbook](./maf-ports/ports/db-routing-iq/docs/runbook.md) |
| 11 | hn-briefing-hosted | hosted agent+Routines(本番リリース手順 `--candidate` / `--promote`) | hosted agent・Routine | 60 passed | [runbook](./maf-ports/ports/hn-briefing-hosted/docs/runbook.md) |
| 12 | claim-voice-live | Voice Live | なし(マネージドモデル) | 77 passed | [runbook](./maf-ports/ports/claim-voice-live/docs/runbook.md) |
| 13 | services-agency | 通信グラフ制約(agent-as-tool) | なし | 71 passed | [runbook](./maf-ports/ports/services-agency/docs/runbook.md) |
| 14 | governed-agent | middleware によるガバナンス・監査 | なし | 71 passed | [runbook](./maf-ports/ports/governed-agent/docs/runbook.md) |
| 15 | delegated-access-hosted | hosted agent × 利用者の委任権限(アプリ管理の OBO)で文書・基幹 API を制御。判定点 APIM と MCP サーバー自身を比較 | Container Apps(MCP サーバー 2 系統)+APIM Consumption+AI Search Free+ACR / Entra アプリ登録 2 つ・カスタムロール | 243 passed(ライブ 2026-09-30 済。2026-10-06 の再実施は保留) | [runbook](./maf-ports/ports/delegated-access-hosted/docs/runbook.md) |

### その他の検証ラボ

| 対象 | 内容 | オフライン検証 | 実行ガイド |
| --- | --- | --- | --- |
| agentic-search-maf | 自己評価型リサーチエージェント(Rust 版の MAF 移植。ScriptedAgent テストパターンの出典) | 51 passed(2026-10-06 に初ライブ) | [runbook](./agentic-search-maf/docs/runbook.md) |
| foundry-probes | maf-ports に乗らなかった Foundry 機能 11 本の挙動確認 probe(10 = hosted agent の版更新と会話の継続 — `--scenario release` で公式のリリース手順どおりに再測定、11 = トレース本文の `AppGenAIContent` 振り分け。2026-10-06 に全本ライブ) | 静的検証(py_compile・ruff・SDK シグネチャ照合) | [runbook](./foundry-probes/docs/runbook.md) |
| cu-video-rag | Content Understanding 動画 × AI Search × RAG の精度検証(2026-10-06: 4 本のスモーク `scripts/run_smoke.sh` を追加しライブ通過) | コーパス検証+オフライン指標の再計算(2026-09-03 版とバイト一致) | [runbook](./cu-video-rag/docs/runbook.md) |

## 2026-10-06 の最新化+ライブ再検証で変わったこと(要点)

- **依存**: agent-framework-core 1.19 → **1.20**、agent-framework-openai → 1.15、openai 3.20 → **3.24**、azure-ai-projects 2.7 → **2.8.0**(MAF の Foundry 連携 `agent-framework-foundry` 1.14 を使う Port 11・15 は `<2.8.0` の制約で 2.7.0)、`agent-framework-foundry-hosting` → 1.0.0b261002([BREAKING])。`mcp<2` は MAF 1.20 でも必要。オフラインは 15 ポート計 **829 件**+agentic-search 51 件すべて passed
- **GA 機能・新 API による簡素化**: 採用 — Port 4 の埋め込みを MAF の `OpenAIEmbeddingClient` に(自前ラッパー削除・埋め込みもスパンに出る)、Port 11 に公式の本番リリース手順(`--candidate` / `--promote`)、Port 10 の Bicep に `searchSku`(Free でも Foundry IQ が動くことをライブ確認)。見送り(理由は各 README)— toolbox 経由の委任(Port 15 方式 C: MAF 側がプレリリース+ブラウザ同意)、MAF ホスティングの要求ごとのファクトリ(Port 15: ヘッダーが届かない)、native workflow hosting(Port 11)、ネイティブ承認(Port 14)、HandoffBuilder 1.3(Port 7)、voice agents(Port 12: preview)、合成評価器(Port 9: preview)
- **ライブで直したもの**: 全ポートのトレースに `sampling_ratio=1.0`(azure-monitor-opentelemetry の既定サンプラー 5 spans/秒でスパンが間引かれていた)/ Port 8 の Code Interpreter(`include` で実行ログ・data URI の画像・アップロードの削除)/ Port 9 のルーブリック評価(`pass_threshold` 必須 — 初めて完走)/ Port 11 の同一内容の再デプロイ(既存の版が返る)/ probe 09(`sampling_rate` は百分率 — 自動ランが出なかった真因)/ cu-video-rag のコスト集計(CU usage の新費目 cached-input)
- **ライブで分かったこと(survey 還元済み)**: トレースの会話本文は `AppDependencies` と `AppGenAIContent` の二重書き(probe 11・Port 11)/ hosted agent の版束縛は構成で結果が割れた(Port 11 = 作成時の版、probe 10 = 休止明けは現行の版)/ 応答の `agent_reference.version` は答えた版ではない / Routine の応答は開発者の ID で読めない(403)など。詳細は [docs/tech-selection-guide.md §6](../docs/tech-selection-guide.md)

## 2026-09-29 の最新化チェックで変わったこと(要点)

- **依存**: agent-framework-core 1.12〜1.13 → **1.19**、openai 2.5x → **3.20**(cu-video-rag は langchain 0.3 系の制約で openai 2.x のまま)。`mcp<2` は MAF 1.19 自身の要求で維持。`agent-framework-foundry` 1.13.1 は `azure-ai-projects<2.7.0` を要求するため、hn-briefing-hosted は 2.6.1 止まり
- **コード改修**: Routines の `Foundry-Features: Routines=V1Preview` ヘッダーを削除(Port 11。Routines は GA)/ MCP の認証ヘッダーを MAF 1.19 の `static_headers` に移行(Port 6・10)/ Foundry IQ の Search API を `2026-08-01-preview` に(Port 10)/ hosted agent のコンテナ依存を明示ピン(Port 11)/ Claude・Ollama を Chat Completions クライアントに(agentic-search-maf の潜在バグ)/ 継続評価 probe を公式の形に修正(foundry-probes 09、要再実測)
- **記述の訂正**: AI Search Free でもセマンティックランカーの無料枠が使える(Port 4)/ `AgentThread` → `AgentSession`(Port 13)ほか。詳細は各 README の「検証結果(2026-09-29 最新化チェック)」
- **アーキ図**: 各ポートの `docs/architecture.png` を日本語+処理番号の v2 スタイルに更新(ヘルパーは [tools/README](./maf-ports/tools/README.md))
