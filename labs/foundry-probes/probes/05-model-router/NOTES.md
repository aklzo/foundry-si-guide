# Model router — 挙動発見メモ(2026-08-04 実測)

環境: model-router v2025-11-18(GA)/ japaneast / GlobalStandard cap 10

## 発見(挙動)

- **japaneast にデプロイ成功。** survey 02 のリージョン表(Australia East / East US 2 / South India / Sweden Central / West US 3)は古い。カタログ(`az cognitiveservices model list -l japaneast`)にも v2025-11-18 が載っている。→ survey 更新候補。
- **既定で非 OpenAI モデルにルーティングされる。** 5 プロンプト中 4 つが `grok-4-1-fast-reasoning`(xAI)、挨拶のみ `gpt-5-mini-2025-08-07`。survey では「非 OpenAI ルーティングはプレビュー」だが、**既定デプロイ(ルーティング先の絞り込みなし)でいきなり Grok に流れる**。
- ルーティング先はアカウントのデプロイとは無関係(このアカウントに grok / gpt-5-mini のデプロイは無い)。ルーター内部のモデルプールが使われる。
- `response.model` に実ルーティング先が返るので、後から集計・監査可能。usage もルーティング先モデルのトークン単位(reasoning_tokens も見える)。課金はルーティング先モデルの単価。
- `temperature` はルーティング先が reasoning 系(grok-4-1-fast-reasoning)でもエラーにならなかった(gpt-5.4-mini 直だと temperature 不可 — maf-ports 服の罠 — なので、ルーター経由はパラメータ互換の吸収も担っている可能性。断定は保留)。

## つまりどころ

- **データガバナンス上の要注意動作**: モデル選定を「OpenAI 系のみ」と合意している案件で model-router を無設定デプロイすると、ユーザーデータが xAI(Grok)へ流れる。ルーティング対象モデルの絞り込み(デプロイ時の model subset 設定)を必須手順にすること。
- ルーティング先は日々変わり得る(ルーターのバージョンでモデルプールが変わる)。回帰テストの再現性が要る検証では router を使わない。
- 旧版 2025-05-19 / 2025-08-07 は 2026-08-30 リタイア(survey)。既存案件で旧版を掴んでいたら移行が要る。

## SI 判断メモ

- 「コスト最適化に router」という提案は、(1) ルーティング先の許可リスト設定、(2) response.model の監査ログ化、をセットにしないと規制業種では通らない。逆にこの 2 点を付ければ「難問だけ高いモデル」の説得力ある構成になる。

## 2026-10-06 追記(最新化チェック・ライブ未検証)

- 現行ドキュメント(model-router how-to 2026-09-09 版 / concepts 2026-09-01 版)では、既定のデプロイは **Balanced モード+対応モデル全体のプール**。デプロイ時に routing mode(Quality / Cost)と **model subset** を選べる(デプロイ API `2025-10-01-preview` の `properties.routing`。変更の反映は最大 5 分)。**後から追加された新モデルは subset に自動では入らない**。Azure Policy のモデルデプロイ制御が subset にも効く(model-router-policy)。エージェント経由では OpenAI・OSS・Anthropic のモデルも選ばれうる。→ 上の「つまりどころ」の対策(デプロイ時の model subset 設定)は公式手順として整った。
- probe に **観点 F** を追加: Chat Completions に `Foundry-Features: ModelRouterControls=V1Preview`(プレビュー)を付けると `model_selection_details.model_router_details`(`mode` / `routing_trace` / `session_affinity`)が付く(monitor-model-router 2026-09-15 版)。`response.model` に加えて「どのモデルを試してどれが返したか(フォールバック含む)」を監査ログに残せるかを見る。
- ルーターのデプロイ名を環境変数 `FOUNDRY_ROUTER_DEPLOYMENT`(既定 `model-router`)にした。subset を絞ったデプロイ(例: OpenAI 系だけ)を別名で作れば、同じ probe で「Grok に流れなくなるか」を比べられる(runbook §6.5)。
- 再実測で見ること: 既定デプロイのルーティング先が 2026-08-04(5 件中 4 件が grok-4-1-fast-reasoning)から変わったか、F のメタデータがアカウントの `openai/v1` で返るか。

## 2026-10-06 再実測(ライブ)

環境: japaneast・rg-foundry-probes(aif-fprobes1006)・model-router 2025-11-18(既定デプロイ = Balanced・全モデル)・GlobalStandard cap 10。

- **ルーティング先は 08-04 から大きく変わった**: B/C の 5 件は 挨拶 → `gpt-5.6-luna-2026-07-09` / 単純事実 → `gpt-5.6-terra-2026-07-09` / 短い作文 → `gpt-5.4-2026-03-05` / 多段推論 → `grok-4-1-fast-reasoning` / コード → `gpt-5.6-terra-2026-07-09`。D(「1+1 は?」)と E(temperature 0.2)は `grok-4-1-fast-reasoning`。01 の G(会話の継続)は `gpt-5.6-terra-2026-07-09`。→ 7 件中 3 件が Grok(08-04 は 5 件中 4 件)。**絞り込みなしのルーターが非 OpenAI モデルに流れる点は変わらない**。プールに GPT-5.6 系が入り、「易しい問題 → 安いモデル」の振り分けらしい形になった
- `temperature=0.2` は Grok 行きでも受理(08-04 と同じ)
- **F(`Foundry-Features: ModelRouterControls=V1Preview`)はアカウントの `openai/v1` の Chat Completions で動いた**: `model_selection_details.model_router_details` に `mode: "balanced"` と `routing_trace`(`latency_ms: 517`、`attempts: [{model: "gpt-5.4", result: {status: 200}}]`)が返った。`response.model` に加えて「どのモデルを試してどれが返したか(フォールバック含む)」を監査ログに残せる(プレビュー)
- subset を絞ったデプロイとの比較は今回は実施していない(任意。runbook §6.5)
