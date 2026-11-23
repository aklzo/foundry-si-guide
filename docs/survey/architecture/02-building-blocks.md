# 02. 構成要素カタログ — レイヤー別「Foundry 機能 vs 自前実装」の組合せ

[← アーキテクチャ TOP](./README.md)

> **最終更新:** 2026-07-30(公式ドキュメントとの突合検証で訂正)/ 2026-09-26(Routines・A2A ツールの GA 化、Model router のリージョン拡大、hosted agent のセッション仕様・期限到来、閉域ツール表の変化を反映)/ 2026-10-06(L9 に toolbox 経由の利用者委任、L12 にトレース本文の専用テーブル、L13 に合成評価器、L15 にカナリアの公式間不整合、L16 に hosted agent の Terraform を追加) / 2026-10-14(L1 の Model router に Fireworks 3 モデルの既定プール入りとリージョン数の決着、L3 の capability settings 設定ページの 301〈要確認〉、L4 の Memory の TTL・項目 CRUD、L8 の既定ポリシー URL の移動・文字起こしモデルの除外・ストリーミング末尾の注記、L10 の Browser Automation〈ページは GA 表明・閉域は非対応のまま〉、L12 のテレメトリ送出の既定変更と閲覧ロールの付与先、L13 の Learn ラベル外しと GA 一覧表の食い違い・Rubric の尺度、L15 の idle timeout 上限の両論) / 2026-11-22(features 差分更新〈10-14 以降+Ignite 2026〉の波及: L1 に GPT-6.x の APAC Data Zone・managed compute〈GA、APAC Data Zone なし〉・Model router の再編〈45 モデル・Claude は Global の version 1 のみ・Fireworks は有効化時のみ・Policy は要求時に効かない・Auto は Global〉・Baseten / fal の DPA 対象外・prompt cache の書込課金、L2 に Microsoft Copilot harness〈preview、12-01 課金開始〉と外部エージェント登録〈GA〉・Workflows 廃止まで 9 日・Durable Extension の stable 化・GPT-6 系の tool calling、L3 に会話保持と Responses API の CMK、L4 に harness で Memory 不可、L5 に Foundry IQ (Azure AI Search) への改称と Search `2026-10-01` の GA 範囲・SharePoint indexed GA・KB の fail-open・Web search の経路差、L6 に OpenAPI の OAuth passthrough 非対応・MCP 自動登録の廃止・ツールガバナンス、L8 に Content Safety preview 6 機能の 2027-04-30 廃止・フィルター Off の承認範囲・分類器更新・Modified Abuse Monitoring の縮小、L9 に `agents/write`・エージェントスコープとファイル・コスト閲覧ロール、L10 にサブネット IP 共有 GA・`192.168.0.0/24`・private CA・Browser Automation の閉域両論・閉域で電話チャネル不可、L11 に Azure AI Gateway と cost controls、L12〜13 に外部エージェントのトレース GA・Insights GA・Rubric GA の両論・HITL、L14 に Bot Service 不要、L15 に idle 上限 240 分の確定・7 段のサイズ・idle 待機の課金・egress GA・memory snapshots・BYO-AKS、L16 に azd 拡張 GA と `az cognitiveservices agent` の Deprecated) / 2026-11-22 訂正(Foundry IQ: ユーザートークンを渡さないときの KB の挙動は Learn のページで食い違うので両論に。閉域取り込みの tier を S2 / S3 / L1 / L2 と明記)

## このドキュメントの使い方

Foundry を使ったアーキテクチャは「Foundry を使うか使わないか」の二択ではない。**レイヤーごとに独立して「Foundry のマネージド機能に寄せる / アプリ側で自前実装する」を選べる**のが実態であり、SI の設計はこの組合せ選択そのものである。

