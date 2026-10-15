# foundry-probes 実行ガイド

> **対象:** `labs/foundry-probes/`(Foundry 機能の挙動確認 probe 11 本。アプリではなく「観点ごとにリクエストを投げて生の応答を記録する」ラボ)
> **最終確認:** **ライブ 2026-10-06**(01〜11 を新規 RG rg-foundry-probes・japaneast・main.bicep〈router 込み〉で再実測。依存 openai 3.24.0 / azure-ai-projects 2.8.0 / azure-identity 1.26.0。09 の真因を特定して修正、10 は release シナリオ 3 回、11 を新設。RG 削除・purge 済み — 再デプロイ手順は §5)/ オフライン 2026-10-06(自動テストなし。11 本+probe 10 の agent の `py_compile`・`ruff check` clean・SDK 呼び出しの AST シグネチャ照合で 122 呼び出し不一致 0・`az bicep build` 3 本 OK)/ 過去のライブ: 01〜09 は 2026-08-04(openai 2.53.0 / azure-ai-projects 2.4.0)、10 は 2026-09-30(専用の最小基盤)
> **正は本 Markdown。** 人間用 HTML(同じディレクトリの `runbook.html`)は `python3 labs/tools/build_runbooks.py` で生成する(HTML は直接編集しない)。発見の一次記録は各 probe の `NOTES.md`、一覧と検証対象外の理由は [README](../README.md)。

## 1. このラボで確かめること

- maf-ports の 13 ポートに乗らなかった Foundry 機能(Conversations・prompt agents・File Search・Web search・Model router・Structured outputs・ガードレール・埋め込みのルーティング・継続評価・hosted agent の版更新と会話の継続)が、**単純な入力に対して実際にどう振る舞うか**。
- 各 probe は観点(A, B, C…)ごとに「リクエスト → 応答の要点」を対で標準出力に出す。**失敗(`!!` 行)も観察結果**で、スクリプトは例外で止まらず次の観点に進む。
- 出力(`logs/<probe>.log`)が `NOTES.md` の根拠になる。再実測では「NOTES の発見と同じ形が出るか / 変わったか」を見る。

## 2. 構成

図(`architecture.png`)は本ラボには未作成(probe はクライアントから Foundry の各 API を直接叩くだけで、構成要素間の流れがない)。

```text
probes/NN-*/probe.py ──(Entra ID: az login / DefaultAzureCredential)──┬─▶ プロジェクト openai/v1  {project}/openai/v1        … 01〜07, 09
                                                                      ├─▶ エージェントエンドポイント {project}/agents/<name>/endpoint/protocols/openai … 02, 09
                                                                      ├─▶ プロジェクト REST(agents / evaluation_rules / sessions) … 02, 09, 10
                                                                      └─▶ アカウント openai/v1  https://<foundry>.openai.azure.com/openai/v1 … 01(A), 08
```

| コンポーネント | 役割 | 課金 |
| --- | --- | --- |
| probe スクリプト(ローカル、`uv run python ...`) | 観点別リクエストと結果表示 | なし |
| Foundry リソース `aif-<baseName>` + プロジェクト `probes`(`infra/main.bicep`) | 全 probe の接続先 | リソース自体は無料 |
| モデルデプロイ gpt-5.4-mini(GlobalStandard, cap 10) | 01〜07, 09 の推論 | トークン従量 |
| model-router デプロイ(`deployRouter=true` 時) | 01(G)・05 | ルーティング先モデルの単価で従量 |
| text-embedding-3-small(CLI で追加) | 08 | トークン従量 |
| File Search のベクトルストア | 03(probe 内で作成・削除) | ストレージ従量(削除忘れ注意) |
| Web search ツール | 04 | ツール呼び出し単位の別課金・**DPA 対象外** |
| Log Analytics + Application Insights(接続済み) | 09 の継続評価結果・手動 KQL | 取り込み従量 |
| hosted agent `probe-version-continuity`(10 が作成。v1〜v3・コードデプロイ)/ `probe-release-binding`(10 の `--scenario release`。v1〜v2、最後に削除) | 10 | セッションの実行中の CPU / メモリ(モデルは呼ばない)。休止中は課金なし |

## 3. 前提

| 区分 | 必要なもの | 備考 |
| --- | --- | --- |
| ツール | uv(Python 3.11 以上。uv が取得)、Azure CLI(`az login` 済み) | オフライン確認は uv だけ |
| Azure | `infra/main.bicep` + `infra/roles.bicep` + 埋め込みデプロイ(§5.1) | 課金あり。使い終わったら RG ごと削除 |
| 権限 | 署名ユーザーに Cognitive Services OpenAI User + Foundry User(旧 Azure AI User)— main.bicep が付与。プロジェクト/アカウント MI に同 2 ロール — roles.bicep が付与(09 の継続評価の前提) | RBAC 伝播に 5〜15 分 |
| データ取り扱い | 04 は検索クエリが Microsoft のコンプライアンス境界外(Bing)へ出る。05 は既定で非 OpenAI モデル(Grok 等)へ流れる | 機微データを入力しない |

