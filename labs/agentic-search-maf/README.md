# agentic-search-maf

`agentic-search-rs`(`~/devs/agentic-search-rs` にある Rust 製の自己評価型リサーチエージェント)を **Microsoft Agent Framework (MAF)** で書き直した学習ラボ。

元ツールと同じく、質問を与えるとエージェントが検索クエリを計画し、Web ページを収集・抽出したうえで、**鮮度・正確性・網羅性**を自己評価し、不足があれば追加検索を自律的に行う。最終成果物は出典付きの Markdown レポート。

**「同じ構成を MAF で実現できるか」の検討結果は [docs/maf-port-design.md](docs/maf-port-design.md) を参照。** 結論だけ言うと: コアのエージェントループは MAF の Workflow(循環グラフ)でそのまま実現でき、むしろ Rust 版で手書きしていた基盤(LLM 抽象・イベント配信・構造化出力)の多くがフレームワーク機能に置き換わる。再現できないのは gpui 製 macOS GUI と Rust 固有の非機能特性。

## ドキュメント

| ドキュメント | 内容 |
|---|---|
| [docs/architecture.md](docs/architecture.md) | **アーキテクチャ**(処理フロー・モジュール構成・終了条件・並列実行・拡張ポイント・技術選定) |
| [docs/maf-port-design.md](docs/maf-port-design.md) | Rust 版からの**移植の構成検討**(実現可否マトリクス・できないものと理由・意図的な変更) |
| [docs/maf-implementation-notes.md](docs/maf-implementation-notes.md) | **MAF 実装ナレッジ**(1.10 実測。API 差分の移行表・エラー対処クックブック・テスト戦略) |
| [docs/runbook.md](docs/runbook.md) | **実行ガイド**(オフライン/ローカル LLM/Azure の実行手順と確認観点。人間用 HTML: `docs/runbook.html`) |

## 元リポジトリとの対応

| Rust (agentic-search-rs) | Python (本ラボ) | 置き換え |
|---|---|---|
| `agent/mod.rs` の手書き while ループ | `workflow.py` | MAF Workflow(循環グラフ + 条件エッジ) |
| `llm/` の `LlmClient` trait + 自作 HTTP クライアント×3 | `llm.py` | MAF `OpenAIChatClient`(Responses: openai/azure)/ `OpenAIChatCompletionClient`(Chat Completions: ollama/claude)+ `Agent`×4 ロール |
| `llm/json.rs` の寛容 JSON 抽出 | `json_utils.py` + `response_format` | 構造化出力をネイティブ利用、寛容パースはフォールバックに降格 |
| `events.rs` の `EventSink` コールバック | `events.py` + `yield_output` | Workflow の intermediate output イベント |
| `search/`・`fetch/`(SSRF ガード含む) | `search.py`・`fetch/` | MAF に該当機能なし → 素の Python で忠実移植 |
| `agent/knowledge.rs`・`prompts.rs`・`config.rs`・`retry.rs` | 同名モジュール | ほぼ 1:1 移植 |
| `crates/cli` | `cli.py` | argparse |
| `crates/gui`(gpui / macOS) | **なし** | 移植不可(docs 参照)。代替は DevUI / trace JSONL |

## 必要環境

