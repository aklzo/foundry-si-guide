# foundry-probes — Foundry 未検証機能の挙動確認ラボ

[maf-ports](../maf-ports/) の 13 ポートは Foundry のモデル推論・トレーシング・評価(バッチ)・Memory・Code Interpreter・MCP・Foundry IQ・hosted agent+Routines・Voice Live・AI Search を「ユースケースとして」検証済み。本ラボは **そこに乗らなかった機能を、単純例+観点別リクエストで叩いて挙動を記録する** 検証ラボ。

目的は動くアプリを作ることではなく、**各機能が実際にどう振る舞うか(発見メモ)と、どこで詰まるか(つまりどころ)を一次記録として残す**こと。各 probe は「観点ごとにリクエストを投げて生の応答を観察する」スクリプトで、実行ログ(`logs/`)がそのまま `NOTES.md` の根拠になる。

## probe 一覧(01〜09 は 2026-08-04、10 は 2026-09-30 ライブ実測。**2026-10-06 に 01〜11 を再実測**。12〜15 は 2026-11-22 実測)

| # | 機能 | サーベイでの位置 | 主な発見 / つまりどころ | NOTES |
| --- | --- | --- | --- | --- |
| 01 | Conversations API(サービス側会話状態) | 03 / GA | プロジェクト経由のみ(アカウントは 404)・TTL フィールド無し・store=False は会話にも残らない・model-router で別モデル継続可 | [NOTES](./probes/01-conversations/NOTES.md) |
| 02 | Prompt agents(サービス側定義+版) | 03 / GA | 版が自動採番・agent ごとに Entra ID 発行・`agent_reference` で旧版固定呼び出し・`instructions` 上書きは 400 | [NOTES](./probes/02-prompt-agents/NOTES.md) |
| 03 | File Search + ベクトルストア | 04 / GA | 埋め込みモデルの自前デプロイ不要・チャンク既定 800/400 実測一致・store 削除でファイルは残る・明示 TTL 可 | [NOTES](./probes/03-file-search/NOTES.md) |
| 04 | Web search ツール | 04 / GA | 型名は `web_search`・`action.queries` に実クエリ露出(DPA 対象外送信の実体)・tool_choice 強制で無駄検索も走る | [NOTES](./probes/04-web-search/NOTES.md) |
| 05 | Model router | 02 / GA | **japaneast で動く(survey のリージョン表が古い)**・既定でいきなり Grok にルーティング(データガバナンス注意)・response.model で監査可(※2026-10-06: プールに GPT-5.6 系が入り 7 件中 3 件が Grok。`ModelRouterControls=V1Preview` で routing_trace が取れる) | [NOTES](./probes/05-model-router/NOTES.md) |
| 06 | Structured outputs / json_schema | **未収録** | Responses/Chat 両面で strict 動作・enum 矯正が効く・`additionalProperties` 省略でも通る(本家より緩い) | [NOTES](./probes/06-structured-outputs/NOTES.md) |
| 07 | Guardrails / コンテンツフィルター | 06 / モデル=GA | 既定 `Microsoft.DefaultV2`・jailbreak は入力段 400・素朴な有害依頼はモデル refusal 任せ(2 レイヤ) | [NOTES](./probes/07-guardrails/NOTES.md) |
| 08 | 埋め込みのエンドポイントルーティング | 08 の注記 | **embeddings はプロジェクト経由 404 / アカウント経由のみ成功**(chat は両方 OK)。接続情報 2 本持ちが必須(※2026-10-06: 404 は継続。プロジェクトの資格情報〈ai.azure.com スコープ〉のままアカウントの URL に向ければ通る = MAF 1.14 の振り替え方式) | [NOTES](./probes/08-embeddings-routing/NOTES.md) |
| 09 | 継続評価(evaluation_rules) | 05 / プレビュー | **prompt agent スコープ必須(生 response 不可)**・配線から結果取得まで SDK で完結(**2026-10-06 訂正**: 自動ランは `evals.runs` に 1 応答 1 ランで出る。出なかった真因は probe の `sampling_rate=1.0` = **1%**〈百分率〉。さらに**エージェントエンドポイント経由の応答はランが全件 failed〈404〉**で、プロジェクトの Responses+`agent_reference` で呼ぶ必要がある) | [NOTES](./probes/09-continuous-eval/NOTES.md) |
| 10 | hosted agent の版更新と会話の継続 | arch 09 §6.3 / hosted agent GA | **会話は版をまたいで続く**(履歴はエージェント単位)・起動中のセッションは旧版のまま、**休止明けに現行の版で再開**(版の明示固定も休止明けは効かない)・ロールバックも同じ・旧版の削除はセッションが残ると 409 → `force=true` で履歴もファイルも残して現行版へ(※2026-10-06 `--scenario release` で再測定: 交絡を除いても**休止〈idle・`stop_session`〉明けは現行のセレクタの版**で再開し、公式の「作成時の版に束縛」は起動中だけ成り立つ。ただし同日の maf-ports Port 11〈MAF の hosted agent〉では公式どおり v1 のままで、構成により割れる) | [NOTES](./probes/10-hosted-version-continuity/NOTES.md) |
| 11 | トレース本文の保護テーブル振り分け(`AppGenAIContent`) | arch 09 §3.6 / プレビュー | **2026-10-06・japaneast(flag 未登録)ではどの発生源も二重書き**(従来テーブルにも本文が残る)・振り分けは取り込み側で**属性名**で決まる(gen_ai.* 以外のキーは対象外)・**MAF のメッセージイベント〈AppTraces の Message 本体〉は対象外**・プラットフォーム側スパンはオプトインなしで本文を記録・AppGenAIContent は最大数分遅れて届く(同時のこともある) | [NOTES](./probes/11-trace-content-routing/NOTES.md) |
| 12 | 閉域(PNA Disabled+BYO VNet 注入+standard setup、2026-11-22) | 03 / 07・arch 07 | **Cosmos Serverless で standard が組める**・注入ありのアカウントは**アカウントの capability host が自動作成**(明示作成は 400 / 409)・`Microsoft.ContainerService` 未登録・NAT なしでも prompt agent と File Search / Code Interpreter(ファイル入出力も可)/ Web search / OpenAPI / MCP が動く(OpenAPI と MCP はエージェントサブネットから VM に到達)・外からは 403「Public access is disabled」・**Copilot harness のサンドボックスは閉域でも公開インターネットに出る**(NSG・UDR で止まるかは 15)・閉域だけ `input_file` が 400 | [NOTES](./probes/12-closed-network/NOTES.md) / [COST](./probes/12-closed-network/COST.md) |
| 13 | 権限の境界(UAMI × ロール × スコープ、2026-11-22) | 03 / 07 | Foundry User @プロジェクトはプロジェクトの Responses 可・アカウントの `/openai/v1` は 401・**Project Runtime User 単体はどの経路も 403**・**API キーでエージェントのエンドポイントも通る**(一覧だけ 403)・`disableLocalAuth` は約 1 分で 403 `AuthenticationTypeDisabled`・**他人の `previous_response_id` で続きが読める**(会話と GET は分離)・Foundry User は接続を作れない・PM は Agent Consumer も付与可で metrics は空・**Memory はプロジェクトの経路なら `x-memory-user-id` で他人の記憶が読める**(エンドポイントではヘッダー無視) | [NOTES](./probes/13-rbac-boundaries/NOTES.md) |
| 14 | Agent Optimizer の利用可否(2026-11-22) | 05 / Limited preview | **申請・有効化なしで estimate(200)と最小ジョブ(201 → 約 2 分で succeeded)が通る**・SDK / REST から prompt agent を最適化できる・**閉域のプロジェクトでも成功**・実費は 1 ジョブ数円(estimate の low 付近) | [NOTES](./probes/14-optimizer-access/NOTES.md) |
| 15 | エージェントの外向き通信の経路(委任サブネットの NSG / UDR・harness の egress controls、2026-11-22) | 03 / 07・arch 07 | **NAT なし・既定の送信なしでも OpenAPI / MCP / Copilot harness の shell は公開側に届く**(送信元は AzureCloud.japaneast の Azure 公開 IP)・**どれも委任サブネットの NSG(宛先 /32)・UDR(/32・0.0.0.0/0 → None)で止まり、外すと戻る**・Web search は 0.0.0.0/0 → None でも動く(サブネットを通らない)・Code Interpreter は外に出ない・ツールなしの prompt agent と harness の応答は 0.0.0.0/0 → None でも返る・**harness の egress controls(RAI ポリシー、preview)は Deny のホスト名だけ 403**、ただし付けると VNet 内 8080 番・公開 22 番も即時拒否・**purge したアカウントと同じ名前で作り直すとエージェントのエンドポイントだけ 70 分以上 403**(名前を変えると出ない) | [NOTES](./probes/15-egress-paths/NOTES.md) / [COST](./probes/15-egress-paths/COST.md) |