環境変数(`labs/foundry-probes/.env`。雛形は `.env.example`。**ライブ実行時のみ必要**。`.env` は git 管理外):

| 変数 | 用途 | 取得元 |
| --- | --- | --- |
| `FOUNDRY_PROJECT_ENDPOINT` | プロジェクト経由の openai client / agents / evaluation_rules | main.bicep 出力 `projectEndpoint` |
| `FOUNDRY_OPENAI_V1_ENDPOINT` | アカウント直下の openai/v1(01 の A、08) | main.bicep 出力 `openaiV1Endpoint` |
| `FOUNDRY_MODEL` | 推論モデルのデプロイ名 | main.bicep 出力 `modelDeploymentName`(例 `gpt-5.4-mini`) |
| `FOUNDRY_API_KEY` | 空なら Entra ID(既定・推奨)。アカウント openai/v1 にだけ効く | ポータルのキー(通常は空のまま) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | probe のコードは使わない(手動 KQL 用のメモ) | main.bicep 出力 `appInsightsConnectionString` |
| `FOUNDRY_ROUTER_DEPLOYMENT` | 05 のルーターのデプロイ名(既定 `model-router`。2026-10-06 追加) | ルーティング先を絞った別名デプロイと比べるときだけ設定 |

## 4. オフライン確認(Azure 不要・無料)

probe はライブ専用スクリプトで、自動テスト(pytest)はない。オフラインでは「現行 SDK で読み込めて、呼び出しの形が合っているか」までを確認する。

```bash
cd labs/foundry-probes
uv sync
uv run ruff check .                                          # 期待: All checks passed!
for f in probes/*/probe.py; do uv run python -m py_compile "$f" || echo "NG $f"; done   # 期待: 何も出ない
uv run python -c "from foundry_probes.common import Settings, make_project_client; print('import ok')"
```

オフラインで確認済みの事項(2026-09-29、2026-10-06 に openai 3.24.0 / azure-ai-projects 2.8.0 で再確認):

- [ ] 全 probe の `client.<...>.create(...)` 等の呼び出し先・キーワード引数・`azure.ai.projects.models` のフィールドが openai 3.24.0 / azure-ai-projects 2.8.0 のシグネチャに存在する(AST 照合で 122 呼び出し不一致 0。08 D の `get_openai_client(base_url=...)` は文書化された `**kwargs` 経由)
- [ ] `uv run python probes/10-hosted-version-continuity/probe.py --help` に `--scenario {continuity,release}` が出る(既定は 2026-09-30 実測の continuity)
- [ ] `get_openai_client()` → `{project}/openai/v1/`、`get_openai_client(agent_name=...)` → `{project}/agents/<name>/endpoint/protocols/openai/` を向く(`Settings` にダミー値を入れて生成した client の `base_url` で確認)
- [ ] 09 の `EvaluationRule(...)` がワイヤ形式 `{"eventType": "responseCompleted", "filter": {"agentName": ...}, "action": {"type": "continuousEvaluation", ...}}` にシリアライズされる
- [ ] `az bicep build --file infra/main.bicep --stdout > /dev/null`(roles.bicep も)が警告なしで通る

## 5. ライブ実行(Azure 必要・課金あり)

### 5.1 デプロイ

```bash
cd labs/foundry-probes
az group create -n rg-foundry-probes -l japaneast
# baseName の使用済み: fprobes(2026-08-04)/ fprobes1006(2026-10-06)。どちらも purge 済みだが、別名で作ると確実
# (以下の fprobes は例。roles.bicep・埋め込み・片付けのコマンドも同じ名前にそろえる)
az deployment group create -g rg-foundry-probes -f infra/main.bicep \
  -p baseName=fprobes modelName=gpt-5.4-mini modelVersion=2026-03-17 \
     userObjectId=$(az ad signed-in-user show --query id -o tsv) \
     deployRouter=true routerVersion=2025-11-18
# 第 2 段: MI へのロール(principalId ローテーション対策で分離)
PID=$(az rest --method get --url "https://management.azure.com$(az cognitiveservices account show -n aif-fprobes -g rg-foundry-probes --query id -o tsv)/projects/probes?api-version=2025-06-01" --query identity.principalId -o tsv)
AID=$(az cognitiveservices account show -n aif-fprobes -g rg-foundry-probes --query identity.principalId -o tsv)
az deployment group create -g rg-foundry-probes -f infra/roles.bicep -p baseName=fprobes accountPrincipalId=$AID projectPrincipalId=$PID
# 08 用の埋め込みデプロイ
az cognitiveservices account deployment create -n aif-fprobes -g rg-foundry-probes \
  --deployment-name text-embedding-3-small --model-name text-embedding-3-small --model-version 1 \
  --model-format OpenAI --sku-name GlobalStandard --sku-capacity 10
```