本ページは 16 レイヤーそれぞれについて、取りうる選択肢を**マネージド度 3 段階**で並べ、選定の決め手と地雷を整理する。ユースケース別の「実際にどう組んだか」は [04〜08 のユースケース編](./README.md#ドキュメント一覧)を参照。

### マネージド度の定義(本ドキュメント共通)

| 記号 | 呼称 | 意味 |
|---|---|---|
| **M** | フルマネージド | Foundry の機能を構成するだけ。ランタイムコードを書かない |
| **H** | ハイブリッド | Foundry の部品を API として借り、制御はアプリ側コードが持つ |
| **S** | 自前実装 | Azure 汎用サービス / OSS / 自社実装で組む。Foundry 固有機能に依存しない |

「M ほど良い」ではない。**M は立ち上がりが速く運用が軽い代わりに、制御粒度・移植性・コスト可視性を失う。**S はその逆。案件のライフサイクル(PoC か 10 年運用か)、規制、既存資産で決まる。

---

## レイヤー一覧(先に全体像)

| # | レイヤー | M(フルマネージド) | H(ハイブリッド) | S(自前実装) | 迷ったら |
|---|---|---|---|---|---|
| L1 | モデル提供 | Foundry モデルデプロイ(Global Standard) | Foundry + APIM ゲートウェイ | 他クラウド / セルフホスト(vLLM 等) | M |
| L2 | オーケストレーション | Prompt agent / Workflows(廃止予定) | Hosted agent(MAF・LangGraph 等) | 自アプリ内でループ実装 + Responses API | H |
| L3 | 会話状態 | Agent Service の Conversations | standard setup の BYO Cosmos DB | 自前 DB(Cosmos / PostgreSQL 等) | M→S |
| L4 | 長期記憶 | Foundry Memory(プレビュー) | Memory + 自前フィルタ | 自前サマライズ + ベクトル検索 | S(本番) |
| L5 | ナレッジ / RAG | File Search / Foundry IQ | Azure AI Search ツール + 自前索引 | 自前パイプライン + 任意ベクトル DB | H |
| L6 | ツール実行 | ツールカタログ / MCP / OpenAPI ツール | Toolbox + 自前 MCP サーバー | アプリ内 function calling ループ | H |
| L7 | コード実行 | Code Interpreter | Custom Code Interpreter | Container Apps dynamic sessions 直 | M |
| L8 | ガードレール | Guardrails(既定 DefaultV2) | カスタムガードレール + 自前後処理 | Content Safety API を自前で呼ぶ | M+S 併用 |
| L9 | ID・認可 | Foundry RBAC + Entra | OBO / マネージド ID | 自前トークン交換・認可基盤 | M |
| L10 | ネットワーク | パブリック + Private Link | Standard setup(BYO VNet 注入) | 自前 VNet に全部置く | 要件次第 |
| L11 | ゲートウェイ / 流量制御 | Foundry のクォータのみ | APIM AI ゲートウェイ | 自前プロキシ | H |
| L12 | 可観測性 | Foundry Tracing + Monitor | OTel 自前計装 → App Insights | 自前ログ基盤 | M+H |
| L13 | 評価 | Foundry Evaluations | evals API を CI から呼ぶ | 自前評価ハーネス | H |
| L14 | UI・チャネル | Teams / M365 公開 | 自作 Web + Responses API | 既存システムに組込み | 要件次第 |
| L15 | 実行基盤(コンピュート) | Hosted agents | Container Apps / App Service | AKS / オンプレ | H |
| L16 | IaC・CI/CD | ポータル手動 | Bicep / Terraform + azd | 既存 IaC 基盤に統合 | S |

---

## L1. モデル提供(推論エンドポイント)

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: Global Standard デプロイ | Foundry リソースへのモデルデプロイ。グローバルルーティング従量課金 | GA | 大半の新規案件。最大クォータが取れる | データ処理リージョンを限定できない |
| M: Data Zone Standard | EU / US / APAC のデータゾーン内で処理 | GA | 域内(APAC = 豪・日・韓・星・印のいずれか)処理で足りるが単一リージョンだと容量が足りない案件 | 対応モデル・ゾーンが限られる。**APAC Data Zone は日本国内処理を保証しない**。**2026-11-22:** GPT-6 世代で APAC Data Zone(japaneast を含む)に載るのは `gpt-6.1-sol` / `gpt-6.1-terra` / `gpt-6.2-astra` / `gpt-6.2-sol` の 4 モデル(Astra / Sol / Luna は US・EU のみ)。**managed compute は Data Zone が US / EU のみ**で APAC なし。**2026-09-01 から Global 比のプレミアム価格**(APAC DZ +20%〈新設〉・EU DZ +20%〈9% 引き上げ〉・US DZ +10%〈据え置き〉・日本 Regional +35%。従量課金は 2026-09-01 以降に投入されたモデルのみ、PTU は既存も対象)( https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/microsoft-foundry-model-deployment-pricing-update/4535385 2026-07-09 公開) |
| M: Regional Standard | 指定した Azure geography 内で処理(公式は「運用上 geography 内のリージョン間で処理されうる」と記載。単一リージョン固定ではない) | GA | 厳格なリージョン指定。**日本国内限定処理が必須なら Regional Standard(Japan East)のみ** | 新モデルの提供が最後になりがち。クォータが小さい。**日本の Regional は 2026-09-01 から Global 比 +35%**(適用範囲は Data Zone 行と同じ。同上ブログ) |
| M: Provisioned (PTU) | 予約スループット。時間課金 + Reservations | GA | レイテンシ SLA・安定スループットが要る本番 | **モデル自動アップグレード対象外(手動移行)**。最低 PTU 単位あり |
| M: Batch | 非同期一括、24h ターゲット、50% 割引 | GA | 夜間バッチ、大量分類・要約 | リアルタイム SLA なし |
| M: Instant models | デプロイ不要でモデル名指定のみ | プレビュー | 検証・試作 | プレビュー中は **West US 3 のみ**。FT モデル・カスタムガードレール不可 |
| M: Model router | 単一デプロイで品質/コスト基準の自動振り分け | GA(version `2025-11-18`。現行ページ〈2026-09-01 版〉に非 OpenAI モデルルーティングのプレビュー表記なし) | コスト最適化。モデル選定を運用で回したい | **Global Standard 32 / Data Zone Standard 23 リージョン**(Japan East / West とも両方対応。2026-09-26 に公式表で計数。7・8 月号ブログは GS 28 / DZ 21 と記載)。旧記載「対応リージョン 5 つ」から大幅に拡大(7・8 月号ブログがリージョン拡大を告知)。Claude は事前デプロイ必須。ルーティングプールは同一版のまま入れ替わる(2026-08 に retired モデルが除外)ため、プール更新時は再評価。**2026-10-14 更新:** whats-new-model-router(2026-10-06 版)で **2026-10 にプールが 35 モデルへ拡大**(`gpt-6-astra`・`claude-fable-5-1` / `claude-opus-5` / `claude-sonnet-5`・`grok-4.6`・**`FW-GLM-5.3` / `FW-GLM-5.3-Flash` / `FW-Kimi-K3`〈Fireworks〉**)。**事前デプロイが要るのは Claude だけ**なので、**Fireworks 3 モデル(推論は Microsoft 施設外の Fireworks GPU・US のみ)と Grok が既定プールに入っている** → データ所在要件のある案件は custom subset で明示的に絞る(Fireworks 未有効化のサブスクリプションでの扱いは記載なし — 要確認)。リージョン数の揺れは決着(同ページが「2026-08 = GS 28 / DZ 21 → 2026-09 = 32 / 23」と時系列で記載。ブログの 28 / 21 は 8 月時点の値)。**2026-11-22 更新(ドキュメントを全面再編、model-router-* 10 本超を新設):** プールは **45 モデル**(Learn・Tech Community。Book of News は「top 50」→ 両論、Learn を正とする)。**Fireworks は `Fireworks.EnableDeploy` で有効化したサブスクリプションだけでルーティング対象**(10-14 の要確認を解消)。**Claude は同じリソースに Global Standard でデプロイした version 1(Anthropic 基盤)だけが対象で、Data Zone の router は Claude に流さない**。**Azure Policy は作成・更新時の評価だけで要求時のルーティング先を絞らない** → 所在要件ではデプロイの model subset と Auto の `routing.models` で絞り、**Auto(preview)は常に Global Standard で処理**されるので止める。Responses API にネイティブ対応(Tech Community は preview と書く両論)、Messages API・per-request controls・session affinity・自前デプロイ優先・AI Gateway の automatic model selection は preview。課金はルーティング料+選ばれたモデルの利用料。旧版 2025-05-19 / 2025-08-07 は「2026-08-30 到来」から **2027-01-27** に再設定された([features/02](../features/02-models.md)) |
| H: Foundry + APIM ゲートウェイ | 複数デプロイ / 複数リージョンを APIM で束ねる | GA(APIM 側機能) | 複数チームへの払い出し、トークン課金の可視化、フェイルオーバー | APIM の運用コストと単一障害点化に注意 |
| M: Managed compute(2026-11-22 追加) | オープンモデル(Hugging Face 等)を専用 GPU で配置 | **GA**(2026-11-20。GA 一覧表 11-17 版で Models 行の Preview 注記が消えた) | カタログの従量にないオープンモデル、FT 済みオープンモデルの配置 | **Data Zone は US / EU のみ(APAC なし → 日本は Global)**。H200 追加・CVE パッチ自動適用。**組み込みの Content Safety はデータ経路にない**(L8 は S)。オートスケールの記載なし、LoRA は preview・BYOW は limited preview |
| M: パートナーのサーバーレス(Baseten / fal、2026-11-22 追加) | Baseten on Foundry(serverless、Global または US Data Zone)・fal の動画生成 | プレビュー | 試験的に新しいオープンモデル・動画モデルを使う | **Microsoft の Product Terms・DPA の対象外**(Fireworks は DPA 適用)。Baseten の pay-per-token はリタイア予告 30 日。規制案件の必須経路に置かない |
| S: 他クラウド / セルフホスト | OpenAI 直、Bedrock、vLLM on AKS 等 | — | マルチクラウド要件、ロックイン回避、特殊モデル | Foundry のガードレール・観測・エージェント機能を一切使えない |
| S: Foundry Local / Azure Local | オンデバイス / オンプレ推論 | GA(2026-04-09 に公式ブログで GA 宣言: https://devblogs.microsoft.com/foundry/foundry-local-ga/ 。docs ページにはラベルなし) | 閉域・エッジ・オフライン | サーバー用途は非推奨と明記。モデル選択肢が限られる(2026-11-22: Foundry Local 2.1 で BYOM〈自前モデルの持ち込み〉と Azure Local へのデプロイが加わった — [07 §9](./07-usecase-regulated-edge.md#9-エッジ・オンプレ・ハイブリッド)) |

**Spillover(PTU→Standard 溢れ処理)** は PTU 枯渇時に同一リソースの standard デプロイへ自動転送する GA 機能で、「PTU でベースライン + スパイクは従量」という現実的な構成を Foundry 側だけで組める。DeepSeek / Llama は非対応。

**モデルライフサイクルが最大の運用リスク。** GA モデルは提供開始から**概ね 18 か月(Anthropic / DeepSeek / Fireworks / Mistral AI の GA モデルは 12 か月)**でリタイア、通知は 60 日前。提案の温度感は Azure OpenAI 18 か月・パートナー系 12 か月。Standard 系は自動アップグレードされるが Provisioned は手動移行。つまり **PTU を使うほどモデル更改の計画運用が必須**になる。詳細は [features/02-models](../features/02-models.md)。**2026-11-22 の例:** gpt-4o(2024-05-13)は 2027-01-14 リタイアで、**Global / Data Zone Standard だけが gpt-5.1 に自動アップグレードされ、PTU と Batch は手動移行**。o-series の後継 gpt-5.6-sol / terra は **Batch・Regional Standard で提供されない**(代替は Global / US DZ Batch → gpt-5.4 系、EU DZ Batch → gpt-4.1 系、Regional Standard → gpt-5.1)。さらに「到来」と記録した日付が後から延びた例(MAI-Image-2.5 系・Kimi-K2.7-Code・model-router 旧版)もあり、リタイア表は期限の直前に再確認する([10 章](./10-migration-antipatterns.md#1-確定済み廃止スケジュールと設計への影響))。**GPT-5.6 以降は prompt cache の書込が課金対象**(12 時間 TTL の書込は 2026-11-01 利用分から、PTU の 12 時間書込の重みは 2.5)で、キャッシュ前提の見積もりに書込コストを足す。

---

## L2. オーケストレーション(エージェントの制御ロジック)

技術選定でいちばん論点になるレイヤー。

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: Prompt agent | 指示文 + モデル + ツールの宣言的定義。ランタイムコード不要 | GA | 単一エージェント、ツール呼び出しループが素直、立ち上げ最優先 | 分岐・ループ・リトライの明示制御ができない。**2026-11-22:** GPT-6 系の function tools は Astra・6.1-sol・6.2 系が **Responses API のみ**、Sol・Luna・6.1-terra は Chat Completions で tools を送るなら毎回 `reasoning_effort: none` が必要(reasoning 2026-11-20 版。2026-09-11 の「撤廃」記録は撤回)→ tool calling を伴うアプリは Responses API に寄せる |
| M: Prompt agent × Microsoft Copilot harness(2026-11-22 追加) | prompt agent の実行ランタイムを Microsoft 運用のエージェントループ+会話ごとのサンドボックス(ファイル読み書き・Shell・URL 取得・サブエージェント・skills)に切り替える。作成時に選択 | **パブリックプレビュー**(devblogs 2026-10-28・Learn とも preview。GA 一覧表に行なし)。**2026-12-01 からサンドボックスに従量課金**(0.0994 USD / vCPU 時・0.0118 USD / GiB 時、ブログ) | コードを書かずにファイル処理・コマンド実行・委任を伴う作業をさせたい | 22 リージョン(**Japan East 可、Japan West・East US 2 不可**)、**BYOM・Foundry Memory 不可**、既存エージェントの切り替え不可、呼び出しはエージェントのエンドポイント限定。生成ファイルの取得が 403 になるのはエージェント ID に Foundry User がないため。ツールガバナンスの Policy の検査対象外([features/03](../features/03-agent-service.md)) |
| M: ビジュアル Workflows | ポータルのマルチエージェントデザイナー | プレビュー + **2026-12-01 廃止**(2026-11-22 時点で残り 9 日。GA 一覧表 11-17 版も同日付) | (新規採用は非推奨) | **長期案件で提案してはいけない。** 移行先は MAF / Logic Apps / A2A |
| M: Routines | タイマー(1 回)/ 定期(cron)/ イベント(GitHub issue・Teams チャネルメッセージ)でエージェントを起動 | **GA**(2026-09-24 公式ブログ・GA 一覧表。旧: プレビュー) | 定期実行・イベント駆動の単純な自動化 | 1トリガー + 1アクションのみ(prompt / hosted agent を 1 つ呼ぶ。workflow agent 不可)。多段オーケストレーション不可。**Japan West・UK West・Switzerland West・UAE North・Norway East で非対応**。VNet 保護プロジェクト対応・**CMK 非対応**。定期は最短 5 分間隔。実行 ID は既定 agent identity(作成者 ID は明示オプトイン)。自己再起動用の reminder ツール(hosted 専用)はプレビュー( https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/routines ) |
| M: A2A ツール | エージェント間をプロトコルで接続 | **GA**(`a2a` ツール型 = A2A v1.0 が GA。旧 `a2a_preview` 型 = v0.3 はプレビュー。agent-to-agent 2026-09-11 版・移行ガイド 2026-09-11 版。旧: プレビュー) | 疎結合な委譲、組織をまたぐエージェント連携 | v1.0 は JSON-RPC・テキストのみ・ストリーミング非対応。**incoming A2A の有効化のみ**ポータル未対応(REST/SDK。A2A ツール接続の作成・発信側の構成はポータルで可能)。**incoming A2A はバージョン指定(`A2A-Version` ヘッダー等)が無いとプレビューの v0.3 で応答する**ため本番は v1.0 を明示。A2A のタスク・コンテキストは最終書き込みから 60 日保持 |
| H: Hosted agent + MAF | 自前オーケストレーションコードを Foundry が実行 | GA(MAF 1.0 も GA)。**長時間実行の回復(long-running resiliency)は 2026-11 に GA**(devblogs・Learn。GA 一覧表に行なし) | 分岐・HITL・チェックポイント・ミドルウェアが要る本番 | Python / C# のみ。**初期プレビュー基盤は 2026-08-20 でサポート終了済み**(未移行なら要再デプロイ)。**2026-11-22:** MAF は `agent-framework-foundry` 1.16.2 で `azure-ai-projects<3` に緩和(2.8.0 以降と同居可)した代わりに **Python 3.11 以上・MCP SDK 2.x が必須**、ワークフローのスパン名が `invoke_workflow` に変わった([features/08](../features/08-developer-experience.md)) |
| H: Hosted agent + LangGraph 等 | LangGraph / Semantic Kernel / CrewAI / カスタムコードを持ち込み(公式明記。プロトコルライブラリはフレームワーク非依存のため任意のフレームワークが利用可) | GA(持ち込み枠) | フレームワーク資産がある、型付きステート・タイムトラベルが要る | Foundry 固有機能(Memory 等)との結合は自分で書く |
| H: MAF + Durable Extension | エージェント実行に**耐久実行**を付与。ステップ単位チェックポイント・障害回復・分散ホスト間スケール | MAF 1.0 は GA。~~拡張は Python パッケージ `agent-framework-durabletask` / `-azurefunctions` が 1.0.0b260922(beta)で、拡張単体は GA 前~~ → **2026-11-09 に Python 1.0.0 / .NET 1.16.0 の stable 版**(Learn の導入手順は `--pre` のまま。1.22 以降のレコードがあるストアで新旧ワーカーを混在させない — features/08) | 数時間〜数日の長時間プロセス、確実な再開が必須 | バックエンドは Durable Task Scheduler 推奨。ホストは Azure Functions か自前コンピュート |
| S: 自アプリ内オーケストレーション | 既存アプリのコードでループを回し Responses API だけ叩く | GA(API) | 既存システム組込み、ロックイン回避、独自 SLA | **自前オーケストレーションのメトリクスは Foundry のエージェントビューに出ない**(Foundry はマネージドエージェントしか見えない)。**2026-11-22 緩和:** LangGraph / LangChain / CrewAI 等で書いた Foundry 外のエージェントを **external agents として登録すると、トレース(GA 一覧表でも GA)・Insights・スケジュール型のトレース評価を Foundry で使える**(2026-11-18 GA。人手評価・red teaming のターゲット化・イベント起動の継続評価は非対応。登録はトラフィックを中継しない)— [09 §3](./09-operations.md) |
| S: Logic Apps / Durable Functions | ワークフローエンジン側が主で、AI は 1ステップ | GA | 承認・長時間待機・既存業務フロー統合が主役 | AI 部分の反復開発は遅くなる |

```
   ┌── 制御をどこが持つか ───────────────────────────────────┐
   │                                                          │
   │  Foundry が持つ            アプリが持つ         外部が持つ │
   │  ┌───────────────┐   ┌─────────────────┐  ┌────────────┐ │
   │  │ Prompt agent  │   │ Hosted agent    │  │ Logic Apps │ │
   │  │ Routines      │ ← │  (MAF/LangGraph)│ →│ Durable Fn │ │
   │  │ Workflows(廃) │   │ 自アプリ + API  │  │ Copilot St.│ │
   │  └───────────────┘   └─────────────────┘  └────────────┘ │
   │   速い/軽い            制御可/テスト可       業務フロー主導 │
   │   移植性 低            移植性 中〜高          AI は部品     │
   └──────────────────────────────────────────────────────────┘
```

**選定の決め手は「明示的な状態遷移が要るか」。** 要件に「承認待ちで数時間〜数日停止」「失敗したステップだけ再開」「監査のために各ステップの入出力を保存」が含まれた瞬間に M では足りず、H(MAF / LangGraph)か S(Durable な基盤)になる。逆に「FAQ に答える」「1〜2 個のツールを呼ぶ」なら M で十分で、コードを書くのは過剰。

**Connected agents は新 Foundry には無い。** classic の機能で、移行ガイドは A2A ツールを推奨している。ポータルだけでマルチエージェントを組む前提の提案は成り立ちにくくなった。

---

## L3. 会話状態(スレッド / セッション)

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: Agent Service Conversations(basic) | Microsoft 管理ストレージに会話が保存される | GA | 社内利用、データ所在に強い要求がない | データの所在・保持期間をこちらで制御しにくい。**2026-11-22:** basic は conversations / items / responses を **60 日で自動削除**(期限切れは 404、復元不可)と明記(limits-quotas-regions 2026-11-18 版)。直接の Responses API 呼び出しで保存される履歴は**管理ストレージのまま CMK 対象**になったが、**prompt agent は管理ストレージでは CMK 非対応(BYO 時のみ)**のまま |
| H: standard setup(BYO) | 自分の Cosmos DB / Storage / AI Search に保存 | GA 相当 | データ所在・バックアップ・削除要件がある案件 | **2026-11-22:** standard も自前 Cosmos DB の `run-state-v1` コンテナに既定 TTL 60 日(変更可)— 長期保存が要件なら TTL を延ばすか写しを持つ。**セットアップ時にしか選べない。**後から basic→standard の切替は再構築。**2026-09-26 追記:** BYO リソースの宣言は capability hosts から **capability settings(account / project、プレビュー、API `2026-07-15-preview`。現時点の提供は UK South / Canada Central のみ)**へ移行中で、capability settings は既存プロジェクトに追加・変更できず**プロジェクトの削除・再作成**が必要( https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-capability-settings )。**2026-10-14 要確認: この設定ページは 301 で agents/environment-setup(capability settings の記述なし)へ転送されるようになり、プレビューの取り下げか移設中かは判断できない**(capability-hosts・standard-agent-setup・virtual-networks は旧 URL を参照したまま capability settings を前提に書かれ、create-resource-terraform〈10-09 版〉の対応表は「capability host」行を復活。展開リージョン〈UK South / Canada Central〉は再確認不能)→ 当面は capability host 前提で設計する(2026-11-22: 301 は不変。BYO リソースの表記は「Storage / Foundry IQ (Azure AI Search) / Cosmos DB」に統一) |
| S: 自前セッションストア | 会話は自アプリの DB に持ち、モデル呼び出しはステートレス | GA(API) | マルチテナント分離、既存の会話履歴資産、法定保存 | プロンプト組み立て・トリミングを自分で実装 |

**メッセージ 10 万/スレッドなどの固定リミットは引き上げ不可。** 長期にわたる 1 スレッド運用(例: 常設の業務チャネル)を想定するなら S 側に倒すか、定期的にスレッドを切る設計にする。

---

## L4. 長期記憶(ユーザープロファイル / 手続き記憶)

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: Foundry Memory | user profile / chat summary / procedural の 3 種を抽出・統合・検索 | プレビュー | パーソナライズを短期で試したい | **VNet 非対応。**19 リージョン。100 scope/store・10,000 memories/scope。プレビュー中の課金体系変更が明記。**2026-10-14 追記(memory-usage 2026-10-06 版、引き続きプレビュー):** メモリ項目の CRUD・ストア既定の TTL(`default_ttl_seconds`。作成時のみ設定可で、変えるならストアを作り直す)・remember / forget コマンドが追加。検索ツールの出力が `results` → `memories` に変わったので生ペイロードを読むパーサーは要修正。利用者の分離キーは `x-memory-user-id` ヘッダー(無ければ Entra トークンの `{tid}_{oid}`)で、hosted agent のセッション分離の `x-ms-user-identity` とは別。**2026-11-22:** GA 一覧表は Memory = Preview のまま、VNet 非対応・19 リージョンも不変。**Microsoft Copilot harness のエージェントでは Memory を使えない**。hosted agent のアプリ状態は Memory ではなく durable state store(L15)に置く |
| H: Memory + 自前ポリシー | Memory を使いつつ、保存可否・削除をアプリ側で制御 | プレビュー | 個人情報の取扱いを自分で説明する必要がある | プレビュー機能への依存は残る |
| S: 自前記憶 | 要約 + ベクトル検索 + 有効期限を自分で実装 | — | 規制業種、閉域(VNet 必須)、削除権対応 | 記憶の品質チューニングを自分でやる必要 |

**閉域要件があるなら現時点で Memory は選べない**(VNet 非対応)。ここは「プレビュー機能を本番に載せない」という一般則以前の、機能的な非互換。

---

## L5. ナレッジ / RAG

Foundry で最も選択肢が多く、コストと品質の差が出るレイヤー。3 層に整理できる。

> **2026-11-22 改称:** Azure AI Search は **「Foundry IQ (Azure AI Search)」**に改称された(リソース型 `Microsoft.Search`・`*.search.windows.net`・API 版・RBAC・課金メーター名は不変)。本書では文脈に応じて「AI Search」の表記を残す。Search データプレーン安定版 **`2026-10-01`** で、LLM クエリプランニング・answer synthesis・reasoning effort の low / medium・File / indexed Azure SQL / **indexed SharePoint** のナレッジソース・document-level 権限(SharePoint ACL・ADLS Gen2 ACL / RBAC・Blob RBAC)が GA(`auto` effort・remote SharePoint・Fabric・MCP・Work IQ ソース・Purview ラベルは preview)。詳細は [04 章](./04-usecase-chat-rag.md)・[features/04](../features/04-tools-knowledge.md)。

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: File Search | ファイルを上げるだけでベクトルストア化・ハイブリッド検索 | GA | PoC、部門内文書、数千ファイル規模 | **埋め込みは text-embedding-3-large(256次元)固定、チャンク 800 / オーバーラップ 400 は既定値**(公式表記は Default。変更用パラメータの記載はない)。10,000 ファイル/ストア、エージェント・会話に各 1 ストア。追加課金あり |
| M: Foundry IQ(knowledge bases) | 複数ソースを束ね agentic retrieval(クエリ分解→並列検索→再ランク)で照会 | 一部 GA / 一部プレビュー(ポータル体験は全プレビュー。GA 一覧表の行名は「Knowledge (Foundry IQ (Azure AI Search))」= Partial GA。2026-11-22: API 側の GA 範囲が `2026-10-01` で拡大 — 上の注記) | 複数エージェントで同じ知識を共有、ACL / Purview 連携 | エージェントからは **MCP ツール経由**。SDK 対応は Python + REST のみ。**2026-11-22:** **KB 接続にユーザートークンがないときの挙動は Learn のページで食い違う**(foundry-iq-connect = 絞らずに返す〈fail-open〉、retrieve・query-time ACL のページ = ACL 付きの文書は返さない)→ 権限トリミングが要るならユーザートークンの転送を必須にして試験する。Serverless の GA は両論(Search Learn = GA / Azure ブログ = 2026-12 GA)、プロジェクト内蔵のマネージド Foundry IQ・Microsoft Retriever 1・ナレッジグラフは preview |
| H: Azure AI Search ツール | 既存インデックスに直結、引用付き | GA | 既に AI Search 資産がある、索引設計を自分で持ちたい | **1 ツール 1 インデックス。**同一テナント必須 |
| H: 自前索引 + Foundry から検索 | AI Search を自前パイプラインで作り、エージェントからは検索 API を叩く | GA | チャンク戦略・メタデータ・セキュリティトリミングを作り込む | 取り込みパイプラインの運用は自分持ち |
| S: 完全自前 RAG | 任意のベクトルストア(Cosmos DB / PostgreSQL+pgvector 等)+ 自前検索 | GA(各サービス) | マルチクラウド、既存 DB に相乗り、コスト最適化 | 再ランク・ハイブリッド・評価まで全部自作 |
| M: Web search / Grounding with Bing | 公開 Web をリアルタイム検索 | GA | 最新情報が要る一般用途 | **DPA 対象外・コンプライアンス境界外へデータ送信・別課金。**規制業種では原則不可。**2026-11-22:** 直付けの Web search は **Web IQ**(Web IQ の利用規約に従い境界外で処理されうる)、**toolbox 経由は Grounding with Bing**(DPA 非適用・境界外転送・GCC 等のコミットメント放棄の注記はこちら)と経路で条項が分かれた。`external_web_access` は常に false 扱い |
| M: SharePoint / Work IQ / Fabric IQ | M365・Fabric のデータに OBO で接続 | プレビュー(2026-11-22: **Foundry IQ の indexed SharePoint ナレッジソースは GA**〈private ingestion は Dedicated の S2 / S3 / L1 / L2 のみ〉で、remote SharePoint・SharePoint ツールとは別物。Work IQ は Learn = 標準 MCP 経路 GA / 組み込み `work_iq_preview` = preview、ブログ = preview の両論) | 社内文書・業務データの横断 | **M365 Copilot ライセンスまたは Retrieval API の pay-as-you-go 課金が必要**(SharePoint / Work IQ)。Work IQ は VNet 非対応。app-only 不可(ユーザー ID 必須) |

**File Search の既定値を受け入れられるかが一次判断ポイント(埋め込みモデルは text-embedding-3-large 256 次元で実質固定)。** 「日本語の長文契約書」「表が多い技術文書」のように、チャンク 800 トークン(既定)では品質が出ないと分かっている文書群では、最初から H 以上を選ぶ。逆に FAQ・議事録・マニュアル程度なら M で十分なことが多い。

**取り込み(ingestion)は Foundry の外側の話**である点に注意。Document Intelligence(決定論的な OCR・レイアウト抽出)と Content Understanding(LLM によるスキーマ抽出)の使い分け、そのバッチ実行基盤(Functions / Container Apps jobs / Data Factory)は自分で設計する。詳細は [08 の IDP ユースケース](./08-usecase-specialized.md)。

---

## L6. ツール実行(外部システム連携)

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: OpenAPI ツール | OpenAPI 3.0/3.1 仕様で外部 API に接続 | GA | 仕様が整備された社内 API | 認証は anonymous / API キー / マネージド ID。API キーは 1 スキーム/ツール。**OAuth identity passthrough は非対応(toolbox 経由でも不可)**(2026-11-22 明記)→ 利用者の権限で叩くなら MCP サーバー化か自前 OBO |
| M: MCP ツール | リモート MCP サーバーのツール群に接続 | GA | SaaS 連携、再利用可能なツール群 | 長時間実行はプレビュー。個別サーバーにプレビューあり。**2026-11-22:** カスタム MCP エンドポイントの APIM 自動登録は廃止(ゲートウェイ経由のエンドポイントを手で指定。直接のエンドポイントを使うとゲートウェイのポリシーを迂回する) |
| M: Azure Functions ツール | キュー経由で Functions を非同期呼び出し | **要確認(公式間不整合)**: how-to ページは新 Agent Service の手順を掲載するが、移行ガイドのツール対応表(2026-09-11 版)は Foundry (new) = **No**( https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/migrate#agent-tool-availability )。旧記載「GA」は classic 側の表記 | 独自ロジック、既存 Functions 資産 | **standard セットアップのみ(basic 不可)** |
| M: Logic Apps コネクタ → MCP 変換 | 1,400+ コネクタのアクションをツール化 | プレビュー | SaaS・基幹の広範な接続を短期で | 1 コネクタ/ツール、**OAuth 2.0 コネクタ非対応**、マネージドコネクタのみ |
| H: Toolbox | 複数ツールを 1 つの MCP 互換エンドポイントに束ね、バージョニング・集中認証 | **GA**(GA 一覧表 https://learn.microsoft.com/en-us/azure/foundry/concepts/general-availability に Toolboxes = GA と明記。現行 REST は api-version=v1 で特殊ヘッダー不要) | ツールの再利用と統制、MAF / LangGraph からも同じツールを使いたい。**2026-09-24 追記:** Azure ブログは「hosted agent 向けは GA、prompt agent への拡大はパブリックプレビュー」、Toolbox 内の **Tool search は GA** と告知( https://azure.microsoft.com/en-us/blog/ship-agents-faster-with-expanded-model-choice-voice-agents-and-continuous-optimization/ ) | Code Interpreter / File Search を toolbox 経由で使うと**ユーザー分離なし**。**2026-11-22:** Tool search は Learn も GA になり揺れ解消。prompt agent の Toolbox はブログ = preview / Learn = 区別なし。ツールガバナンス(Azure Policy の承認ツール+プロジェクトの `toolControls`、preview)は toolbox と prompt agent の保存時・実行時を縛るが、**hosted agent のコードと Copilot harness は Policy の検査対象外**([05 B1](./05-usecase-agent-automation.md#b1-単一エージェント-基幹-api-参照系中心)) |
| S: アプリ内 function calling | ツール定義とディスパッチを自アプリで実装 | GA | 既存の権限モデルに合わせた細かい認可、監査 | ツールカタログ・集中管理の恩恵はない |

**Hosted agent はツールを直付けできない。** 「Adding tools directly to hosted agent's definition is not supported. We recommend using toolboxes in Foundry」と明記されており、hosted agent の定義ではツールの直接指定が非サポート(prompt agent の `create_version` には `tools` が現存)。**コードファーストを選んだ時点で、ツール層は Toolbox(MCP エンドポイント)経由が前提**になる。Toolbox はバージョニングと集中認証(資格情報の注入・トークン更新・ポリシー適用)を担うため、これは制約であると同時に統制上は利点でもある。

**ツール設定は実行時に上書きできる。** `file_search.vector_store_ids`、`code_interpreter.container`、`mcp.server_label/server_url/headers` はリクエスト単位で差し替えられる。**テナントごとにナレッジベースを切り替える、dev/stg/prod で同じエージェント定義を使い回す**といった構成が、エージェントのバージョンを増やさずに組める。

**認可の設計が本命の論点。** エージェントが基幹システムを叩くとき、「エージェントのマネージド ID で叩く(app-only)」のか「ログインユーザーの権限で叩く(OBO)」のかで監査要件の満たし方が変わる。SharePoint / Fabric IQ / Work IQ は **OBO 必須で app-only 不可**であり、バッチ的な無人実行ができない。

---

## L7. コード実行サンドボックス

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: Code Interpreter | サンドボックスで Python 実行(データ分析・作図) | GA | アドホック分析、グラフ生成 | セッション課金(アクティブ 1h / アイドル 30min)。**アウトバウンド通信不可**。リージョン制限 |
| H: Custom Code Interpreter | 独自 Python パッケージ・コンピュート・Container Apps 環境を指定。コンテナは MCP サーバーとして公開される | プレビュー | 独自ライブラリが要る分析 | **standard setup のみ。**`az feature register --namespace Microsoft.App --name SessionPoolsSupportMCP` が事前に必要。Foundry Owner + Container Apps ManagedEnvironment Contributor ロール。**デプロイに最大 1 時間。**ファイル入出力は API 非対応で **URL 経由(大きいファイルは Blob の SAS URL)** |
| S: Container Apps dynamic sessions を直接使う | Hyper-V 分離のセッションプールを自アプリから呼ぶ。プレウォームでミリ秒起動 | GA(ACA 側) | 実行の課金・監査・ネットワークを自分で制御したい。数百〜数千の同時セッション | 自分でセッション管理 |

Code Interpreter の基盤は Container Apps dynamic sessions なので、**「Foundry 経由で使う」か「ACA を直接使う」かは同じ技術の窓口違い**である。untrusted なコードを実行する要件なら、どちらでも Hyper-V によるカーネルレベルの分離が効く(Well-Architected でも「ユーザー投稿 / AI 生成コードには dynamic sessions を使え」と推奨されている)。**閉域構成では Code Interpreter はファイルの上り下りを伴わないシナリオしか動かない**点に注意。

---

## L8. ガードレール・安全性

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: 既定ガードレール(Microsoft.DefaultV2) | 4 カテゴリのコンテンツフィルター。編集不可 | 既定適用 | 全案件のベースライン | テキスト・画像とも既定閾値は **Medium**( https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/default-safety-policies 2026-05-31 更新の表)。**2026-10-14 更新:** 出典は https://learn.microsoft.com/en-us/azure/foundry/guardrails/default-safety-policies へ移動(旧 URL は 301、ms.date 2026-10-08)。適用除外は「transcription(文字起こし)モデル」と明記され、それ以外の音声モデルには Audio models の既定表がある。**既定(バッファあり)のストリーミングでも応答の最後の区切り(末尾約 15〜30 語)はフィルター適用前に届きうる**(content-streaming 2026-10-13 版 → [06 C1](./06-usecase-customer-facing.md#プロンプトインジェクションと安全性)) |
| M: カスタムガードレール | リスク × 介入ポイント × アクションで構成 | モデル向けは GA 相当 / **エージェント向けはプレビュー** | 閾値調整、PII、Prompt Shields、ブロックリスト | 介入点は User input / Tool call / Tool response / Output。Tool 系はプレビュー。**2026-11-22 訂正:** 有害カテゴリの「Off」で承認制(Modified Guardrails)なのは**出力側だけ**で、入力側の Off は全顧客が選べる(表名は「Blocking levels」に)。hosted agent のエージェント境界の検査(Hosted agent content safety、出力は Default〈同期〉/ Asynchronous filter)は preview |
| M: ブロックリスト | 完全一致 / 正規表現の禁止語 | GA 相当 | 固有名詞・禁則語の統制 | **Azure OpenAI モデル限定。**1 リスト 1 万語、反映まで約 5 分 |
| S: Content Safety API を自前で呼ぶ | ガードレールの分類器をアプリから直接使う | GA | Claude 等の非対象モデル、managed compute のオープンモデル(組み込み Content Safety がデータ経路にない)、独自の前後処理 | レイテンシとコストを自分で管理。**2026-11-22: preview 6 機能が 2027-04-30 廃止** — Groundedness detection(Content Safety と Foundry ガードレールの Groundedness)・Custom categories (rapid)・Analyze Multimodal・接続 / 非接続コンテナー・Embedded SDK。Prompt Shields・有害性・保護素材・PII・Task adherence・ブロックリストは対象外。接地性の検査を自前で組むなら評価器か自前の検証に寄せる |
| S: 自前ポリシーエンジン | 出力の業務ルール検証、承認フロー | — | 業種固有の禁止事項、金額・権限チェック | 実装・保守コスト |

**Claude を使うなら自前実装が必須。** 「Foundry doesn't provide built-in content filtering for Claude models at deployment time」と明記されており、Claude を選んだ時点で L8 は M から S に落ちる。これはモデル選定がアーキテクチャを変える典型例で、提案時に見落としやすい。

**分類器は更新される(2026-11-22 追記)。** Content Safety の分類器の 2026-10 更新が Spain Central から段階展開中で、同じ入力でもブロック判定が変わりうる。閾値を詰めた案件は代表データでの再試験をリリース手順に入れる([09 §6](./09-operations.md))。GPT のテキスト透かし(`gpt-6.2-sol` / `-astra`、デプロイ単位の `textWatermarking`、既定 Disabled)も加わった。また **2026-11-01 以降に提供開始したモデルは Modified Abuse Monitoring の対象外**(告知日から。gpt-6.2 系が該当)になり、「悪用監視のデータ保存をオプトアウト済み」を前提にした規制案件はモデル選定で崩れうる([07 章](./07-usecase-regulated-edge.md))。

**エージェントに明示割当てしたガードレールは、基盤モデル側の設定を完全に上書きする。** Tool call / Tool response にコントロールを置き忘れると、その経路が未スキャンになる。

**hosted agent のガードレールは「付けたつもり」で素通りしうる(2026-09-26 追記)。** Invocations プロトコルでは `rai_config` に `invocations_moderation`(本文のどこにテキストがあるかの宣言。`azure-ai-projects` 2.7.0 以上)が無いとポリシーは**無効のまま HTTP 200 で通る**。また存在しないポリシー ID を参照してもエージェントは作成・active になり、**フェイルオープンで無フィルタになる**と公式が明記している。Responses プロトコルなら `rai_policy_name` だけで効く。デプロイ後に有害プロンプトでの遮断を必ず実測する( https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/add-hosted-agent-guardrails 2026-09-24 版)。

---

## L9. ID・認証・認可

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: Entra ID + 組込み RBAC | Foundry User / Project Manager / Account Owner / Owner / Agent Consumer の 5 ロール | GA | 標準的なエンタープライズ | **2026-11-22(rbac-foundry 11-18 版):** `agents/write` を持つ主体はエージェントを介さずプロジェクトの Responses エンドポイントで推論できる、エージェントスコープの割り当てはプロジェクトのファイルを分離しない、Foundry ロールではコストが見えない(Cost Management Reader を別途)— [01 §5.2](./01-official-baselines.md#5-2-rollout-planning-トポロジー決定表)。ロール割り当ての手段として公式に載っているのはポータル / Azure ポータル IAM / Azure CLI(**SDK での割り当ては記載なし**。旧記載「SDK 非対応と明記」は出典に該当記述がなく features 側で 2026-07-30 に訂正済みのものを同期)。改名ロールアウト中のため IaC は GUID 指定推奨 |
| M: API キー | キー認証 | GA | 検証用途のみ | **Agents / Evaluations / Content Understanding / workflows は Entra 必須でキー不可。**本番は `disableLocalAuth` を推奨 |
| H: OBO(ユーザー委任) | ログインユーザーの権限で下流データにアクセス | ツール依存 | 「ユーザーが見える情報しか答えない」要件 | SharePoint / Fabric IQ / Work IQ は OBO 必須。無人バッチと両立しない |
| H: toolbox 経由の利用者委任(2026-10-06 追加) | toolbox の接続に `oauth2`(OAuth identity passthrough)/ `user-entra-token` を設定し、Foundry がトークン取得・更新・利用者ごとの分離を行う。MAF hosted agent は `FoundryToolbox` / `AddFoundryToolboxes` が `x-agent-foundry-call-id` を転送 | Toolbox は GA(個々の認証種別のステータスは features 参照) | **MCP 等のツールの委任では公式推奨**(2026-09-29〜10-02 の 4 ページ) | 利用者に Foundry Agent Consumer 以上・**テナント一致(クロステナント不可)**・初回同意フロー。「401/403 なしで別人の権限で動く」= 呼び出し元文脈の欠落 → 2 人の利用者で出し分けテスト。アプリ管理 OBO(`x-client-*` 転送)との使い分けは [05 B1](./05-usecase-agent-automation.md#b1-単一エージェント-基幹-api-参照系中心) |
| H: エージェント ID の認可(2026-11-22 追加) | エージェント ID・AgentBlueprint・エージェント ID による OBO(A2A 接続の `AgentOnBehalfOfUser` 等) | **プレビュー**(新設ページ群) | エージェントごとに下流権限を分けたい | 新しい認可スキームは preview。既存の agent identity / マネージド ID 前提の設計を置き換える段階ではない([features/03](../features/03-agent-service.md)) |
| S: 自前認可レイヤー | アプリでテナント・ロールを判定し、検索フィルタや権限に反映 | — | マルチテナント SaaS、細粒度 ACL | セキュリティトリミングの正しさを自分で保証 |

---

## L10. ネットワーク

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: パブリックエンドポイント | 既定 | GA | PoC、社外公開サービス | — |
| M: Private Link(インバウンド) | プライベートエンドポイント + 3 種の DNS ゾーン | GA 相当 | 社内からのみアクセス | — |
| H: Standard setup / BYO VNet 注入 | `Microsoft.App/environments` 委任サブネット(/27 以上、推奨 /24)にコンテナ注入 | GA 相当 | エージェントのアウトバウンドを自社 VNet 内に維持 | **後付け・変更不可(再デプロイ必要)。**リソースと VNet は同一リージョン。サブネットは Foundry リソース専用。**2026-11-22:** ネットワーク構成は**最初の hosted agent 作成時に確定**(別構成は新プロジェクト)。hosted のセッションは**サブネット IP を共有(GA)**し /24 で計画上約 60,000 セッション(実質の上限は同時セッションクォータ 2,000 / 1,000)。**PE を `192.168.0.0/24` に置かない** |
| H: Managed Virtual Network | Microsoft 管理 VNet + マネージド Azure Firewall | 要確認(ラベルなし)・**ポータル UI 未対応** | VNet 運用を持ちたくないが外向き統制は要る | 有効化後の無効化不可、BYO VNet からの移行パスなし。対応 18 リージョン |
| S: すべて自社 VNet 内 | Foundry を使わずセルフホスト | — | 完全閉域・オフライン | Foundry の機能を捨てる |

**ネットワーク分離で使えなくなるツールがある**のが最大の落とし穴。Traces の VNet 対応は公式ドキュメント間で不整合(configure-private-link は Not supported、GA 一覧は Tracing VNet: Preview。安全側は非対応前提で設計)、Memory は VNet 非対応、Work IQ は VNet 統合非対応、Logic Apps / Browser Automation / Computer Use / Image Generation は「Not supported / Under development」と明記されている(**2026-10-14:** Browser Automation はツールページ本文が「generally available」と書くようになったが〈移行ガイドの表・TOC は preview のまま〉、configure-private-link の表は Not supported のままで、**GA 表明と閉域対応は別物**)。**File Search は公式ツール表の 2026-08-14 版で「Supported / Through private endpoint」に変わった**が、Blob Storage のファイルを File Search で使う構成は非対応のまま([03 章 G2](./03-decision-guide.md#g2-ネットワークゲート))。**閉域案件では「使える機能の一覧」から設計を始める**必要がある。**2026-11-22 更新:** Browser Automation の閉域は公式間で割れた(configure-private-link のツール表 = **Supported** / toolbox-network-isolation = **Not supported**。private website access は別の preview)— 両論のため閉域の必須経路には置かない(本ドキュメントの判断)。**voice agents の電話系チャネル(Teams Phone / Twilio / SIP)と発信は閉域プロジェクトでは使えない**と明記された(電話窓口は非閉域プロジェクトに分けるか Voice Live を自前で使う — [08 E1](./08-usecase-specialized.md#e1-音声エージェント-コンタクトセンター))。

閉域固有の実務上の落とし穴を挙げる。

- **hosted agent のエンドポイント自体は公開アドレスのまま**(hosted agent の GA 後も virtual-networks ページの azd 手順の表は「No, in this preview」のまま。2026-09-26 確認)。 セッションはユーザー ID で分離されるが、「エンドポイントをプライベートにする」のはプラットフォーム側の未提供機能と明記されている。「閉域なのでエンドポイントも内部だけ」という前提で設計すると崩れる。**2026-11-22 要確認:** virtual-networks(2026-11-17 版)の azd 節の書き直しでこの記述が消え、networking-options は「egress を VNet に閉じる構成では Foundry エンドポイントへのインバウンドも PE 経由」とするが、公開到達性を明示に否定する記述もない → 閉域要件の案件は実機で公開側から到達しないことを確認する。
- **Firewall で TLS 検査をするなら Entra / マネージド ID の 3 FQDN を除外する(2026-11-22 追加)。** 社内 CA の証明書を信頼させる private CA trust(preview、ポータル非対応)が加わったが、プラットフォーム自身の Entra / MI 通信は対象外で、検査すると一覧取得などがタイムアウトする([01 B](./01-official-baselines.md#b-baseline-本番の出発点-waf-が-ai-ワークロードの推奨アーキテクチャ-と名指し))。
- **ACR のプライベート化は 2026-06-25 以降に作成したプロジェクトのみ。** それ以前のプロジェクトは ACR にパブリックエンドポイントが必要。
- **VNet 化後は公開インターネット上の端末から `azd up` / `azd deploy` ができない**(データプレーン呼び出しが 403)。VNet 内のセルフホスト GitHub Actions runner / Azure DevOps agent が公式の推奨パターンで、**CI/CD 基盤の追加コストとして見積もりに入れる必要がある。**
- **Azure Firewall と併用する場合、TLS インスペクション(自己署名証明書の挿入)は不可。** Container Apps のマネージド ID 系 FQDN、または `AzureActiveDirectory` サービスタグの許可が要る(2026-11-22: 上の private CA trust を使っても Entra 系 3 FQDN は検査除外が必要)。hosted agent の宛先制御は **network egress controls が GA**(Transform ルール・secret 参照ヘッダー・Azure Policy 統制は preview で日本リージョンなし)。

---

## L11. ゲートウェイ・流量制御

| 選択肢 | 実体 | 向く要件 | 制約・地雷 |
|---|---|---|---|
| M: Foundry のクォータのみ | デプロイ単位の TPM/RPM | 単一アプリ・単一チーム | チーム別の配分・課金按分ができない |
| H: APIM AI ゲートウェイ | トークンレート制限、トークン課金メトリクス、セマンティックキャッシュ、複数バックエンドの負荷分散・サーキットブレーカー | 複数チーム / 複数テナントへの払い出し、リージョン跨ぎ冗長 | APIM 自体の可用性設計・コストが乗る。**2026-11-22:** Foundry UI から新しい APIM を紐付けることはできなくなり、プロジェクト単位のトークン上限は Foundry では読み取り専用(変更は APIM のポリシー XML)、カスタム MCP の自動登録は廃止。既存 APIM は非推奨ではなく、そのまま動く |
| H: Azure AI Gateway(2026-11-22 追加) | APIM とは別のリソース型 `Microsoft.ApiManagement/aigateways`(`az aigateway`)。ハブが承認済みモデルをエイリアスで公開し、各プロジェクトは connected models として使う hub-and-spoke | 中央の AI ゲートウェイでモデル消費を集約したい組織 | GA 一覧表 Manage > AI Gateway = Preview(製品ページはライフサイクル表記なし、トークン上限は manage-costs = GA の両論)。Foundry 側の UI は段階展開中。閉域では新ポータルで作った AI Gateway は公開になる制約が残る。**Copilot harness は BYOM(ゲートウェイ越しのモデル)非対応** |
| M: Cost in Foundry / cost controls(2026-11-22 追加) | 予算超過を HTTP 429(`x-ms-budget-cause`)でブロック | 部門・プロジェクト単位でコストの上限を掛けたい | **preview**。対象は **GPT / o-series のみ**(PTU・ツール料金・hosted のコンピュートは数えない)、判定が遅れると **fail-open**、cost control を持つプロジェクトは削除不可、**Foundry ロールではコストが見えない**(Cost Management Reader が別途要る)、データは 8〜24 時間遅れ → 完全なハードリミットではない([09 §5](./09-operations.md)) |
| H: Front Door / App Gateway + WAF | 外部公開時のグローバル分散と WAF | 顧客向け公開 | L7 の保護は AI 特有の攻撃(プロンプトインジェクション)には効かない |
| S: 自前プロキシ | 独自のルーティング・課金 | 特殊な課金モデル | 実装・運用コスト |

**「複数の部門が同じ Foundry を使う」案件では L11 が事実上必須**になる。Foundry のクォータはデプロイ単位でしか切れないため、部門別のレート制限・使用量可視化・上限超過時の挙動を成立させるには APIM 層が要る。(2026-11-22 注記: Foundry 自身の統制〈アクセス制御・デプロイポリシー・クォータ・コンテンツフィルター・トレース・評価・コストの可視化〉にゲートウェイは不要と公式が明記し、プロジェクト単位の予算ブロックは cost controls〈preview〉で一部できるようになった。ただし部門別のトークンレート制限・按分メトリクス・バックエンドの冗長化は引き続きゲートウェイ層の仕事)

---

## L12〜L13. 可観測性・評価

| 選択肢 | 実体 | ステータス | 制約・地雷 |
|---|---|---|---|
| M: Foundry Tracing | OTel 準拠で App Insights に送信。ポータルで 90 日閲覧 | GA(prompt / hosted agent、**2026-11-22: 外部エージェントも GA** — GA 一覧表 11-17 版「GA for prompt, hosted, and external agents; Preview for workflow agents」)、workflow はプレビュー | **VNet 対応は公式間で不整合(configure-private-link は Not supported、GA 一覧は Tracing VNet: Preview。安全側は非対応前提で設計)**。**会話の中身(GenAI 機微属性 7 種)は公式では 2026-09-30 から専用テーブル `AppGenAIContent` に振り分け(Protected + Privileged Monitoring Data Reader で読み手を絞る手順は preview)。2026-10-06 の実測では従来テーブルとの二重書き** → [09 §3.6](./09-operations.md#3-6-トレースに会話の中身を残すか-hosted-agent-の選定基準)。**2026-10-14 追記:** Privileged Monitoring Data Reader は接続先 **App Insights リソースへの付与**で App Insights と Foundry の両方の画面で本文を読める(ワークスペースへの付与は、ワークスペース中心のクエリを直接打つ ID だけ)。hosted agent のコンテナ側は `azure-ai-agentserver-responses` 2.3.0 で**テレメトリ送出の既定が background**になり、要求の完了はテレメトリの到達を保証しない(従来どおりなら `AGENTSERVER_FLUSH_MODE=async`) |
| M: Trace Replay | 会話トレースの再生 | prompt / hosted は実質 GA | Log Analytics Reader ロール必須。2 スパン以上必要 |
| M: Monitoring ダッシュボード | トークン・レイテンシ・成功率・評価スコア | **プレビュー**(2026-11-22: Learn のラベルは外れたが GA 一覧表 Monitoring = Preview のためプレビュー扱いを維持。プロジェクト単位の Monitor は preview) | 本番の運用監視をこれ 1 本に依存しない |
| M: Insights(2026-11-22 追加) | 接続済み App Insights のトレースを GPT ジャッジで横断分析し、繰り返し起きる挙動を Insight(重大度・根拠トレース・推定原因・修正案)として提示。評価器を事前定義せずに未知の問題を見つける | **GA**(Azure ブログ・Book of News・`azure-ai-projects` 2.11.0。GA 一覧表に行なし) | 31 リージョンで **Japan East / West を含む**。SDK は 2.11.0 で `.beta` から移動した破壊的変更あり。insights → agent optimizer の連携は preview |
| M: Evaluations | 組込み評価器 + クラウド評価 | GA(一部評価器はプレビュー) | **Entra ID 必須(キー不可)**。モデルを呼ぶ評価は Foundry User を**アカウントスコープ**で、トレース評価はプロジェクト MI に App Insights の Reader(evaluation-permissions 2026-09-29)。**合成評価器 `builtin.output_quality` / `builtin.tool_use_quality`(preview)**は複数評価器を 1 回のジャッジ呼び出しに束ねる(ジャッジは GPT-5.6 系推奨)。`azure-ai-projects` 2.8.0 は Agent Optimization・データ生成・評価器ライフサイクル API を「GA」とするが GA 一覧表(Agent optimizer = Limited preview)と食い違う。**2026-10-14:** Rubric 評価器・traces→dataset・合成データセット・会話評価 / シミュレーション・Agent optimizer の Learn 機能ページから「(preview)」が外れた(GA の明記なし)が、GA 一覧表は Preview / Limited preview のまま → **SDK = GA / Learn = ラベルなし / GA 一覧表 = Preview の 3 者併記で、本書はプレビュー扱いを維持**。トレース評価は Learn でも preview(手順は `azure-ai-projects==2.7.0` 固定)。Rubric 評価器のスコアは 0〜1・閾値既定 0.5 で、openai の `score_model` グレーダー(1.0〜5.0)とは別物([09 §4.3](./09-operations.md#4-3-クラウド評価の実行))。**2026-11-22 更新:** 品質ルーブリックは continuous-scheduled-evaluation が「generally available」と明記(built-in-evaluators の見出しは preview、GA 一覧表は Evaluations = GA〈一部 preview〉→ 両論)。safety rubric(Americas / Europe のみ)・task-level rubric・**Human in the loop(トレース注釈 → 評価データセット → golden dataset)**・決定モデル judge(Learn は Microsoft-Decision-1 のみ対応で 1.1 は非対応 / ブログは 1.1 可の両論。Decision-1 は 2027-02-04 リタイア)・ベンチマーク評価・音声評価器は preview。multi-turn evaluation は Book of News = GA / Learn = preview、traces→dataset は Tech Community = GA / GA 一覧表 = Preview。azd の評価は `azd ai eval`(`azure.ai.evaluations` 拡張、preview)へ移った |
| M: 継続的評価 | 本番トラフィックのサンプリング評価 | **プレビュー**(Monitor ダッシュボード 2026-09-03 版で「Recurring evaluations (preview)」に包含。features/05 の 2026-09-07 訂正に同期。2026-11-22: 専用ページ化して Learn のラベルは外れたが GA 一覧表 Monitoring = Preview のため維持) | 既定 100 回/時(`max_hourly_runs`)。スケジュール型の dataset / trace 評価が加わり、**イベント起動の継続評価に対応しない外部エージェントはスケジュール型のトレース評価で代替** |
| M: AI Red Teaming Agent | PyRIT ベースの自動敵対スキャン | GA | ~~対応リージョンは公式間で不整合(5 対 2)~~ → **2026-11-22: 概念ページ・リージョン表とも East US 2 / France Central / North Central US / Sweden Central の 4 リージョンで統一**(**日本リージョンなし**)。workflow / 非 Foundry エージェント・Function ツールは非対応(**external agents もターゲットにできない**) |
| H: 自前 OTel 計装 | アプリ側で GenAI セマンティック規約に沿って計装 | — | Foundry 外の処理も 1 本のトレースに乗せられる |
| S: 自前評価ハーネス | pytest 等で回帰テスト化 | — | CI に組み込みやすい。評価器は自作 |

**本番の監視は M だけでは足りない。** Monitoring がプレビュー、Tracing の VNet 対応がプレビュー(GA 一覧表 11-17 版も Tracing VNet = Preview)である以上、閉域・本番案件では Azure Monitor + App Insights を主系として設計し、Foundry のダッシュボードは開発時の可視化と位置づけるのが安全。

---

## L14. UI・チャネル

| 選択肢 | 実体 | ステータス | 制約・地雷 |
|---|---|---|---|
| M: Teams / M365 Copilot へ公開 | 安定エンドポイントを Teams アプリ化 | GA(GA 一覧表の行名は 2026-11-17 版で「Publish agents to Microsoft Copilot and Teams」) | ~~Bot Service リソース必要~~ → **2026-11-22: 別途の Azure Bot Service リソースは不要**(Foundry が登録。REST は `performBotRegistration: true`)。組織公開は M365 管理者承認。**パブリックネットワーク無効プロジェクトはポータル不可・REST のみ**(チャネルからの受信は公衆インターネット経由)。voice agents の Channels では標準の Teams / M365 公開カードは出ない |
| M: ポータルの Playground | 検証用 UI | GA | 本番 UI ではない |
| H: 自作 Web / モバイル + Responses API | 独自 UI から直接 | GA | 認証・ストリーミング・引用表示を自作 |
| S: 既存システムに組込み | 業務画面の一機能として | — | 既存の認可・監査に統合しやすい |

---

## L15. 実行基盤(コンピュート)

| 選択肢 | 実体 | ステータス | 向く要件 | 制約・地雷 |
|---|---|---|---|---|
| M: Hosted agents | コンテナ(ACR)または zip を Foundry が実行 | GA | エージェント本体のホスティングを持ちたくない | **Python / C# のみ**(hosted-agents 2026-09-11 版。7・8 月号ブログは「ランタイム対応は言語で異なる」と注記)。31 リージョン(Japan East/West 含む)。**初期プレビュー基盤は 2026-08-20 でサポート終了済み**。同時セッションはサブスクリプション × リージョンで既定 1,000(Japan East 等 7 リージョンは 2,000。**2026-11-22 時点も不変** — サブネット IP 共有の GA はクォータ増ではない)。RAI ポリシーの `egressPolicy` による hosted agent の宛先制御(FQDN 許可/拒否・Audit モード)は ~~プレビュー(2026-09-24 公式ブログ)~~ → **2026-11 に GA**(安定版 api-version `2026-09-01`。Transform ルール・secret 参照ヘッダー・Azure Policy 統制は preview)。**長時間実行の回復(long-running resiliency)も GA**、memory snapshots(起動高速化)・session compute API は preview |
| S: 顧客の AKS へ hosted agent を配置(BYO-AKS、2026-11-22 追加) | Foundry の hosted agent を顧客所有の AKS で動かす | **coming soon**(devblogs。public preview は 12 月上旬目標)/ Book of News = preview の両論 | 閉域・データ所在で Foundry のマネージド基盤に載せられない案件 | 2026-11-22 時点では本番設計に使えない。egress controls・private CA trust はマネージド hosted 向けで、BYO-AKS 側は別途文書化と明記。「AKS AI Manager for Foundry」の位置づけは一次情報で未確認 |
| H: Container Apps | 自前コンテナ。サーバーレス GPU、dynamic sessions | GA | 言語自由、スケール制御、既存 CI/CD、非信頼コード実行 | ネットワーク・ID を自分で設計 |
| H: App Service / Functions | Web アプリ / イベント駆動 | GA | 既存資産が乗っている。Functions は Durable の標準ホスト | 長時間実行の制約(Durable で回避) |
| S: AKS | フル制御 | GA | 大規模、既存 K8s 基盤 | 運用負荷が最大。**エージェント用途で AKS を推奨する一次ドキュメントは確認できず** |

**Hosted agent のスケール単位は「レプリカ」ではなく「セッション」。** 課金はアクティブな全セッションの CPU + メモリ合計で、~~サイズは 0.5vCPU/1GiB・1vCPU/2GiB・2vCPU/4GiB の 3 種のみ~~ → **2026-11-22 時点のサンドボックスは 0.25 vCPU / 0.5 GiB 〜 16 vCPU / 32 GiB の 7 段**(`$HOME` の永続ストレージは最大 100 GiB)。**課金は使用率ではなく割り当て量に掛かり、idle timeout で停止するまでの待機時間も課金対象**(処理が終わったら `stop` で止める運用が推奨)。**オーバーサイジングは同時実行数の倍率でコストに効く。**セッションごとに VM 分離サンドボックス + 永続 `$HOME` / `/files` を持ち、**アイドルタイムアウト**(エージェントバージョンごとに **2〜240 分**で設定可、既定 15 分。2026-08-25 に下限が 5→2 分。~~2026-10-14: REST 仕様・azd beta.19 は上限 240 分、Learn は 60 分のままで両論~~ → **2026-11-22: Learn も 2〜240 分に改訂され両論解消**)で計算はデプロビジョンされるが状態は保持、30 日無活動で恒久削除(旧記載の「セッション最大寿命 30 日」の表現は現行ページから消え、「30 日無活動で削除」のみ)。フレームワークのチェックポイント等を置ける**永続キーバリューの状態ストア**(項目は既定 30 日の無書き込みで失効、無期限設定可)も追加された。~~ディスク「セッションあたり最大 20GiB(1vCPU 以上)・約 20% システム予約」は現行の hosted-agents / limits ページに記載が見当たらない~~ → 2026-11-22: `$HOME` の永続ストレージは CPU 段と変換後イメージサイズで決まり**最大 100 GiB**(旧「1 vCPU 以上で 20 GiB」から拡大)。**memory snapshots(preview)を有効にすると idle をまたいで `$HOME` が残らない**ので、状態を `$HOME` に置く設計とは両立しない([features/03](../features/03-agent-service.md))。

**Hosted agent は「デプロイ先」であって「フレームワーク」ではない。** 公式明記は MAF / LangGraph / Semantic Kernel / CrewAI / カスタムコードで、プロトコルライブラリはフレームワーク非依存のため任意のフレームワークが利用可。逆に MAF を Container Apps に置くこともできる。この 2 軸(何で書くか × どこで動かすか)は独立している。

**バージョンは不変で、トラフィック分割はできない(※2026-10-06: hosted agent の本番昇格ページ〈deploy-hosted-agent-production、preview〉は `FixedRatio` 2 本で 90/10 のカナリアを示し、manage-hosted-agent・configure-agent の「分割不可」と食い違う。未実測のため本カタログは分割不可を前提に置く — [09 §6.3](./09-operations.md#6-3-エージェントのバージョニングとリリース))。** hosted agent の各バージョンはコンテナイメージ・リソース割当・環境変数・プロトコル構成のスナップショットで、**1 エンドポイント = 1 バージョン**。カナリアリリースをやるなら、エージェントを別名で立てて呼び出し側で振り分ける設計が要る(**prompt agent も同じ**: バージョン選択ルールの型名は `FixedRatio` で `traffic_percentage` を持つが、configure-agent〈2026-09-11 版〉の Limitations に「**No traffic splitting — 同時にトラフィックを受けられるのは 1 バージョンのみ**」と明記。旧記載「prompt agent は FixedRatio で % 指定が可能」は誤り)。

---

## L16. IaC・CI/CD

| 選択肢 | 実体 | ステータス | 制約・地雷 |
|---|---|---|---|
| S: Bicep / ARM | `Microsoft.CognitiveServices/accounts` + `accounts/projects` + `accounts/deployments` | GA | ネットワーク注入は**作成時のみ**設定可 |
| S: Terraform | `azurerm_cognitive_account`(kind AIServices + `project_management_enabled`)+ `azurerm_cognitive_account_project` | GA 相当 | プレビュー機能は AzAPI 併用。AVM モジュール `Azure/avm-ptn-aiml-ai-foundry` あり |
| S: Terraform(hosted agent 定義、2026-10-06 追加) | AzAPI の `azapi_data_plane_resource`(type `Microsoft.Foundry/agents@v1`、親はプロジェクトのデータプレーン エンドポイント)で**名前付きエージェント**を管理。定義の変更で Foundry が新しい版を作る | 公式 how-to(2026-09-23 版、手順に `[TO VERIFY]` 残存) | azd 不要。イメージはダイジェスト固定、`rai_policy_name` はポリシーの ARM ID 全体、readiness ゲート必須、state に秘密を置かない、**書き手を 1 つに**(state lock は他の API クライアントを止めない)。詳細は [09 §6.4](./09-operations.md#6-4-iac) |
| H: azd + Terraform 基盤 | `azd ai agent init --infra=terraform`(`main.tf` / `provider.tf` / `variables.tf` / `outputs.tf` / `main.tfvars.json`)。基盤は Terraform、**版は `azd deploy` が作る** | ~~azd 拡張はプレビュー~~ → **2026-11-05 に GA**(下の行) | リモート state は自分で構成(`azurerm` バックエンド・環境別キー)。**ejection はサービスの `network:` 構成に非対応** |
| H: azd Foundry 拡張 | `azd ai agent init/run/invoke/doctor` 等(別ページでは init/show/monitor/invoke/files の列挙もあり、公式ドキュメント間で表記揺れ) | ~~プレビュー~~ → **GA(2026-11-05、`microsoft.foundry` 1.0 / `azure.ai.agents` 1.0.0〜1.2.0、azd 1.37.0 以上)**。evaluations / dataset 拡張は 1.0.0-beta.2、finetune / models は preview。破壊的変更: toolbox → toolboxes、`azd ai agent eval` 廃止 → `azd ai eval`、preview 機能は `AZD_ALPHA_ENABLE_AGENTS_*` で個別に opt-in。**`az cognitiveservices agent` は Deprecated(2027-02-28 後の最初の Azure CLI リリースで削除)なので CI/CD の標準 CLI は azd** | エージェント開発ライフサイクル向け(2026-08 末の推奨基準は azd 1.32.0+ / `azure.ai.agents` 拡張 1.0.0-beta.13+。拡張レジストリには routines / toolboxes / evaluations 等の個別 azd 拡張も並ぶ)。**az CLI に `az foundry` は存在しない**(2026-09-26 再確認。Foundry DevPack が入れる `microsoft.foundry` は azd 拡張) |
| M: ポータル手動 | — | — | 再現性なし。PoC 限定 |

**環境分離の単位を最初に決める。** プロジェクト単位 / リソース単位 / サブスクリプション単位のどれで dev-stg-prod を切るかで、クォータ・ネットワーク・RBAC の設計が全部変わる。**最初の「default」プロジェクトだけが OpenAI Batch / Fine-tuning / Stored completions に対応する**という非対称もあるため、「プロジェクトを増やせば済む」と考えると詰まる。

---

## 組合せの典型パターン(このカタログの使い方の例)

| パターン名 | L2 オーケストレーション | L5 RAG | L10 ネットワーク | L12 観測 | 想定 |
|---|---|---|---|---|---|
| **最小 PoC** | M(Prompt agent) | M(File Search) | M(パブリック) | M | 2 週間で動くものを見せる |
| **社内本番(標準)** | M または H | H(AI Search 自前索引) | M(Private Link) | M + H | 情シス主導の社内展開 |
| **基幹連携・承認付き** | H(MAF hosted) | H | H(BYO VNet) | H | 業務システムに書き込む |
| **規制業種・閉域** | H または S | S | H(BYO VNet)/ S | H + S | 金融・公共 |
| **既存システム組込み** | S(自アプリ) | S | S | S | Foundry はモデル供給元 |
| **マルチテナント SaaS** | H | S(テナント別索引) | M + APIM | H | 外部顧客に販売 |

各パターンの詳細な構成図・コンポーネント一覧・見積もり観点は [04〜08 のユースケース編](./README.md#ドキュメント一覧)を参照。