- Python 3.10+(開発時は 3.13。agent-framework-core **1.10.0** で実装、2026-09-29 に 1.19.0 / agent-framework-openai 1.14.4 / openai 3.20.0、2026-10-06 に **1.20.0** / agent-framework-openai 1.15.0 / openai 3.24.0 で再検証)
- 既定プロバイダーはローカル [Ollama](https://ollama.com/)(API コストゼロ)。`--provider` で claude / openai / azure に切替可能

## セットアップと実行

```sh
cd labs/agentic-search-maf
uv sync --extra dev          # uv.lock どおりに .venv を作る(Azure をキーなしで使うなら --extra azure も)

# ローカル LLM(既定・無料)
ollama serve
ollama pull llama3.2:3b

# 実行
.venv/bin/agentic-search-maf "調査したい質問" --output report.md --trace report.trace.jsonl

# Azure OpenAI / Microsoft Foundry Models を使う場合
export AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
export AZURE_OPENAI_API_KEY=...   # 省略すると Entra ID(DefaultAzureCredential。要 --extra azure と az login)
.venv/bin/agentic-search-maf "質問" --provider azure --model <deployment-name>
```

詳細な実行手順と確認観点は [docs/runbook.md](./docs/runbook.md)(人間用 HTML: `docs/runbook.html`)。

環境変数は Rust 版と同名(`AGS_LLM_PROVIDER` / `AGS_LLM_MODEL` / `AGS_SEARCH_PROVIDER` / `AGS_REPORT_LANGUAGE` / `AGS_MAX_CONCURRENT_PAGES` / `AGS_MAX_RETRIES` など)。検索プロバイダーは duckduckgo(既定・キー不要)/ searxng / serper。

## テスト

ネットワーク・LLM 不要で完走する(Rust 版と同じ方針。LLM ロールはスクリプト化したフェイクに差し替え)。

```sh
uv run pytest -q -W error::DeprecationWarning   # 非推奨 API の混入も検知
uv run ruff check . && uv run ruff format --check src/ tests/
```

ワークフローの統合テスト(`tests/test_workflow.py`)は Rust 版 `agent/mod.rs` のテストを移植したもので、「不足→追加検索→充足で終了」のループと「評価者が壊れてもレポートは失われない」フォールバックを実 MAF グラフ上で検証する。

## 構成

```
src/agentic_search_maf/
  workflow.py    エージェント本体: Planner → Gatherer → Evaluator ⇄(ループ)→ Reporter
  llm.py         チャットクライアント工場 + 4 ロールの Agent 生成
  schemas.py     構造化出力スキーマ(Plan / Extraction / Evaluation)+ 寛容パース
  prompts.py     全プロンプト(Rust 版から逐語移植)
  knowledge.py   KnowledgeStore(重複排除・訪問管理・ダイジェスト)
  events.py      進捗イベントのペイロード + trace JSONL(Rust 版と互換)
  search.py      SearchProvider(duckduckgo / searxng / serper)
  fetch/         SSRF ガード・リダイレクト再検証・Readability 抽出
  config.py      AGS_* 環境変数(Rust 版と同名)
  retry.py       指数バックオフ(一時障害のみ再試行)
  cli.py         CLI フロントエンド
```

## 検証結果(2026-10-06 ライブ — 初のエンドツーエンド実行)

Foundry の共有基盤(maf-ports の rg-maf-ports、gpt-5.4-mini GlobalStandard 容量 100)に `--provider azure` で接続(`AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` をシェルで export)。質問「Microsoft Agent Framework の最新リリースで何が変わったか」、`--max-iterations 2`。

- **結果**: 68.9 秒で完走(終了コード 0)。`done: 94 findings from 23 sources in 2 iteration(s) | scores: freshness 78, correctness 64, coverage 58`。`report.md`(8,922 バイト、出典付き本文+`## Self-assessment`)と trace JSONL(39 イベント。`plan_ready` → `query_started` → `page_processed` → `iteration_done` → `evaluation_done` の順)が出た
- **自己評価ループ**: iteration 1 で +53 findings、評価 72 / 68 / 74・`sufficient=False` → 評価者の追加クエリ 6 本で iteration 2(+41)、評価 78 / 64 / 58 で `--max-iterations` に達して終了。Known limitations に「python-1.20.0 と .NET のリリース変更が並立していて、どれを最新とみなすかが曖昧」と書き、本文も .NET 側の変更に寄った — 正確性 64 という自己採点と整合しており、**Reflection ループが自分の弱点(言語別リリースの混同)を言語化できている**
- **api-version(runbook §6 #9)**: Responses API への 27 リクエストすべてが `POST …/openai/v1/responses?api-version=preview` で **200**。`preview` 指定で問題は出なかったため**据え置き**(コード変更なし)。レスポンスヘッダーは `x-ms-served-model: gpt-5.4-mini-2026-03-17`・`x-ratelimit-limit-tokens: 100000`(容量 100 = 100K TPM)
- **検索の失敗に耐える**: DuckDuckGo が 11 クエリ中 3 回 HTTP 202(レート制限)を返し、1 ページは 403 でスキップされたが、ワークフローは止まらず残りの結果でレポートを書いた(クエリ・ページ単位の失敗は警告を出して次へ進む設計どおり)
- 本ラボはトレースを App Insights に送らない(trace JSONL のみ)。ollama / claude / openai プロバイダーは未実行

## 検証結果(2026-10-06 最新化チェック)

オフラインの確認(ライブは上の「検証結果(2026-10-06 ライブ — 初のエンドツーエンド実行)」)。

- **依存更新**(`uv lock --upgrade`): agent-framework-core 1.19.0 → **1.20.0**、agent-framework-openai 1.14.4 → **1.15.0**、openai 3.20.0 → **3.24.0**、azure-identity 1.25.3 → **1.26.0**(extra `azure`)、msgspec 0.21.1 → 0.22.0、ruff 0.16.9 → 0.16.10。core 1.20 の新しい推移依存として `regex` が入る。pyproject の下限を検証版(`agent-framework-core>=1.20` / `agent-framework-openai>=1.15` / `azure-identity>=1.26`)に引き上げ。
- **テスト**: `uv run pytest -W error::DeprecationWarning` → **51 passed**(既存 50 + 新規 1)。ruff check / format clean。Workflow 側(`Agent`・`ChatOptions`・`WorkflowBuilder(start_executor=, output_from=, intermediate_output_from=)`・`add_edge(..., condition=)`・`run(stream=True)`・`ev.type`)は**変更不要**。
- **新規テスト(1.15 の修正の固定)**: agent-framework-openai 1.15 の「Azure 経路に OpenAI のメタデータ既定を混ぜない」修正で、`--provider azure`(`azure_endpoint=` 経路)のリクエストに `OPENAI_ORG_ID` / `OPENAI_PROJECT_ID` 由来の `OpenAI-Organization` / `OpenAI-Project` ヘッダーが付かなくなった。HTTP 層(openai 3.x の httpx2)を差し替えて実際の送信ヘッダーを見ると、1.14.4 では両ヘッダーが Azure エンドポイントへ送られていた(開発機に OpenAI 直の環境変数を置いたまま Azure を叩くと、無関係な組織 ID が Azure 側に渡っていた)。`tests/test_llm.py` の `test_azure_route_does_not_forward_openai_org_headers` で固定(1.14.4 では落ちることを確認)。認証ヘッダーは `api-key` のみ(`Authorization` なし)。
- **観察(要ライブ確認)**: `azure_endpoint=` 経路の `OpenAIChatClient` は既定で **`?api-version=preview`** を付けて `/openai/v1/responses` を呼ぶ(agent-framework-openai の `DEFAULT_AZURE_OPENAI_RESPONSES_API_VERSION = "preview"`。1.14.4 も同じ)。Learn の API ライフサイクル(api-version-lifecycle、2026-10-06 確認)は「v1 GA API では `api-version` は必須でない」「プレビュー機能は機能別のヘッダーで opt-in」としており、2026-09-29 の「api-version 不要」は Azure 側の仕様としては正しいが、MAF はプレビュー指定を付けて送っている。`api_version=` 引数で別の値に上書きはできるが、外すことはできない(なお docstring にある環境変数 `AZURE_OPENAI_API_VERSION` は 1.15.0 では効かない — 既定値 `preview` が明示引数として設定読み込みに渡るため。2026-10-06 実測)。maf-ports の各ポートは `base_url=` 経路で api-version を付けない。→ 同日のライブで `preview` 付きのまま 27 リクエストすべて 200 だったため据え置き(コードは変更していない)。
- **変更不要**: 1.20 で `SwitchCaseEdgeGroup` の条件関数の例外が伝播するようになったが、本ラボは `add_edge(..., condition=)`(isinstance 判定のみ)で影響なし。
- **今後の選択肢**: `agent-framework-anthropic` / `agent-framework-ollama` は 2026-10-06 時点でも **1.0.0b261002(ベータ)** — GA まで互換エンドポイント経由のまま(候補として記録のみ)。

## 検証結果(2026-09-29 最新化チェック)

オフライン(ネットワーク・LLM 不要)のみ。実 LLM でのエンドツーエンド実行は初版から未実施(ライブ未検証)。

- **依存更新**: agent-framework-core 1.10.0 → **1.19.0**、agent-framework-openai 1.10.0 → **1.14.4**、openai 2.44.0 → **3.20.0**、readability-lxml 0.8.4.1 → 0.9、pytest 9.1.1 / pytest-asyncio 1.4.0 / ruff 0.16.9。`uv.lock` を新規作成(以前は `uv pip install -e` 運用でロックなし)。pyproject の下限を検証版に引き上げ。
- **テスト**: `uv run pytest -W error::DeprecationWarning` → **50 passed**(既存 44 + 新規 `tests/test_llm.py` 6)。ruff check / format clean。MAF 1.10→1.19 の破壊的変更・非推奨警告は本ラボの使用 API(`Agent`・`ChatOptions`・`WorkflowBuilder(start_executor=, output_from=, intermediate_output_from=)`・`run(stream=True)`・`ev.type`)には無し → Workflow 側は**変更不要**。
- **改修 1(不具合修正)**: ollama / claude プロバイダーを `OpenAIChatClient` → `OpenAIChatCompletionClient` に変更。`OpenAIChatClient` は 1.10 の時点から **Responses API** のクライアントで、Anthropic の OpenAI 互換層は Chat Completions しか持たない(`/v1/responses` なし。出典: https://platform.claude.com/docs/en/api/openai-sdk )。初版は実 LLM 未実行だったため潜在していた。Ollama も `response_format` の実績がある Chat Completions 側に寄せた。openai / azure は Responses のまま。
- **改修 2(不具合修正)**: azure プロバイダーで `AZURE_OPENAI_API_KEY` 未設定時に Entra ID(`DefaultAzureCredential`)を明示的に渡すようにした。旧コメントは「MAF が Entra ID を解決する」としていたが、agent-framework-openai はキーも credential もないと `SettingNotFoundError` を投げる(1.14.4 の `_shared.py` で確認)。`azure-identity` は optional extra `azure` に分離。
- **変更不要**: Azure 経路は `<endpoint>/openai/v1/` の Responses API(v1 API は GA、api-version 不要)で現行どおり。既定モデル名は Azure ではデプロイ名を指定する方式のため影響なし。
- **今後の選択肢**: `agent-framework-anthropic` / `agent-framework-ollama`(いずれも 2026-09 時点でベータ)が GA したら、互換エンドポイント経由をネイティブクライアントに置き換えられる(構造化出力の無効化フォールバックが不要になる可能性)。