`main.bicep` の出力(`projectEndpoint` / `openaiV1Endpoint` / `modelDeploymentName`)を `.env` に転記する(`cp .env.example .env` してから編集)。

### 5.2 実行

```bash
uv sync --extra maf                                   # maf extra = 11 の発生源 (c)(MAF のクライアント側スパン)
./run_all.sh                                          # 全 11 本を順に実行し logs/<probe>.log に保存(tee で画面にも出る。10 は continuity シナリオ)
# 10 だけを専用の最小基盤で動かす場合(モデル・App Insights なし。所要 10 分前後 = 版のデプロイ 3 回+休止待ち 3 分)
az group create -n rg-foundry-probes-p10 -l japaneast
az deployment group create -g rg-foundry-probes-p10 -f probes/10-hosted-version-continuity/infra.bicep \
  -p baseName=<英小文字数字> userObjectId=$(az ad signed-in-user show --query id -o tsv) --query properties.outputs.projectEndpoint.value -o tsv
# Foundry User の反映に約 5 分かかる(hosted agent の作成に要る)
FOUNDRY_PROJECT_ENDPOINT=<上の出力> uv run python probes/10-hosted-version-continuity/probe.py 2>&1 | tee logs/10-hosted-version-continuity.log
uv run python probes/05-model-router/probe.py         # 1 本だけ(例)
# 10 の再測定(公式のリリース手順で休止明けの版を確かめる。2026-10-06 追加・約 10〜15 分)
FOUNDRY_PROJECT_ENDPOINT=<上の出力> uv run python probes/10-hosted-version-continuity/probe.py --scenario release \
  2>&1 | tee logs/10-hosted-version-continuity-release.log
#   条件を変える: --idle-timeout 900(サービス既定)--wait 60(stop_session だけで休止を作り、B を起動中の対照にする)
#   --route-mode preserve(既存のエンドポイント設定を保ってセレクタだけ差し替える = maf-ports Port 11 と同じ形)
# 05 をルーティング先を絞ったデプロイで比べる場合(任意。デプロイ API 2025-10-01-preview の routing ブロック)
FOUNDRY_ROUTER_DEPLOYMENT=<subset のデプロイ名> uv run python probes/05-model-router/probe.py
# 11(トレース本文の振り分け。main.bicep の基盤が要る。最大 20 分ポーリング)
LOG_ANALYTICS_WORKSPACE_ID=<出力 logAnalyticsWorkspaceId> LOG_ANALYTICS_WORKSPACE_RESOURCE_ID=<出力 logAnalyticsWorkspaceResourceId> \
  uv run --extra maf python probes/11-trace-content-routing/probe.py 2>&1 | tee logs/11-trace-content-routing.log
```

2026-10-06 の実測では `.env` を置かず、値を書いたファイルを `uv run --env-file <ファイル>` で渡した(App Insights の接続文字列は `;` を含むので、シェルで `source` するなら値を引用符で囲む)。

出力の読み方: `== <観点>` が見出し、`--- <ラベル>` の下が観察値(長文は `…(全N文字)` で切り詰め)、`!! <例外型>: <内容>` はその観点で返ったエラー(観察対象。スクリプトは続行する)。

## 6. probe 別の確認ポイント

各節の「期待(2026-08-04 実測)」は NOTES の記録。**値(id・トークン数・ルーティング先)は実行ごとに変わる**ので形で比べる。

### 6.1 01 Conversations API

- **確かめること**: サービス側会話状態の使えるサーフェス、多ターン継続、items の粒度、`store=False` との併用、別モデルでの継続、エラー形。
- **コマンド**: `uv run python probes/01-conversations/probe.py`
- **出力で見る所**: A で `!! NotFoundError ... 404`(アカウント直下は不可)、A' で `conv_...` が作成される / C の turn2 が「青」/ F が `items 件数: 0` / G の「実際に使われたモデル」/ H が 400 `Malformed identifier`。
- **主要な発見**: Conversations は**プロジェクト経由のみ**。会話に TTL フィールドはなく明示削除まで残る。`store=False` を conversation と同時指定するとそのターンは会話に残らない(エラーも出ない)。
- 詳細: [01 NOTES](../probes/01-conversations/NOTES.md)

### 6.2 02 Prompt agents