## 検証対象外(理由つき — 今後の候補)

「今は試さないが、理由と入口だけ残す」もの。将来コスト/権限が許せば同じ枠組みで追加する。

| 機能 | 状態 | 見送り理由 | 入口 |
| --- | --- | --- | --- |
| A2A(agent-to-agent) | プレビュー | ポータル未対応・agent card は REST のみ・2 エンドポイント構成で単純例が重い | survey 03、`az rest` + JSONRPC v1.0 |
| Image generation | プレビュー/一部 GA | `gpt-image-1*` は**限定アクセス(要申請)**、`gpt-image-2` のみ申請不要 | survey 02/04。申請後に probe 追加可 |
| AI Red Teaming Agent | GA | **評価専用の別リージョンプロジェクトが要る**+プロンプトが国外評価に渡る(法務確認前提)・多数の敵対的呼び出しで高コスト | survey 05、`beta.red_teams` |
| BYO storage / standard setup | GA相当 | Cosmos DB **最低 5,000 RU/s 常時課金**・トポロジ検証でありコスト対効果が薄い | survey 03/11、`capabilityHosts`(preview API) |
| Deep Research | **非推奨** | 死んだ classic 面。後継は `o3-deep-research`+web search(DPA 制約は 04 と同じ) | — |
| Browser automation / Computer use | プレビュー/限定 | Playwright Workspaces 別課金 / Computer use は登録申請制で叩けない | survey 04 |
| Global Batch / Prompt caching | GA | 低優先。probe 可能なので次サイクル候補(50% 割引・`completion_window` 固定など挙動確認価値あり) | survey 02、arch 09 |