- **確かめること**: `agents.create_version` の版採番、エージェントエンドポイント経由の呼び出し、conversation との組み合わせ、function ツールの返り先、`instructions` 上書き、削除。
- **コマンド**: `uv run python probes/02-prompt-agents/probe.py`
- **出力で見る所**: A の `"id": "probe-prompt-agent:1"` と `instance_identity`(エージェントごとの Entra ID)/ B で `v1.version=1 -> v2.version=2` / D が川柳で返る(既定は最新版)/ F の最終 item が `function_call` / G が `!! BadRequestError ... Not allowed when agent is specified`。
- **主要な発見**: 版は自動採番の upsert(typo が新エージェントになる)。function ツールはクライアント実行ループ。呼び出し時の `instructions` 上書きは 400。エンドポイントの既定ルーティングは「常に最新版」(公式 configure-agent 2026-09-11 版とも一致)。
- 詳細: [02 NOTES](../probes/02-prompt-agents/NOTES.md)

### 6.3 03 File Search + ベクトルストア

- **確かめること**: ファイル登録・ベクトルストアのチャンク既定値・インデックス待ち・根拠付き回答と引用・明示 TTL・削除時のファイル残存。
- **コマンド**: `uv run python probes/03-file-search/probe.py`
- **出力で見る所**: B の `chunking_strategy` が `max_chunk_size_tokens: 800 / chunk_overlap_tokens: 400` / C が数秒で `status=completed` / D が「3 年間」/ E に `file_citation` / F に `expires_at` が入る / G で「store 削除後もファイルは残る」。
- **主要な発見**: 埋め込みモデルの自前デプロイ不要(サービス管理・変更不可)。自作ストアの既定は無期限。**ストアを消してもファイルは残る**ので `files.delete` を別に行う(probe は最後に削除する)。
- 詳細: [03 NOTES](../probes/03-file-search/NOTES.md)

### 6.4 04 Web search ツール

- **確かめること**: ツール型名、`web_search_call` の中身(外に出た検索クエリ)、引用の形、`tool_choice` 強制。
- **コマンド**: `uv run python probes/04-web-search/probe.py`(**DPA 対象外・別課金。4 リクエストのみ**)
- **出力で見る所**: A で `type='web_search' -> 受理` / B の `action.queries`(モデルが組み立てた実クエリ)/ C の `url_citation` / D で挨拶だけでも `output types=['web_search_call', 'message']`。
- **主要な発見**: 接続リソース不要でツール指定だけで動く。`action.queries` が「コンプライアンス境界外へ出た文字列」の実体。`tool_choice` 強制は無駄な検索と課金を生む。
- 詳細: [04 NOTES](../probes/04-web-search/NOTES.md)

### 6.5 05 Model router

- **確かめること**: japaneast での動作、難易度別のルーティング先、usage の見え方、`temperature` の受理。
- **コマンド**: `uv run python probes/05-model-router/probe.py`(要 `deployRouter=true`)
- **出力で見る所**: B/C の各行 `-> model=<実モデル名>`(2026-08-04 は 5 件中 4 件が `grok-4-1-fast-reasoning`、挨拶のみ `gpt-5-mini-2025-08-07`)/ D の `reasoning_tokens` / E が `temperature=0.2 -> OK` / F(2026-10-06 追加)の `model_selection_details`(`mode`・`routing_trace` が付けばルーティングの試行を監査できる。付かなければ「なし」と出る — プレビューのため)。2026-10-06 の実測: B/C は gpt-5.6-luna / gpt-5.6-terra / gpt-5.4 / grok-4-1-fast-reasoning に分散(7 件中 3 件が Grok)、F は `mode: balanced` と `routing_trace` が返った。
- **ルーティング先を絞る比較(任意)**: model subset(例: OpenAI 系だけ)と routing mode を指定したルーターを別名でデプロイし(model-router how-to の REST 例。`properties.routing.mode` / `models`)、`FOUNDRY_ROUTER_DEPLOYMENT=<その名前>` で同じ probe を流す。B/C に非 OpenAI のモデル名が出なければ絞り込みが効いている
- **主要な発見**: 絞り込みなしのルーターは既定で非 OpenAI モデル(Grok)に流れる。`response.model` で監査可能。**データガバナンス要件がある案件では model subset 設定が必須**。現行ドキュメントでは非 OpenAI ルーティングの preview 表記が消え、正式仕様の挙動になっている。
- 詳細: [05 NOTES](../probes/05-model-router/NOTES.md)

### 6.6 06 Structured outputs(json_schema)

- **確かめること**: Responses `text.format`(strict)と Chat Completions `response_format` の両面、enum 矯正、`additionalProperties` 省略時の扱い。
- **コマンド**: `uv run python probes/06-structured-outputs/probe.py`
- **出力で見る所**: A の `パース成功。currency=JPY 明細数=2` / B の `currency=JPY ... 余計なキー=set()` / C が JSON 文字列 / D が 400 にならず JSON を返す。
- **主要な発見**: 両 API 面で strict が効き、プロンプトで指示しても schema が勝つ。Foundry は `additionalProperties` 省略の strict スキーマも受理(OpenAI 本家より緩い → 本家へ戻すと落ちうる)。
- 詳細: [06 NOTES](../probes/06-structured-outputs/NOTES.md)

### 6.7 07 Guardrails / コンテンツフィルター

- **確かめること**: 既定ポリシー下の注釈(`content_filter_results` / `prompt_filter_results`)、有害依頼と jailbreak 入力の扱い。
- **コマンド**: `uv run python probes/07-guardrails/probe.py`。D は手動: `az cognitiveservices account deployment show -n aif-fprobes -g rg-foundry-probes --deployment-name gpt-5.4-mini --query properties.raiPolicyName -o tsv`(期待: `Microsoft.DefaultV2`)
- **出力で見る所**: A にカテゴリ別 `severity` と入力側 `jailbreak`/ B は「ブロックされず応答が返った」(モデルの refusal)/ C が `BadRequestError ... 400`(content_filter)。
- **主要な発見**: 防御は 2 レイヤ — jailbreak は Prompt Shields が入力段で 400、素朴な有害依頼はモデル refusal(200)。アプリは両方を安全側の結果として扱う。
- 詳細: [07 NOTES](../probes/07-guardrails/NOTES.md)

### 6.8 08 埋め込みのエンドポイントルーティング

- **確かめること**: embeddings がアカウント / プロジェクトのどちらのエンドポイントで使えるか。
- **コマンド**: `uv run python probes/08-embeddings-routing/probe.py`(要 text-embedding-3-small デプロイ)
- **出力で見る所**: A が `"dims": 1536` で成功 / B が `NotFoundError 404`(`base_url=.../api/projects/probes/openai/v1/`)/ C が成功 / D(2026-10-06 追加)= プロジェクトの資格情報のまま base_url をアカウントへ向けた embeddings(agent-framework-foundry 1.14 の `FoundryEmbeddingClient` と同じ方式)。2026-10-06 の実測: B は今も 404、D は成功(`ai.azure.com` スコープのトークンがアカウントで通る)。
- **主要な発見**: **embeddings はプロジェクト経由 404・アカウント経由のみ成功**(chat/responses は両方 OK)。接続情報はプロジェクトとアカウントの 2 本を持つ。
- 詳細: [08 NOTES](../probes/08-embeddings-routing/NOTES.md)

### 6.9 09 継続評価(evaluation_rules)

- **確かめること**: prompt agent に `RESPONSE_COMPLETED` 駆動の継続評価ルールを掛け、自動評価ランが発火・観測できるか。呼び出し方 2 通り(D = エージェントエンドポイント / D2 = プロジェクトの openai client+`conversation`+`agent_reference` = 公式サンプルの呼び方)で比べる。
- **コマンド**: `uv run python probes/09-continuous-eval/probe.py`(ランが 6 件そろうか最大 600 秒でポーリング)
- **出力で見る所**: A の `eval_...` / B のルール(`action.type=continuousEvaluation`・`filter.agentName`・`samplingRate: 100.0`)/ C の一覧(`event=None` になる表現揺れがある)/ D・D2 の後の `自動ラン検出: continuousevalrun_... status=...`、各ランの `data_source.item_generation_params.source.content`(どの応答のランか)と `report_url`。
- **主要な発見(2026-10-06)**: ルールは **prompt agent スコープ必須**。1 応答 = 1 ランが 16 秒以内に `evals.runs.list` に出る。**D(エージェントエンドポイント)の応答のランは `failed`**(評価器が応答を取得できず AOAI 404 "Response ... not found")、**D2 は `completed`**(coherence 4.0)。08-04 と 2026-10-06 の 1〜2 回目にランが出なかったのは、probe が `sampling_rate=1.0`(= **1%**。百分率)を渡していたため(修正済み)。
- 詳細: [09 NOTES](../probes/09-continuous-eval/NOTES.md)

### 6.10 10 hosted agent の版更新と会話の継続