> **リソース状態:** 検証用の基盤(RG `rg-foundry-probes`)は 2026-08-04 の実測完了後に**削除済み**(コスト停止)。2026-10-06 の再実測でも新規に作成(baseName `fprobes1006`)し、実測後に RG を削除・アカウントを purge した。再実行は下記手順で新規デプロイする。NOTES と `logs/`(ローカル)が一次記録として残る。
>
> **probe 10 は専用の最小基盤**(`probes/10-hosted-version-continuity/infra.bicep` = Foundry アカウント+プロジェクト+実行者の Foundry User。モデル・App Insights なし)で実測し、2026-09-30 に RG `rg-foundry-probes-p10` ごと削除・アカウントを purge 済み。main.bicep の基盤でも実行できる(Foundry User の割り当て込み)。

> **probe 12〜15 は専用の環境**(RG `rg-ignite26-verify`、15 の harness の追試は `rg-ignite26-verify2`。閉域は `probes/12-closed-network/infra.bicep`、公開の basic 構成は `probes/13-rbac-boundaries/infra.bicep`)で 2026-11-22 に実測し、**実測後に RG ごと削除済み**(アカウントは purge。手順と費用は `probes/12-closed-network/deploy.sh`・各 probe の `COST.md`)。12〜15 の `logs/` は一次記録として git 管理に含める。サブスクリプション ID・テナント ID・マネージド ID などの GUID・メールアドレス・公開 IP・リソース名の乱数部分は `tools/scrub_logs.py` で伏せ字にし、資格情報は含めない。