- **確かめること**: hosted agent の新しい版をデプロイした後も、旧版で始まった会話を続けられるか。会話のつなぎ方 3 通り(P = `previous_response_id` だけ / S = + `agent_session_id` / C = `conversation`)× 版の操作(切り替え・移行・ロールバック・旧版の削除・休止明けの再開)
- **コマンド**: §5.2 の 10 の手順(v1〜v3 を順にデプロイし、途中で idle_timeout 120 秒+60 秒待つ)
- **出力で見る所**: 各ターンの `build=` と `history=`(応答した版と受け取った履歴の数)・`marker=`(`$HOME` のファイル)・`sessions (...)` の `version_indicator`、4 の `delete_version(v1) failed: 409` と `force=True ok`
- **再測定(2026-10-06 実測)**: `--scenario release`(§5.2)。公式 manage-hosted-agent(2026-09-16 版)の「既存セッションは作成時の版に束縛され、セレクタ変更で移行しない」と下の観察の食い違いを決着させる。旧版の削除や休止中の新しい版の作成を挟まず、production 固定 → 候補作成 → 昇格 → 休止(`stop_session` と idle_timeout の 2 通り)→ 再開 → 休止中のロールバック、の順。出力の最後の `まとめ` で R6(A3 / B3 / P3)と R7(N2)が「公式どおり」か「09-30 と同じ」かを見る。判定の読み方は NOTES 10 の 2026-10-06 追記。**結果: R6 の A3 / P3(`stop_session` 後)と idle 明けの B3、R7 の N2 はすべて「09-30 と同じ」(現行のセレクタの版)**。idle_timeout 900 秒・`--route-mode preserve` でも同じ。同日の maf-ports Port 11(MAF のホスティング)は公式どおりで、構成差は未切り分け
- **主要な発見(2026-09-30)**: 会話は版をまたいで続く(履歴はエージェント単位)。**起動中のセッションは旧版のまま、休止明けは現行の版で再開**(明示固定したセッションも同じ — 公式の記述と食い違い)。ロールバックも同じ規則。旧版の削除はセッションが残ると 409、`force=true` で削除すると同じセッション ID のまま現行版で続き、履歴も `$HOME` も残った。App Insights 未接続では接続文字列がコンテナに注入されない
- 詳細: [10 NOTES](../probes/10-hosted-version-continuity/NOTES.md)

### 6.11 11 トレース本文の保護テーブル振り分け(AppGenAIContent)

- **確かめること**: 機微な gen_ai.* 属性の値が、発生源(A1 合成スパン / A2 対照 = gen_ai.* 以外の属性名 / A3 ログの属性 / B prompt agent のプラットフォーム側スパン / C MAF のクライアント側スパン)ごとに、従来テーブル(AppDependencies / AppTraces / AppEvents / AppRequests)と `AppGenAIContent` のどちらに入るか。サブスクリプションの feature flag は表示だけで変更しない。
- **コマンド**: §5.2 の 11(`--extra maf`、`LOG_ANALYTICS_WORKSPACE_ID` が要る)
- **出力で見る所**: D の flag の状態と `protectionLevel` / E のポーリング(`AppGenAIContent の発生源=[...]` に a1・a3・b・c がそろうまで)/ F の `summary` — 発生源 × テーブルごとの `rows`・`values_present`(従来テーブルに本文が残っていれば `本文(目印あり)`、移行後はポインタの短い値になるはず)・`pointer_rows` / `pointer_matches`(`_MS.GenAIContentId` と AppGenAIContent.Id の一致)・`columns_with_marker`。
- **主要な発見(2026-10-06、flag 未登録)**: どの発生源も**二重書き**(従来テーブルに本文が残り、AppGenAIContent にもコピー。ポインタは 1 対 1 で一致)。A2(gen_ai.* 以外の属性名)と **MAF のメッセージイベント(AppTraces の Message 本体)は対象外**。AppGenAIContent は従来テーブルより最大 6 分遅れて届く(2 回目はほぼ同時)。プラットフォーム側スパンはオプトインなしで本文を記録する。
- 詳細: [11 NOTES](../probes/11-trace-content-routing/NOTES.md)

## 7. 確認観点

| 確認 | # | 観点 | 確認方法 | 期待結果 |
| --- | --- | --- | --- | --- |
| [ ] | 1 | 正常系: 全 probe の完走 | `./run_all.sh` 後に `grep -c '^== ' logs/*.log` | 10 本すべてにログがあり、各 probe の観点見出しが最後(01 は I、05 は F、08 は D、09 は E、10 は `まとめ`)まで出ている |
| [ ] | 2 | 想定どおりのエラー(分岐・異常系) | `grep -n '^!!' logs/*.log` | 01 A の 404(アカウント直下)・01 H の 400・02 G の 400 のように、NOTES が「つまりどころ」として記録したものだけが出る。それ以外の `!!`(401/403 等)は §10 へ |
| [ ] | 3 | エンドポイント非対称(08・01) | `logs/08-embeddings-routing.log` の B、`logs/01-conversations.log` の A | どちらも 404。変わっていたら survey 08 / 03 の記述更新候補 |
| [ ] | 4 | データガバナンス(05) | `grep 'model=' logs/05-model-router.log` | ルーティング先のモデル名が出る。OpenAI 以外(grok 等)が混ざるなら、その環境で router を使う前に subset 設定が要る |
| [ ] | 5 | 外部送信の実体(04) | `logs/04-web-search.log` の `action.queries` | ユーザー入力由来の検索クエリ文字列が見える(= Bing に出た文字列) |
| [ ] | 6 | 継続評価(09) | `logs/09-continuous-eval.log` の D | `自動ラン検出: continuousevalrun_...` と `report_url` が出れば 2026-09-29 の修正で解消。出なければポータルの Monitor → Recurring evaluations を確認し NOTES に記録 |
| [ ] | 7 | 観測: 継続評価の結果の見え先 | ポータル Build → Evaluations(または Monitor タブ)/ D の `report_url` | probe-ce-agent の応答に対する coherence 評価が表示される |
| [ ] | 8 | 後片付け(probe 内) | 各 probe の最後の観点(02 H・03 G・09 E) | エージェント・ベクトルストア・ファイル・ルール・eval の削除が `OK` / `files.delete 済み` |
| [ ] | 9 | コスト・後片付け(基盤) | `az group show -n rg-foundry-probes`(10 を専用基盤で動かしたら `rg-foundry-probes-p10` も) | 検証後は §9 で削除し、`ResourceGroupNotFound` になる |
| [ ] | 10 | 版更新と会話の継続(10) | `logs/10-hosted-version-continuity.log` の `まとめ` | P3/S3/C3 = 旧版(v1)・N1 = v2・S-mig/C-mig = v2・N2 = v2(ロールバック後も)・P4/S4/C4 = v2(v1 削除後)・休止明けの 5 = すべて v3。どれも履歴が途切れない。変わっていたら NOTES 10 と architecture 09 §6.3 の更新候補 |
| [ ] | 11 | 版の束縛(10 の再測定) | `logs/10-hosted-version-continuity-release.log` の `まとめ` | N0 = v1・候補 = v2・A2 / B2 / P2 = v1・N1 = v2 は両説一致。**R6(A3 / B3 / P3)と R7(N2)**が「公式どおり」(v1 / v2)か「09-30 と同じ」(v2 / v1)か。結果で NOTES 10・architecture 09 §6.3 の書き換え要否が決まる |
| [ ] | 12 | 埋め込みの振り替え(08 D) | `logs/08-embeddings-routing.log` の D | 成功なら agent-framework-foundry 1.14 の方式(プロジェクトの資格情報+アカウントの base_url)が成り立つ。B の 404 が続くかも併記 |
| [ ] | 13 | ルーティングの記録(05 F) | `logs/05-model-router.log` の F | `model_selection_details.model_router_details` の `mode` / `routing_trace` の有無。B/C のルーティング先が 2026-08-04 から変わったか |
| [ ] | 14 | トレース本文の振り分け(11) | `logs/11-trace-content-routing.log` の F | 従来テーブルの `values_present` が `本文(目印あり)` なら二重書き(2026-10-06 の状態)、短い値ならポインタ化(移行済み)。A2 と MAF のメッセージイベントは AppGenAIContent に現れない |

## 8. トレース・評価の確認

probe はトレース(OpenTelemetry)を送らない(観察はすべて標準出力と `logs/`)。Application Insights は 09 の継続評価の結果と、必要時の手動確認のために接続してある。

```bash
az monitor app-insights query --app appi-fprobes -g rg-foundry-probes \
  --analytics-query "union traces, customEvents, dependencies | where timestamp > ago(1h) | summarize count() by itemType, name | top 20 by count_"
```

- 09 の評価結果の一次確認は `evals.runs.list` の `report_url`(ポータルの評価レポート)と `runs.output_items.list`(評価器ごとのスコア)。
- 11 の照会は probe が `azure-monitor-query` で行う(`union withsource=T AppDependencies, AppTraces, AppEvents, AppRequests, AppGenAIContent | where * has "<run>"`)。従来テーブルに本文が残っていないかの点検は `AppDependencies | where TimeGenerated > ago(1h) | where isnotempty(Properties["gen_ai.input.messages"]) | take 5` と、AppTraces の Message 本体。

## 9. 片付け

```bash
az group delete -n rg-foundry-probes --yes --no-wait   # ステートレス設計。router / Web search は従量なので放置しない
# 10 を専用基盤で動かした場合
az group delete -n rg-foundry-probes-p10 --yes
az cognitiveservices account purge -l japaneast -g rg-foundry-probes-p10 -n aif-<baseName>   # 同名で作り直すなら
```

- probe が途中で落ちた場合は、残骸(`probe-prompt-agent` / `probe-ce-agent`・ベクトルストア `probe-store*`・`assistant-` ファイル・ルール `probe-continuous-rule`)が残り得る。RG ごと削除すればまとめて消える。