## 実行の前提

1. **基盤デプロイ(課金発生。検証後は RG ごと削除推奨)**
   ```bash
   az group create -n rg-foundry-probes -l japaneast
   az deployment group create -g rg-foundry-probes -f infra/main.bicep \
     -p baseName=fprobes modelName=gpt-5.4-mini modelVersion=2026-03-17 \
        userObjectId=$(az ad signed-in-user show --query id -o tsv) \
        deployRouter=true routerVersion=2025-11-18
   # MI ロール(第2段。principalId ローテーション対策で分離。理由は maf-ports/infra/shared.bicep)
   PID=$(az rest --method get --url "https://management.azure.com$(az cognitiveservices account show -n aif-fprobes -g rg-foundry-probes --query id -o tsv)/projects/probes?api-version=2025-06-01" --query identity.principalId -o tsv)
   AID=$(az cognitiveservices account show -n aif-fprobes -g rg-foundry-probes --query identity.principalId -o tsv)
   az deployment group create -g rg-foundry-probes -f infra/roles.bicep -p baseName=fprobes accountPrincipalId=$AID projectPrincipalId=$PID
   # 埋め込み probe 用(08)
   az cognitiveservices account deployment create -n aif-fprobes -g rg-foundry-probes \
     --deployment-name text-embedding-3-small --model-name text-embedding-3-small --model-version 1 \
     --model-format OpenAI --sku-name GlobalStandard --sku-capacity 10
   ```
2. **`.env` 作成**(`main.bicep` の出力を転記。雛形 `.env.example`)。認証は `az login` 済みの Entra ID を既定とする。
3. **probe 実行**: `uv sync` → `uv run python probes/<NN>-<name>/probe.py`(結果は `logs/` に保存して NOTES の根拠にする)。`./run_all.sh` で全 probe を一括実行。

   詳細な実行手順と確認観点は [docs/runbook.md](./docs/runbook.md)(人間用 HTML: `docs/runbook.html`)。
4. **撤去**: `az group delete -n rg-foundry-probes`(ステートレス設計。model router / Web search は従量課金なので放置しない)。

## 注意

- **Web search(04)は DPA 対象外・データがコンプライアンス境界外へ出る**。probe は最小リクエストに絞ってある。
- **Model router(05)は既定で非 OpenAI モデル(Grok 等)に流れる**。データガバナンス要件のある環境で無設定デプロイしない。
- 実測は 2026-08-04・japaneast・gpt-5.4-mini v2026-03-17 時点。プレビュー機能は仕様変更があり得るので、NOTES の日付を見て再実測すること。

## 検証結果(2026-09-29 最新化チェック)

Azure リソースは削除済みのため**オフライン(静的)確認のみ・ライブ未検証**。probe はライブ専用スクリプトなので、全 9 本を `py_compile`・`ruff check` し、呼び出している SDK メソッドとキーワード引数を installed SDK(openai 3.20.0 / azure-ai-projects 2.7.0)のシグネチャと AST で突き合わせた(不一致 0)。