## 10. トラブルシューティング

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| `ConfigError: FOUNDRY_PROJECT_ENDPOINT / ... を .env に設定` | `.env` 未作成・未記入 | `.env.example` をコピーして main.bicep の出力を転記 |
| `DefaultAzureCredential failed to retrieve a token` | `az login` していない / テナント違い | `az login`(必要なら `--tenant`) |
| 401 / 403 `PermissionDenied` | RBAC 伝播待ち、または roles.bicep 未実行 | 5〜15 分待つ / §5.1 の第 2 段を実行 |
| 01 A・08 B の 404 | 仕様(アカウント直下に Conversations なし・プロジェクト経由に embeddings なし) | 正常。NOTES の発見どおり |
| 02 G の 400 `Not allowed when agent is specified` | 仕様(エージェント指定時は `instructions` 上書き不可) | 正常 |
| `extra_body={"agent": ...}` で 400 | 旧名称 | `agent_reference` を使う |
| 05 で `DeploymentNotFound` | `deployRouter=true` でデプロイしていない | main.bicep を `deployRouter=true routerVersion=2025-11-18` で再デプロイ |
| 08 A も失敗 | text-embedding-3-small 未デプロイ | §5.1 の `deployment create` |
| 09 B で 403 `preview_feature_required` | 継続評価(プレビュー)に opt-in ヘッダーが必要になった | `AIProjectClient(..., allow_preview=True)` にする(SDK が `Foundry-Features: Evaluations=V1Preview` を付ける) |
| 09 D で自動ランが出ない | `sampling_rate` を割合のつもりで 1.0 にしている(百分率なので 1%)/ プロジェクト MI のロール不足 | `sampling_rate=100`(または省略)。roles.bicep の実行を確認 |
| 09 のランが `failed`(`Response with id ... not found`) | エージェントエンドポイント経由の応答は評価器から見えない | プロジェクトの openai client に `agent_reference` を付けて呼ぶ(D2) |
| 11 で AppGenAIContent が 0 件のまま | 着信が従来テーブルより数分遅い / 送信前にプロセスが終わった | 最大 20 分待つ(probe は待つ)。`force_flush` 済みか確認 |
| 10 で hosted agent の作成が「does not have permissions … agents/write」 | Foundry User の反映待ち(infra.bicep が付与) | 約 5 分待って再実行 |
| 10 の 4 で `409 conflict ... deletion-blocking session(s)` | 仕様(版に結び付いたセッションが残っていると削除できない。休止中も 30 日の期限まで) | 正常。probe は続けて `force=True` で削除する |
| 10 `--scenario release` の `stop_session(...) failed` | セッション停止 API の失敗(Entra 分離では呼び出し元の ID に限られる) | 結果を記録して続行(B は idle_timeout の経過で休止するので判定は残る)。R8 で `force=True` 削除する |
| 05 F で `model_selection_details なし` | プレビューのメタデータは要求ごと・サービス版ごとに付かないことがある(公式) | 観察結果として記録(エラーではない) |
| `RequestConflict`(デプロイ時) | アカウント配下のサブリソースを並行作成 | main.bicep は直列化済み。手動追加(埋め込み)は前のデプロイ完了後に |

## 11. 関連・更新履歴

- 一覧・検証対象外の理由・最新化チェック結果: [README](../README.md)
- 機能の GA/プレビュー状況: [features/03 Agent Service](../../../docs/survey/features/03-agent-service.md) / [features/04 ツール・ナレッジ](../../../docs/survey/features/04-tools-knowledge.md) / [features/02 モデル](../../../docs/survey/features/02-models.md) / [features/05 観測・評価](../../../docs/survey/features/05-observability-evaluation.md) / [features/06 安全性](../../../docs/survey/features/06-safety-guardrails.md) / [features/08 開発者サーフェス](../../../docs/survey/features/08-developer-experience.md)
- ユースケース実装例: [labs/maf-ports](../../maf-ports/README.md)

| 日付 | 内容 |
| --- | --- |
| 2026-09-29 | 初版(openai 2.53→3.20 / azure-ai-projects 2.4→2.7。09 の eval データソースを公式の継続評価の形に修正・要再実測) |
| 2026-09-30 | probe 10(hosted agent の版更新と会話の継続)を追加し、専用の最小基盤でライブ実測(§5.2・§6.10・§7 #10・§9・§10) |
| 2026-10-06 | ライブ再実測(01〜11。新規 RG・削除と purge 済み)。09 の真因(`sampling_rate` の百分率・エージェントエンドポイント経由の応答は評価が 404)を特定して修正、10 は release シナリオで「休止明けは現行の版」を再確認(Port 11 と割れる)、11(AppGenAIContent)を新設(§5.2・§6.9〜6.11・§7 #6・#14・§8・§10) |
| 2026-10-06 | 依存を openai 3.24 / azure-ai-projects 2.8.0 / azure-identity 1.26 へ更新(静的検証のみ)。10 に `--scenario release`(公式のリリース手順との食い違いの再測定)、08 に D(MAF 1.14 方式の埋め込み)、05 に F(ルーティングの記録・プレビュー)と `FOUNDRY_ROUTER_DEPLOYMENT` を追加(§4・§5.2・§6.5・§6.8・§6.10・§7 #11〜13・§10) |