- **依存更新**: openai 2.53.0 → **3.20.0**、azure-ai-projects 2.4.0 → **2.7.0**、azure-identity 1.25.3(据え置き)、ruff 0.16.9。pyproject の下限を検証版に引き上げ、未使用だった `httpx` 依存を削除(openai 3.x は HTTP クライアントが httpx2 に変わり、azure-ai-projects 2.5.0 以降も追随。probe は httpx を直接使わない)。`uv.lock` は従来どおり git 管理外(`.gitignore`)。
- **改修(09 継続評価)**: eval 定義を公式の継続評価の形 `data_source_config={"type": "azure_ai_source", "scenario": "responses"}`(data_mapping なし)に変更し、ラン検出のポーリングを 300 秒・`report_url` 表示に拡張。旧版はバッチ評価用の `custom` + `data_mapping` で作っており、公式手順(ランは `evals.runs.list` に `continuousevalrun_*` として現れる)と食い違っていた → NOTES の「evals.runs に出ない」は**要再実測**。出典: https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard (2026-09-03 版)
- **変更不要(01〜08)**: Conversations / Responses / Files / Vector stores / Chat Completions / Embeddings / Evals の呼び出しは openai 3.20.0 でシグネチャ・戻り値フィールド(`output_text`・`content_filter_results` 等の拡張フィールド含む)とも互換。02 の `get_openai_client(agent_name=...)` は 2.7.0 でも同じエージェントエンドポイントを向き、公式クイックスタート(2026-09-03 版)の主経路と一致。
- **現行ドキュメントとの差分(挙動の再解釈が要るもの)**: 05 — Model router ページから「非 OpenAI ルーティングはプレビュー」の表記が消え、既定で Grok 等に流れる挙動は正式仕様側になった(2025-11-18 版は 2027-05-20 リタイア予定)。04 — Responses の `web_search_preview` は「サポートされるが非推奨」、prompt agent 用 `WebSearchTool` には `external_web_access`(SDK 2.6.0+)が追加。
- **Bicep**: `az bicep build` で main / roles とも警告なし。`Microsoft.CognitiveServices/accounts@2025-06-01` は他ラボと同じ GA API のため据え置き。RBAC ロール名は「Foundry User(旧 Azure AI User)」の改名をコメントに反映済み(ロール ID は不変)。
- **今後の選択肢**: 02 の版固定は `agent_reference.version` に加え、エージェントエンドポイントの `version_selector` でピン留めする方法が公式化(configure-agent 2026-09-11 版)。

## 検証結果(2026-10-06 最新化チェック)

Azure リソースは削除済みのため**オフライン(静的)確認のみ・ライブ未検証**。

- **依存更新**(`uv lock --upgrade`): openai 3.20.0 → **3.24.0**、azure-ai-projects 2.7.0 → **2.8.0**、azure-identity 1.25.3 → **1.26.0**、ruff 0.16.10(推移依存: azure-storage-blob 12.31.0・cryptography 50.0.2・python-dotenv 1.2.4)。本ラボは agent-framework-foundry を使わないので、MAF 側の `azure-ai-projects<2.8.0` 制約(agent-framework-foundry 1.14.0)を受けずに 2.8.0 にできる。pyproject の下限を検証版に引き上げ
- **静的検証**: `ruff check .` clean / 全 10 本+probe 10 の `agent/main.py` を `py_compile` / 呼び出している SDK メソッド・キーワード引数・モデルのフィールドを installed SDK と AST で突き合わせ **111 呼び出しで不一致 0**(ライブ後の改修と 11 の追加後は 122 呼び出しで不一致 0)(2.7.0 / openai 3.20.0 の環境でも 0 — 使っている API 面は変わっていない)/ `az bicep build`(main・roles・probe 10 の infra)警告なし
- **SDK 2.8.0 で probe に関係する差分**: `get_openai_client()` の実装(`_patch.py`)は 2.7.0 と同一 — 02 / 09 / 10 のエージェントエンドポイント(`agent_name=`)の向き先・`api-version=v1`・`Foundry-Features` ヘッダーは前回と同じ。docstring には「`agent_name` には `allow_preview=True` が必要(ないと ValueError)」と書かれたが、実装は強制していない(ダミー資格情報で確認)→ 将来の版で強制されたら `AIProjectClient(..., allow_preview=True)` にする。評価器・データセットの操作は beta から GA の `project.evaluators` / `project.datasets` へ移った(probe は未使用)。`project.beta.voice_agents`(`realtime` / `conversations` / `telephony`)が加わった。`agents.stop_session` は 2.7.0 からある
- **改修**(いずれもライブ再測定の準備。既存の観点・既定の動作は変えない):
  - **10**: `--scenario release` を追加。公式の本番リリース手順(production 固定 → 候補作成 → 候補専用セッション → 昇格)に沿って進め、セッションを休止(idle_timeout 経過と `stop_session` の 2 通り)させてから再開し、応答した版を「公式どおり(作成時の版)/ 09-30 の実測どおり(現行のルーティング先)」で判定する。休止中のロールバックも対照に入れた。別名のエージェントを使い最後に削除する。フェイクの SDK で制御フローを通しで確認済み
  - **08**: 観点 D を追加 — プロジェクトの資格情報(`https://ai.azure.com/.default` のトークン)のまま base_url だけアカウントの `openai/v1` に向ける。agent-framework-foundry 1.14.0 の「Foundry project embeddings」(`FoundryEmbeddingClient`)は、プロジェクトの OpenAI クライアントを作ってから base_url を `https://<res>.openai.azure.com/openai/v1/` に**書き換えて** embeddings を呼ぶ実装で(installed package の `_embedding_client.py` で確認)、B の 404 を SDK 側で回避している。そのトークンがアカウント側で通るかを実測する
  - **05**: 観点 F(Chat Completions に `Foundry-Features: ModelRouterControls=V1Preview` を付けて `model_selection_details.model_router_details` の mode / routing_trace が付くか — monitor-model-router 2026-09-15 版、プレビュー)と、ルーターのデプロイ名の環境変数 `FOUNDRY_ROUTER_DEPLOYMENT`(既定 `model-router`)を追加。ルーティング先を絞ったデプロイ(model subset / routing mode。デプロイ API `2025-10-01-preview` の `routing` ブロック)を別名で作れば、同じ probe で絞り込みが効くかを比べられる
- **現行ドキュメントとの差分**:
  - **09**: 新ページ evaluation-permissions(2026-09-29)が「モデルを呼ぶ評価は Foundry User を**アカウントスコープ**で(プロジェクトだけの割り当てでは推論が認可されない)」「継続評価ルールの作成にはプロジェクト MI に Foundry User」と明記。roles.bicep はプロジェクト MI に Foundry User を**アカウントスコープ**で付けているので満たしている → 再実測でランが出なければ、原因は RBAC 以外(データソースの形・非同期の遅延・観測面)に絞れる
  - **10**: manage-hosted-agent(2026-09-16 版)に「Release a version without changing production」節。既定ルーティングは latest 追従なので候補作成前に production を具体版へ固定せよ、候補は `version_ref` で固定したセッションで試せ、「**既存のセッションは作成時の版に束縛され、セレクタを変えても移行しない**。旧版とイメージはセッションやロールバックが依存する間は残せ。エージェントや版の削除はロールバック手段ではない」。probe 10 の観察(休止明けは現行のルーティング先・明示固定も休止明けは効かない)と食い違う。manage-hosted-sessions(2026-08-21 版)に「セッションの停止(`:stop`)」API(計算資源を止めファイルは残す。2.7.0 以降の SDK にある)
  - **05**: Model router は既定で **Balanced** モード+全モデルのプール。デプロイ時に routing mode(Quality / Cost)と **model subset** を選べ、後から追加された新モデルは subset に自動では入らない。Azure Policy のモデルデプロイ制御が subset にも効く(model-router-policy)。エージェント経由では OpenAI・OSS・Anthropic のモデルも選ばれうる
- **ライブ再測定(2026-10-06 12:06〜13:56 UTC、新規 RG `rg-foundry-probes`・baseName `fprobes1006`・japaneast・main.bicep〈router 込み〉+ roles + 埋め込み。11 本を同じ RG で)**:
  - **01〜04・06・07**: 08-04 と同じ形(01 A の 404・H の 400、02 G の 400、03 チャンク 800/400・store 削除後もファイル残存、04 `action.queries` と `url_citation`、06 strict、07 jailbreak は入力段 400・有害依頼は refusal・`Microsoft.DefaultV2`)。02 の版の戻り値に `blueprint`・`agent_guid`・`draft` が加わっている。01 G の model-router は `gpt-5.6-terra` で継続
  - **05**: ルーティング先は 08-04 から変わり、7 件中 3 件が Grok(残りは gpt-5.6-luna / -terra / gpt-5.4)。F の `routing_trace` はアカウントの `openai/v1` で返った
  - **08**: B は今も 404、**D(ai.azure.com スコープのトークン+アカウントの URL)は成功**
  - **09**: 自動ランが出なかった真因を特定して修正 — ①`sampling_rate` は百分率で、probe の 1.0 は 1% だった(→ 100)、②エージェントエンドポイント経由の応答はランが作られても評価器が応答を取得できず `failed`(AOAI 404)。プロジェクトの Responses+`agent_reference`(公式サンプルの呼び方)なら `completed`(coherence 4.0)。1 応答 = 1 ランで 16 秒以内に `evals.runs.list` に出る
  - **10**(`--scenario release`、3 回): 起動中のセッションは作成時の版、**`stop_session` / idle 明けのセッションは現行のセレクタの版で再開**(`version_ref` の明示固定も同じ)、休止中のロールバックも同じ規則。idle_timeout 120 秒・900 秒、切り替え API の形(組み直し / 既存設定を保ってセレクタだけ差し替え = `--route-mode preserve`)のどれでも同じ。**同日の maf-ports Port 11(MAF の hosted agent〈agent-framework-foundry-hosting 1.0.0b261002〉、共有基盤)では 4 通りとも公式どおり v1 のまま**で、構成により結果が割れる。残る条件差はコンテナの実装(未切り分け。NOTES 10)
  - **11(新設)**: 合成スパン・ログ・prompt agent のプラットフォーム側スパン・MAF のクライアント側スパンのすべてで**二重書き**(従来テーブルに本文が残り、AppGenAIContent にもコピー、`_MS.GenAIContentId` で 1 対 1)。属性名が gen_ai.* の 7 種でなければ対象外、MAF のメッセージイベントの本文(AppTraces の Message)も対象外。AppGenAIContent は 1 回目は約 6 分遅れ、2 回目(`sampling_ratio=1.0`)は同時に届いた。分類は 2 回とも同一
  - 所要: デプロイ 1 分弱(+ロールと埋め込み 1 分)、probe 01〜08 は各 10 秒〜1 分、09 は 1 回 2〜10 分、10 は 1 回 3〜6 分、11 は 9 分(着信待ち)。コスト感: 数ドル未満(gpt-5.4-mini・model-router・Web search 4 回・埋め込み・hosted agent の数分の CPU / メモリ・App Insights の取り込み少量)
  - 後片付け: RG を削除し Foundry アカウント aif-fprobes1006 を purge 済み
- **改修(ライブで判明したもの)**: 09 の `sampling_rate=100.0` と D2(公式サンプルの呼び方)・ランの `data_source` / `error` 表示、10 の `--idle-timeout` / `--wait` / `--route-mode`、11 の新設(pyproject に azure-monitor-opentelemetry / azure-monitor-query、extra `maf` に agent-framework-core / -openai。run_all.sh は `--extra maf` で実行)、main.bicep に `logAnalyticsWorkspaceId` / `logAnalyticsWorkspaceResourceId` の出力

## 関連

- ユースケース実装例: [labs/maf-ports](../maf-ports/)(13 ポート。Memory / Code Interpreter / MCP / IQ / hosted / Voice など)
- 機能の可否判断: [docs/survey/features/](../../docs/survey/features/README.md)
