# Microsoft Foundry アーキテクチャ設計ガイド

> **最終更新:** 2026-07-30(公式ドキュメントとの突合検証で訂正)/ 2026-09-26(四半期定期更新: AAC・WAF・CAF・Copilot Studio と期限・ステータスを一次情報で再突合)/ 2026-09-29(features 差分更新の波及: 04 / 05 / 08)/ 2026-09-30(Port 15 ライブ検証の波及: 09 §3.6 新設・05)/ 2026-10-06(2026-09-29〜10-06 の一次情報で差分更新+同日のラボ実測の還元: 09 §3.6 第 4 案〈保護テーブル〉・§6.3 公式の本番リリース手順・§6.4 Terraform、05 の toolbox 経由の委任、07 の Agent 365 egress、08 の voice agents 移行と Japan East の realtime 系 ほか)/ 2026-10-14(2026-10-06〜10-14 の features 差分更新の波及: gpt-4.1-nano のリタイア日の再改訂と On Your Data の期限当日、Voice Live の処理スコープ表記、hosted agent のユーザー分離ページの整理と idle timeout 上限の両論、capability settings 設定ページの 301、既定ストリーミングの末尾漏れ、評価機能のラベル外しと GA 一覧表の食い違い、ファインチューニングの選択肢 ほか)/ 2026-11-22(2026-10-14 以降+Ignite 2026〈11-17 開幕〉の features 差分更新の波及: **voice agents・hosted の egress controls / long-running resiliency / サブネット IP 共有・external agents・Insights・managed compute が GA 側へ**〈GA 一覧表に載ったのは managed compute と外部エージェントのトレースだけで残りは両論〉、Microsoft Copilot harness〈preview、12-01 課金開始〉、Azure AI Search → Foundry IQ (Azure AI Search) の改称と Search `2026-10-01` の GA 範囲・KB の fail-open、閉域〈`192.168.0.0/24`・構成確定のタイミング・private CA trust・Browser Automation の両論・電話チャネル不可〉、日本のデータ所在〈GPT-6.x の APAC Data Zone・managed compute の APAC なし・Policy 系 preview の日本リージョンなし・Modified Abuse Monitoring の縮小・Voice Live の Global 処理〉、Cost in Foundry / cost controls と Azure AI Gateway、Control Plane のカスタムエージェント廃止〈2027-05-07〉、期限表〈Claude 4.5・gpt-4o 2024-05-13 の延長、Content Safety preview 6 機能・Azure Language legacy 機能〉、アンチパターン A18・A19、図 12 枚の描き直し)/ **版:** 初版
> SI の技術選定・アーキテクチャ選定基準の構築を目的に、**Microsoft Foundry を使ったシステムアーキテクチャ**を、インフラを含めた広い視点で整理したもの。機能単位の GA / プレビュー調査は [features/](../features/README.md) を参照。

## ドキュメント一覧

| # | ドキュメント | 内容 | こんなときに読む |
|---|---|---|---|
| — | **本ページ(TOP)** | アーキテクチャ一覧・選定早見表・全案件共通の前提 | まずここ |
| 01 | [公式ベストプラクティス](./01-official-baselines.md) | AAC リファレンスアーキテクチャ(Basic / Baseline / ALZ 版)、WAF for AI、CAF、アクセラレータ・AVM の現況 | 提案の根拠になる公式資料を探す |
| 02 | [構成要素カタログ](./02-building-blocks.md) | **16 レイヤーごとの「Foundry 機能を使う vs 自前実装する」全選択肢** | 個別の技術要素を比較する |
| 03 | [選定ガイド](./03-decision-guide.md) | 5 つの決定ゲート、デシジョンツリー、要件キーワード逆引き、提案チェックリスト | 何から決めればいいか分からない |
| 04 | [UC-A 社内ナレッジ検索・RAG](./04-usecase-chat-rag.md) | File Search / 自前索引 / AI Search ツール / SharePoint / Foundry IQ の 5 パターン | 文書検索チャットを作る |
| 05 | [UC-B 業務自動化・マルチエージェント](./05-usecase-agent-automation.md) | 基幹連携、HITL 承認フロー、長時間プロセス、マルチエージェント、業務フロー主導 | エージェントに業務処理をさせる |
| 06 | [UC-C 顧客向け公開・マルチテナント](./06-usecase-customer-facing.md) | WAF チューニング、BOLA 対策、テナント分離、チャージバック、大規模キャパシティ | 外部顧客に提供する |
| 07 | [UC-D 規制業種・閉域・データ主権](./07-usecase-regulated-edge.md) | 3 つの egress モデル、閉域で使えない機能一覧、CMK、Purview の限界、Gov クラウド、エッジ | 金融・公共・医療の案件 |
| 08 | [UC-E 音声・文書処理・バッチ・M365](./08-usecase-specialized.md) | Voice Live とテレフォニー、DI と Content Understanding の使い分け、Batch、マルチモーダル生成、Teams 公開、ファインチューニング運用 | チャット以外の類型 |
| 09 | [運用アーキテクチャ](./09-operations.md) | PTU サイジング、BCDR、可観測性、評価、コスト、CI/CD | 本番運用を設計する |
| 10 | [移行とアンチパターン](./10-migration-antipatterns.md) | 確定済み廃止スケジュール、移行パターン、**踏みやすい 18 のアンチパターン** | 既存資産があるとき / レビュー前 |
| 11 | [エージェント構成の判断フレームワーク](./11-decision-frameworks.md) | CAF デシジョンツリー、単一 vs マルチ判断、AAC オーケストレーション 5 パターン、**Copilot Studio の上限ライン** | プラットフォームとエージェント構成を根拠付きで決める / 「試作で比較するしかないか」と聞かれた |

**人間用 HTML:** `html/index.html`(Markdown が正。HTML は `python3 docs/survey/tools/md2html.py` で自動生成するので直接編集しない)

---

## アーキテクチャ一覧

### 公式リファレンスアーキテクチャ(Microsoft が検証済み)

**Foundry チャット系の「リファレンスアーキテクチャ」はこの 3 本しかない。**それ以外の公式ページは「ガイド」または「ソリューションアイデア」で検証レベルが下がるため、顧客提案での引用時は区別する。

| 記号 | 名称 | 変種 | 実装コード | 詳細 |
|---|---|---|---|---|
| **公式-A** | Basic Microsoft Foundry Chat | パブリック・単一リージョン・ゾーン冗長なし。**記事自身が本番非推奨と明言** | `Azure-Samples/microsoft-foundry-basic` | [01 章](./01-official-baselines.md#a-basic-poc-専用-本番非推奨と記事自身が明言) |
| **公式-B** | **Baseline Microsoft Foundry Chat** | **ネットワーク分離・単一リージョン・ゾーン冗長。**WAF が「AI ワークロードの推奨アーキテクチャ」と名指し | `Azure-Samples/microsoft-foundry-baseline` | [01 章](./01-official-baselines.md#b-baseline-本番の出発点-waf-が-ai-ワークロードの推奨アーキテクチャ-と名指し) |
| **公式-C** | Baseline in an Azure Landing Zone | ネットワーク分離・hub-spoke | **記事から削除済み。**`Azure/AI-Landing-Zones`(Preview)または AVM を使う | [01 章](./01-official-baselines.md#c-baseline-in-azure-landing-zone-hub-spoke-版-ただしコードは記事から消えた) |

### 想定ユースケース別アーキテクチャ

| ID | パターン | オーケストレーション | RAG / ナレッジ | ネットワーク | 主な決め手 | 詳細 |
|---|---|---|---|---|---|---|
| **A1** | 部門内 FAQ チャット | Prompt agent | File Search | パブリック | 速度優先。権限制御なし | [04](./04-usecase-chat-rag.md#a1-部門内-faq-チャット-file-search・最小構成) |
| **A2** | 全社ナレッジ検索(本番) | Prompt / Hosted agent | **AI Search 自前索引** | Private Link | **ユーザーごとに見える文書が違う** | [04](./04-usecase-chat-rag.md#a2-全社ナレッジ検索-ai-search-自前索引・本番の標準形) |
| **A3** | 既存 AI Search 資産の活用 | Prompt agent | AI Search ツール直結 | 要件次第 | 索引設計を自分で持ち続けたい | [04](./04-usecase-chat-rag.md#a3-既存-ai-search-資産の活用-ai-search-ツール直結) |
| **A4** | M365 / SharePoint が主データ源 | Prompt agent | SharePoint ツール(OBO) | パブリック | 権限透過。**M365 Copilot ライセンス前提** | [04](./04-usecase-chat-rag.md#a4-m365-sharepoint-が主データソース) |
| **A5** | 複数ソース横断・高精度 | 任意(MCP 経由) | **Foundry IQ**(agentic retrieval) | 要件次第 | 複数エージェントでナレッジ共有 | [04](./04-usecase-chat-rag.md#a5-複数ソース横断・高精度-foundry-iq-agentic-retrieval) |
| **B1** | 単一エージェント + 基幹 API | Prompt agent + Toolbox | 補助的 | 社内網 | 参照系中心 | [05](./05-usecase-agent-automation.md#b1-単一エージェント-基幹-api-参照系中心) |
| **B2** | **承認付き業務自動化(HITL)** | **MAF hosted agent** | 調査工程で使用 | BYO VNet | 「担当者が承認してから実行」 | [05](./05-usecase-agent-automation.md#b2-承認付き業務自動化-hitl) |
| **B3** | 長時間・確実な再開 | **MAF + Durable Extension + DTS** | 任意 | 任意 | 数時間〜数日停止して再開 | [05](./05-usecase-agent-automation.md#b3-長時間・確実な再開が要る業務プロセス) |
| **B4** | マルチエージェント(専門分化) | MAF workflows / A2A | 領域別 | 任意 | 領域ごとに権限を分けたい | [05](./05-usecase-agent-automation.md#b4-マルチエージェント-専門分化) |
| **B5** | 業務フローエンジン主導 | Logic Apps / Copilot Studio | 任意 | 任意 | 業務部門がビジュアルで保守 | [05](./05-usecase-agent-automation.md#b5-業務フローエンジン主導-logic-apps-copilot-studio) |
| **C1** | 一般顧客向けチャット | 任意 | 任意 | 公開 + WAF + APIM | 不特定多数が使う | [06](./06-usecase-customer-facing.md#c1-一般顧客向けチャット-単一テナント) |
| **C2** | マルチテナント SaaS | Hosted agent(プロトコル 2.0.0) | テナント別索引 | 公開 + APIM | 複数顧客に販売する | [06](./06-usecase-customer-facing.md#c2-マルチテナント-saas) |
| **C3** | 大規模 / 複数部門への払い出し | 任意 | 任意 | APIM 必須 | 部門別按分・キャパシティ | [06](./06-usecase-customer-facing.md#c3-大規模トラフィック・複数部門への払い出し) |
| **D1** | 規制業種・閉域 | Hosted agent or 自前 | **AI Search 自前索引一択** | **BYO VNet** | 閉域・監査・データ主権 | [07](./07-usecase-regulated-edge.md) |
| **D2** | ソブリン(Azure Government) | **Prompt agent 対応**(Workflows はプレビュー、Hosted agents・音声 prompt agent 非対応) | File Search / AI Search | Gov クラウド | **hosted agent・A2A・Web search / Bing・SharePoint 等が非対応**。MCP サーバーは 2026-08-19 版で **Yes** に変化(2026-07-13 版では非対応)( https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/azure-government 2026-08-19 版、2026-09-26 確認) | [07](./07-usecase-regulated-edge.md#8-ソブリンクラウド-azure-government) |
| **D3** | エッジ・オンプレ | Foundry 非依存 | 自前 | オフライン | **端末上 = Foundry Local / オンプレ K8s = Azure Local 版(プレビュー・申請制)/ エアギャップ = 切断コンテナ** | [07](./07-usecase-regulated-edge.md#9-エッジ・オンプレ・ハイブリッド) |
| **E1** | 音声エージェント | Voice Live API / voice agents | 任意 | 要件次第(閉域では電話チャネル不可) | リアルタイム音声対話 | [08](./08-usecase-specialized.md#e1-音声エージェント-コンタクトセンター) |
| **E2** | 文書処理・IDP | 非同期パイプライン | DI / Content Understanding | 要件次第 | 帳票・契約書の構造化抽出 | [08](./08-usecase-specialized.md#e2-文書処理・idp-intelligent-document-processing) |
| **E3** | 大量バッチ処理 | ジョブ実行基盤 | 不要 | 任意 | **Batch で 50% 割引** | [08](./08-usecase-specialized.md#e3-大量バッチ処理) |
| **E4** | マルチモーダル生成 | 非同期ジョブ | 不要 | 公開必須(閉域不可) | 画像・動画生成 | [08](./08-usecase-specialized.md#e4-マルチモーダル生成-画像・動画) |
| **E5** | M365 / Teams 連携 | Prompt / Hosted agent | Work IQ 等 | 要件次第 | 業務ツール内で使わせる | [08](./08-usecase-specialized.md#e5-m365-teams-連携) |
| **E6** | ファインチューニング運用 | MLOps パイプライン | 併用推奨 | 要件次第 | **挙動・文体をモデル側で変える**(知識追加は RAG) | [08](./08-usecase-specialized.md#e6-ファインチューニング-モデルカスタマイズの運用) |

### 「Foundry 機能を使う vs 自前実装する」の全組合せ

16 レイヤーそれぞれについて **M(フルマネージド)/ H(ハイブリッド)/ S(自前実装)** の選択肢を [02. 構成要素カタログ](./02-building-blocks.md) に整理してある。要約は下表。

| # | レイヤー | M(フルマネージド) | H(ハイブリッド) | S(自前実装) | 迷ったら |
|---|---|---|---|---|---|
| L1 | モデル提供 | Foundry モデルデプロイ | Foundry + APIM ゲートウェイ | 他クラウド / セルフホスト | M |
| L2 | オーケストレーション | Prompt agent / Workflows(廃止予定) | Hosted agent(MAF・LangGraph) | 自アプリ + Responses API | H |
| L3 | 会話状態 | Agent Service の Conversations | standard setup の BYO Cosmos DB | 自前 DB | M→S |
| L4 | 長期記憶 | Foundry Memory(プレビュー) | Memory + 自前フィルタ | 自前サマライズ + ベクトル検索 | S(本番) |
| L5 | ナレッジ / RAG | File Search / Foundry IQ | AI Search ツール + 自前索引 | 自前パイプライン + 任意ベクトル DB | H |
| L6 | ツール実行 | ツールカタログ / MCP / OpenAPI | Toolbox + 自前 MCP サーバー | アプリ内 function calling | H |
| L7 | コード実行 | Code Interpreter | Custom Code Interpreter | ACA dynamic sessions 直 | M |
| L8 | ガードレール | Guardrails(既定 DefaultV2) | カスタムガードレール | Content Safety API を自前で呼ぶ | M+S 併用 |
| L9 | ID・認可 | Foundry RBAC + Entra | OBO / Agent identity | 自前認可基盤 | M |
| L10 | ネットワーク | パブリック + Private Link | BYO VNet 注入 | 自前 VNet に全部置く | 要件次第 |
| L11 | ゲートウェイ | Foundry のクォータのみ(+ cost controls、preview) | **APIM AI ゲートウェイ** / Azure AI Gateway(preview) | 自前プロキシ | H |
| L12 | 可観測性 | Foundry Tracing + Monitor | OTel 自前計装 → App Insights | 自前ログ基盤 | M+H |
| L13 | 評価 | Foundry Evaluations | evals API を CI から呼ぶ | 自前評価ハーネス | H |
| L14 | UI・チャネル | Teams / M365 公開 | 自作 Web + Responses API | 既存システムに組込み | 要件次第 |
| L15 | 実行基盤 | Hosted agents | Container Apps / App Service | AKS / オンプレ | H |
| L16 | IaC・CI/CD | ポータル手動 | Bicep / Terraform + azd | 既存 IaC 基盤に統合 | S |

---

## 選定早見表 — 3 分で当たりをつける

**決定は後戻りコストの大きい順に閉じていく**(詳細は [03. 選定ガイド](./03-decision-guide.md))。

```
 G1 データ・規制ゲート   「そのデータを、どこで、誰に処理させてよいか」
        │                → モデル・デプロイタイプ・外部ツール可否が決まる
        ▼
 G2 ネットワークゲート   「閉域か、パブリックか」
        │                → 使える Foundry 機能の一覧が決まる（後付け不可）
        ▼
 G3 制御ゲート           「明示的な状態遷移・承認・再開が要るか」
        │                → ポータル完結か、コードファーストかが決まる
        ▼
 G4 統合ゲート           「既存システムとの主従はどちらか」
        │                → プラットフォームとして使うか、部品として使うか
        ▼
 G5 ライフサイクルゲート 「いつまで、誰が保守するか」
                         → プレビュー機能の可否・IaC の作り込み度が決まる
```

| 要件の言葉 | 当たりをつけるパターン |
|---|---|
| 「社内文書を検索して答える」 | **A1** で PoC → 品質が出なければ **A2** |
| 「部署によって見える文書が違う」 | **A2**(Foundry IQ (Azure AI Search) + セキュリティフィルタ。2026-11-22: `2026-10-01` で SharePoint / ADLS Gen2 / Blob の ACL・RBAC 取り込みも GA になり「GA の唯一の方式」ではなくなった。knowledge base 経由ならユーザートークンを必ず渡す — 無いときの挙動は Learn のページで食い違う〈絞らずに返す / ACL 付きは返さない〉) |
| 「担当者の承認を経て実行」 | **B2**(MAF hosted agent)。承認待ちが数日なら **B3** |
| 「複数のエージェントが協調する」 | **B4**。**ポータルのビジュアル Workflows は 2026-12-01 廃止(残り 9 日)なので選ばない** |
| 「顧客向けに公開する」 | **C1**。WAF チューニングと BOLA 対策を工数に入れる |
| 「複数のお客様に SaaS として提供」 | **C2**。**APIM が事実上必須**(テナント別メータリング) |
| 「閉域で運用する」 | **D1**。**まず「閉域で使えない機能の一覧」から設計を始める** |
| 「日本国内でデータ処理を完結」 | `Standard`(リージョナル)または `ProvisionedManaged`。**APAC Data Zone は日本以外も含むので不可**。APAC 内で足りるなら GPT-6 世代は `gpt-6.1-sol` / `-terra`・`gpt-6.2-astra` / `-sol` の APAC Data Zone。managed compute は APAC Data Zone なし、Model router は Policy で要求時の行き先を絞れない(2026-11-22。[01 §7](./01-official-baselines.md#7-日本の案件で特に効く公式事実)) |
| 「音声で対話したい」 | **E1**(Voice Live / voice agents。voice agents は Learn・SDK・ブログ = GA / GA 一覧表 = Preview の両論)。~~SIP 非対応~~ → **SIP 直結は preview で日本リージョンなし**(2026-11-22。日本案件は引き続き ACS 経由)、**閉域プロジェクトでは電話チャネルと発信が不可**、ガードレール非適用に注意。国内処理が要件なら **Voice Live は音声認識・HD 音声・LLM が別々の処理スコープ**(Japan East でも HD 音声・MAI-Transcribe・realtime 系・gpt-6.1-sol / gpt-6-luna は Global)である点を先に確認 |
| 「請求書を読み取って」 | **E2**。定型帳票は DI プリビルト、非定型は Content Understanding |
| 「月間 N 万件を処理」 | **E3**(Batch で 50% 割引)+ [09 章](./09-operations.md)の PTU サイジング |
| 「既存システムに組み込む」 | オーケストレーションは自前(L2 の S)。**Foundry の運用機能は使えなくなる**(2026-11-22: external agents〈GA〉として登録すればトレース・Insights・トレース評価は Foundry で見られる) |
| 「マルチクラウド / ロックイン回避」 | Foundry はモデル供給元として使い、抽象レイヤーを自前で持つ |

---

## 全案件に共通する前提 — Foundry が「やってくれないこと」

**提案時に必ず顧客と合意しておく項目。**個別の詳細は各章に散っているが、頻度と影響の大きい順に並べる。

| # | Foundry がやってくれないこと | 誰が埋めるか |
|---|---|---|
| 1 | **リージョン間の自動フェイルオーバー・DR。**Agent Service は状態のレプリケーション / バックアップ / PITR のいずれも持たず、「復旧は再構築で行う」 | アプリ層でのルーティング + Cosmos DB 継続バックアップ + 再構築パイプライン([09](./09-operations.md#2-信頼性・bcdr)) |
| 2 | **会話に対するユーザー単位の認可。**conversation ID を渡せば誰の会話でも読める(BOLA) | アプリ側で所有権をリクエストごとに検証([06](./06-usecase-customer-facing.md#会話-id-の認可-bola-脆弱性)) |
| 3 | **エージェントの blue-green / canary。**組み込みサポートがない(※2026-10-06: hosted agent の本番昇格ページ〈preview〉は同一エンドポイントで 90/10 のカナリアを示すが、manage-hosted-agent・configure-agent は「分割不可」のまま — 公式間不整合・未実測)。**既存の会話が休止明けにどの版で再開するか**も、公式・Port 11(MAF ホスティング)= 作成時の版、probe 10(Agent Server SDK だけ)= 現行セレクタの版、と 2026-10-06 の実測で構成によって割れた → 受入試験で確かめる | APIM 等のルーティング層を自前で用意し、リリースは公式の「ピン留め → 候補検証 → 昇格」手順で([09](./09-operations.md#6-3-エージェントのバージョニングとリリース)) |
| 4 | **モデルデプロイのラウンドロビン・サーキットブレーカー** | APIM のバックエンドプール + circuit breaker |
| 5 | **部門別・テナント別のトークン計測と課金按分**(クォータはデプロイ単位、`project` タグはプレビューかつ Marketplace モデル非対応。2026-11-22: Cost in Foundry〈preview〉はプロジェクト・エージェント単位で見られるが、`agent.name` タグは 2026-11 以降の利用分から・データは 8〜24 時間遅れ・閲覧に Cost Management Reader が別途要る) | APIM の `llm-emit-token-metric` |
| 6 | **コストのハードリミット。**「Azure OpenAI には現状その機能がない」。**2026-11-22:** cost controls(preview)で予算超過を HTTP 429 で止められるようになったが、**GPT / o-series だけが対象で PTU・ツール料金・hosted のコンピュートは数えず、判定が遅れると fail-open** → 部分的な上限にとどまる([10 A19](./10-migration-antipatterns.md#a19-cost-controls-を-予算のハードリミット-として約束する-2026-11-22-追加)) | 予算アラート + 自作の自動化(cost controls は補助) |
| 7 | **プロジェクト内のエージェント単位のアクセス制御。**`Foundry User` を持てばプロジェクト内の全エージェントと対話できる。2026-11-22: エージェントスコープのロール割り当ても**プロジェクトのファイルは分離しない**(prompt agent を呼べる主体は任意の file ID を参照できる)、`agents/write` を持つ主体はエージェントを介さず推論できる | アプリの認証認可層、または hosted agent の Entra Agent ID。ファイルを分けたいならプロジェクトを分ける |
| 8 | **`max_output_tokens` / `truncation` によるトークン制御。**「self-hosted orchestration でしか実現できない」 | 自前オーケストレーション |
| 9 | **閉域での Traces / Memory / Work IQ / Logic Apps / Browser Automation / Computer Use / Image Generation**(Memory は what-is-memory ページ、Work IQ は work-iq ページに VNet 非対応と明記。**File Search は公式ツール表 2026-08-14 版で「PE 経由で Supported」に変化したが、Blob Storage のファイル連携は非対応** → [03 章 G2](./03-decision-guide.md#g2-ネットワークゲート)。Browser Automation は 2026-10-14 にツールページ本文が GA を表明し、**2026-11-22 時点で閉域は configure-private-link = Supported / toolbox-network-isolation = Not supported の両論**。同日、**voice agents の電話チャネル〈Teams Phone / Twilio / SIP〉と発信は閉域プロジェクト非対応**と明記) | 自前実装または機能除外([07](./07-usecase-regulated-edge.md#3-閉域で使えない機能の一覧-設計の出発点)) |
| 10 | **Claude モデルへのコンテンツフィルター**(組込みフィルターが適用されない) | APIM の `llm-content-safety` かアプリ層で Content Safety を呼ぶ |
| 11 | **音声モデルへのガードレール**(Whisper 等には適用されない) | テキスト化後の経路で Content Safety |
| 12 | **capabilityHost の更新。**作成後は変更不可で、変更は **capabilityHost 自体の削除・再作成**で行う(プロジェクト削除は不要。ただし削除で既存エージェントの会話・ファイルへのアクセスは失われる)。委任サブネット等アウトバウンド網の変更は Foundry リソースの再デプロイが必要( https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/capability-hosts )。**2026-09-26 追記:** 後継として **capability settings(プレビュー、API `2026-07-15-preview`。段階展開中で現時点は UK South / Canada Central のみ)** が登場し capability hosts ページは「参照用に保持」扱いになった。**capability settings は既存プロジェクトに追加・変更できず、変更は「プロジェクトの削除・再作成」**(生成される接続も使用中は変更・削除不可)( https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-capability-settings 2026-09-22 版)。**2026-10-14 要確認: この設定ページは 301 で agents/environment-setup(capability settings の記述なし)へ転送されるようになり、取り下げか移設中かは判断できない**(他ページは旧 URL を参照したまま capability settings を説明)。当面は capability host 前提で設計する([09 §6.2](./09-operations.md#6-2-移植できるもの-できないもの))。**2026-11-22:** 301 は不変。加えて **hosted agent のネットワーク構成は最初の hosted agent 作成時に確定**し、以後の変更は新しいプロジェクト(networking-options) | IaC を「作り直し前提」で設計 |
| 13 | **トレースに入る会話の中身の閲覧制限。**App Insights を接続すると hosted agent のプラットフォーム側スパンに会話全文が入り、コンテナ側の設定では止まらない。専用テーブル `AppGenAIContent` への振り分けは公式では 2026-09-30 から既定だが、**Protected 化とロール限定は自分で設定**し、`gen_ai.*` 以外の属性名や MAF のメッセージイベントに書かれた本文は振り分け対象外。2026-10-06 の実測(フラグ未登録)では全発生源で従来テーブルとの二重書きだった。**公式の確認手順は従来テーブルの残存を確認しない**(2026-10-14 確認) | 「接続しない / App Insights を分ける / 保護テーブル」から選び、従来テーブルに本文が残っていないことを KQL で確認(閲覧ロール Privileged Monitoring Data Reader は接続先 App Insights リソースへの付与で足りる)([09 §3.6](./09-operations.md#3-6-トレースに会話の中身を残すか-hosted-agent-の選定基準)) |
| 14 | **ユーザートークンのない knowledge base 呼び出しでの権限トリミング(2026-11-22 追加)。**Foundry IQ の KB 接続にユーザートークンが無いときの挙動は、Learn のページで食い違う**(foundry-iq-connect = 絞らずに返す〈fail-open〉、retrieve・query-time ACL のページ = ACL 付きの文書は返さない。2026-11-22 確認) | ユーザートークンの転送を必須構成にし、権限の違う 2 人で受入試験([10 A18](./10-migration-antipatterns.md#a18-foundry-iq-の-knowledge-base-をユーザートークンなしで呼び-権限トリミング済み-と判断する-2026-11-22-追加)・[04](./04-usecase-chat-rag.md)) |

**加えて、コンテンツフィルターは「フェイルオープン」する。**フィルタリングシステムが利用不能な場合、リクエストはフィルタリングなしで HTTP 200 で完了する。`content_filter_results` 内のエラーオブジェクトでしか判別できないため、**規制業種では `finish_reason` と `content_filter_results` の検証を必須実装にする。****さらに既定(バッファあり)のストリーミングでも、応答の最後の区切り(試験では末尾約 15〜30 語)はガードレール適用前に届きうる**(content-streaming 2026-10-13 版。禁止語が `finish_reason: "stop"` のまま届いた例)。流出が許されない画面は非ストリーミングにするか、最終区切りをアプリ側で再検査する([06 C1](./06-usecase-customer-facing.md#プロンプトインジェクションと安全性))。**分類器そのものも動く(2026-11-22 追記):** Content Safety の分類器の 2026-10 更新が Spain Central から段階展開中で、同じ入力のブロック判定が変わりうる(閾値を詰めた案件は代表データで再試験)。また **2026-11-01 以降に提供開始したモデルは Modified Abuse Monitoring(悪用監視のデータ保存の変更承認)の対象外**になる(告知日から。gpt-6.2 系が該当)— 「プロンプトを Microsoft 側に保存させない」前提の規制案件はモデル更改のたびに確認する([07](./07-usecase-regulated-edge.md))。

---

## 重要な期限(アーキテクチャ判断に直結するもの)

| 期限 | 対象 | 設計への効き方 |
|---|---|---|
| ~~2026-07-31~~ **期限到来** | コンテナプロトコル 1.0.0 | **非サポート・ブロック中**(2026-09-26 確認。出典は現在「Protocol 1.0.0 is no longer supported, and the platform blocks requests」とだけ書き、ブロック開始日の記載は消えた)。2.0.0 へ更新( https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/isolate-sessions-per-user ) |
| ~~2026-08-20~~ **期限到来** | Hosted agents 初期プレビュー基盤 | **サポート終了済み**(未移行なら新基盤へ再デプロイ)。**自動移行されない。**パッケージ・API・エンドポイント・ID・ライフサイクル管理がまとめて変わる([10 章 2.0](./10-migration-antipatterns.md#2-0-最優先-hosted-agent-初期プレビュー基盤-新基盤-期限-2026-08-20)) |
| ~~2026-08-26~~ **廃止済** | Assistants API / `azure-ai-inference` SDK | 廃止済み(features 側で出典の過去形表記を確認)。Threads / Runs 前提のアプリは全面改修。**状態データは移行されない** |
| ~~2026-09-30~~ **移行日到来** | トレースの会話本文 → 専用テーブル `AppGenAIContent` | 公式では以降の取り込みは既定で専用テーブルだけ(2026-10-06 の japaneast 実測では従来テーブルとの**二重書き**)。閲覧制限は Protected 化+Privileged Monitoring Data Reader を自分で設定。**一時 opt-out は 2027-09-30 で廃止**([09 §3.6](./09-operations.md#3-6-トレースに会話の中身を残すか-hosted-agent-の選定基準)) |
| ~~2026-10-14~~ **廃止済** | **Azure OpenAI On Your Data** | 「モデルが直接データを読む」構成は終了(2026-11-22 確認: 出典が「retired on October 14, 2026, and is no longer supported」と過去形に)。**RAG の既存提案書は要更新**。移行先は Foundry Agent Service + Foundry IQ( https://learn.microsoft.com/en-us/azure/foundry-classic/openai/concepts/use-your-data ) |
| ~~2026-11-19~~ **到来** | o1 / o1-pro / o3 / o3-pro / o3-deep-research / o3-mini / o4-mini | 後継 gpt-5.6-sol / terra は **Batch・Regional Standard で提供されない**(リタイア表 11-18 版の脚注 4 に代替候補)。国内処理(Regional)や Batch で使っていた構成は後継を選び直す([10](./10-migration-antipatterns.md#1-確定済み廃止スケジュールと設計への影響)) |
| **2026-11-30** / 2027-02-22 | Claude 4.5 系(**sonnet 11-30**。haiku / opus は 11-18 版で **2027-02-22** に延長) | リタイア表は往復改訂するので直前に再確認。Claude を使う構成はガードレールが効かない点(全案件共通 #10)と併せて後継モデルで再評価 |
| **2026-12-01(残り 9 日)** | ビジュアル Workflows | **ポータルでマルチエージェントを組む構成が消える。**長期案件で提案不可 |
| **2026-12-01(課金開始)** | Microsoft Copilot harness(prompt agent のマネージドハーネス、preview) | サンドボックスの CPU / メモリ時間に従量課金が始まる(devblogs)。PoC で無料前提にしない |
| **2027-01-14** | gpt-4o(2024-05-13)(~~2026-12-09~~ から延長) | Global / Data Zone Standard は gpt-5.1 に自動アップグレード、**PTU と Batch は手動移行** |
| **2027-02-04** / **2027-02-28 後の CLI** | Microsoft-Decision-1(評価の決定モデル judge で Learn 上唯一の対応モデル)/ `az cognitiveservices agent` | judge を使う評価の組み替え / CI/CD を azd・SDK・REST へ([09](./09-operations.md)) |
| **2027-03-31** | Agents (classic)(v1) | classic プロジェクト上のエージェント資産 |
| **2027-04-14** | gpt-4.1 / gpt-4.1-mini / **gpt-4.1-nano** / gpt-4o(2024-08-06・2024-11-20)/ gpt-4o-mini | **gpt-4.1-nano はリタイア表 2026-09-21 版で 2026-10-14 と表示 → 2026-10-14 取得で再び 2027-04-14**(3 度目の往復)。リタイア表は include で版ごとに動くので、期限の直前に必ず再確認する([10 章](./10-migration-antipatterns.md#1-確定済み廃止スケジュールと設計への影響)) |
| **2027-04-20** | prompt flow | **新規開発に非推奨。**Microsoft Agent Framework への移行を明示要求 |
| **2027-04-30** | Content Safety の preview 6 機能(Groundedness detection〈ガードレールの Groundedness を含む〉・Custom categories rapid・Analyze Multimodal・接続 / 非接続コンテナー・Embedded SDK) | 接地性チェックとオフラインのコンテナー構成が影響を受ける([10](./10-migration-antipatterns.md#1-確定済み廃止スケジュールと設計への影響)) |
| **2027-05-07** | Foundry Control Plane のカスタムエージェント | external agents(2026-11-18 GA)へ同じ `gen_ai.agent.id` で登録し直す。元の登録と APIM API は消さない([09](./09-operations.md)) |
| **2028-09-25** | Azure AI Vision Image Analysis | 「2026-09-25 までに移行計画を」と記載(**計画策定の目安日は到来済み**) |
| 2027-10 〜 2028-04 | ファインチューン済みモデルの deployment | 学習停止の約 6 か月後に推論も停止(gpt-4.1-nano は 11-18 版で 2028-04-13 に延長)。**FT は作り直しが前提** |
| **2029-03-31** | Azure Language の legacy 7 機能(CLU / CQA / 要約 / 感情 / キーフレーズ / カスタムテキスト分類 / オーケストレーション) | **CLU / CQA を使う FAQ ボット系の提案に期限を明記**(本書の見落としだった期限)。Custom Vision 2028-09-25・Read OCR コンテナー 2028-09-28 も追加([10](./10-migration-antipatterns.md#1-確定済み廃止スケジュールと設計への影響)) |
| 日付未公表(30 日前以上に通知) | Modified Abuse Monitoring(2026-11-01 以降に提供開始したモデル) | 既存の承認があっても対象外になる。規制案件はモデル更改のたびに確認 |
| 日付未公表 | Agent Applications | 廃止告知が予告済み |

全体表は [10 章](./10-migration-antipatterns.md#1-確定済み廃止スケジュールと設計への影響)と [features/README](../features/README.md) を参照。

---

## 本ドキュメント群について

- **正(マスター)は Markdown**(生成 AI 用)。人間用 HTML は `docs/survey/tools/md2html.py` で `html/` 配下に自動生成する。**HTML を直接編集しない。**
- 公式ドキュメントに書かれている事実と、本ドキュメントの判断・推測を区別して書いている。**公式に書かれていない判断には「本ドキュメントの判断」と明記**している。
- **公式ドキュメント間で記述が食い違っている箇所**(Data Zone の APAC 記載漏れ、hosted agents の GA / preview 表記、Reservation の交換可否など)は、その旨を併記している。
- **リンク切れ・削除済みリソース**(ALZ 版 baseline の実装リポジトリなど)も、探して見つからないことに時間を使わないよう明記している。
- **本ガイドは公式ドキュメント由来の構成判断に限定する。**現場で詰まった点(公開記事・labs の実測)と、要件シナリオ別の判断(「閉域必須」等)は [casebook/](../casebook/README.md) に分離した。各章の「→ casebook P-xx」はそこへの導線。
- **アーキテクチャ図(Azure 公式アイコン)は `images/*.png`(全 18 枚)。**生成スクリプトと再生成手順は [diagrams/](./diagrams/README.md)(maf-ports の描画ヘルパーを共有)。**2026-09-29 に全 18 枚を v2 スタイルへ描き直し** — 日本語ラベル・処理番号(①②…と下端の「処理の流れ」)・GA / Preview バッジ・タグ付き注記帯・2 倍解像度。公式間でステータスが割れる機能は灰色のバッジ(例: 「GA / 表は Preview」)で示す(2026-11-22 から)。スライド用の切り出し版は `images/slide/*.png`。公式-B と A〜E の主要パターンを整備済み。構成が既存図と実質同じもの(公式-A/C、A3/A4、C1/C3、D2)は作図せず理由を diagrams/README に記載。ASCII 図は生成 AI 用にそのまま残している。

### 更新運用

**推奨頻度:** 四半期に 1 回。Ignite(11 月)・Build(5 月)直後は必ず更新。[features/](../features/README.md) の月次更新とは別サイクルでよい(アーキテクチャの骨格は機能ステータスより変化が遅いため)。

**更新時のウォッチリスト:**

1. [Azure Architecture Center の AI アーキテクチャ索引](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/ai-get-started) — リファレンスアーキテクチャの追加・改称
2. [Baseline Microsoft Foundry Chat](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/baseline-microsoft-foundry-chat) — 本ガイドの土台。`ms.date` の変化を追う
3. [WAF for AI workloads](https://learn.microsoft.com/en-us/azure/well-architected/ai/get-started) — 特に `ai/architecture-pattern` と `ai/application-design`
4. [CAF AI Platform Sharing](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai/platform/ai-platform-sharing-isolation-colocation) — リソース粒度の一次資料
5. [Agent Service の limits / quotas / regions](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/limits-quotas-regions) — 上限値とリージョン対応
6. [Private Link 構成](https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-private-link) — **閉域で使えない機能の一覧が更新される**
7. [Feature readiness at GA](https://learn.microsoft.com/en-us/azure/foundry/concepts/general-availability) — GA / プレビューの一次情報
8. [`Azure/AI-Landing-Zones`](https://github.com/Azure/AI-Landing-Zones) — Preview から GA への昇格を追う
9. [`microsoft-foundry/foundry-samples`](https://github.com/microsoft-foundry/foundry-samples) — Bicep テンプレートの追加
10. [`MicrosoftDocs/architecture-center` のコミット履歴](https://github.com/MicrosoftDocs/architecture-center/commits/main/docs/ai-ml/architecture) — **AAC は `ms.date` を据え置いたまま本文を加筆する**(2026-07〜09 の Baseline 加筆がその例)。ms.date だけで「変化なし」と判定しない
11. [Restrict access to sensitive content in traces](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/traces-sensitive-content) — **トレース本文の専用テーブル化の実効**(2026-10-06 実測は二重書き)と preview 解除。opt-out 廃止 2027-09-30(2026-10-06 追加)
12. [Manage hosted agents「Release a version without changing production」](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/manage-hosted-agent#release-a-version-without-changing-production) と [Promote hosted agents to production](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent-production) — **トラフィック分割(カナリア)の可否の食い違い**と、既存セッションの版の扱い(公式「作成時の版に束縛」/ 実測は構成で割れる)。両ページに残る `[TO VERIFY]` の解消(2026-10-06 追加)
13. [Configure Agent 365 data collection](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/configure-agent-365-data-collection) — hosted agent からの Agent 365 送出の既定と中身の有無(agent-365-integration との記述の食い違い)(2026-10-06 追加)
14. [Hosted agents の概念ページ](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) — idle timeout の上限(Learn = 60 分 / REST 仕様・azd = 240 分)の決着(2026-10-14 追加)
15. capability settings の行方 — 設定ページ(`how-to/configure-capability-settings`)が 301 で消えた。[capability-hosts](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/capability-hosts) と [virtual-networks](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/virtual-networks) の記述が変わるか(2026-10-14 追加)
16. [Speech regions の Voice Live タブ](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions?tabs=voice-live) — 機能ごとの処理スコープ(Global / Data zone / Regional)。`azure-speech` と非 HD 音声の処理スコープの記載が増えるか(2026-10-14 追加)
17. GA 一覧表と Ignite 2026 のブログの両論 — **voice agents(「Agents — Voice Live」行)・network egress controls・Insights・品質ルーブリック・Monitoring・AI Gateway** の GA 一覧表への反映。「到来」後に延びたリタイア日(MAI-Image-2.5 系・model-router 旧版)の再変更(2026-11-22 追加)
18. [Networking options](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/networking-options) / [virtual-networks](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/virtual-networks) — hosted agent のエンドポイントが閉域でも公開到達可能か(2026-11-17 版で記述が消えた)、CGNAT の公式間矛盾、Browser Automation の閉域両論(configure-private-link と toolbox-network-isolation)(2026-11-22 追加)
19. Azure Policy 系 preview の展開リージョン([agent-deployment-policy](https://learn.microsoft.com/en-us/azure/foundry/how-to/agent-deployment-policy)・egress の Policy 統制)— 日本リージョンへの展開。顧客 AKS への hosted agent 配置(BYO-AKS)の public preview(12 月上旬目標)(2026-11-22 追加)
20. [Microsoft Copilot harness](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/use-tools-skills-copilot-harness) — 2026-12-01 の課金開始後の料金ページ掲載・Japan West 対応。Copilot Studio 側の同名ハーネスとの関係と、[Foundry IQ 接続](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agents-experience/foundry-iq-connect)の GA 範囲(2026-11-22 追加)

**差分の取り方(2026-10-14 追加):** 公開ミラー `MicrosoftDocs/azure-ai-docs` は 2026-10-14 時点で 404(Learn の `original_content_git_url` は非公開リポジトリを指す)になり、「GitHub のコミット差分で include の変更を拾う」手順は使えなくなった(AAC の `MicrosoftDocs/architecture-center` は上の 10 のとおり引き続き使える)。代わりに `python3 docs/survey/tools/learn_crawl.py --since <前回日付> --out <作業ディレクトリ> --snapshot docs/survey/tools/learn-snapshot.tsv` で Learn の TOC 全ページの `updated_at`・`ms.date`・本文ハッシュを取り、**updated_at が同じなのに本文が変わったページ**(include だけの変更。virtual-networks・リタイア表がその例)を拾う。スナップショットがない期間は、ja-jp 版の `updated_at` が先に進むことが変更候補の手掛かりになる(翻訳だけの再公開でも進む)。手順の詳細は [features/README の更新運用](../features/README.md)

**HTML の再生成:** リポジトリルートで `python3 docs/survey/tools/md2html.py`(引数なしで features と architecture の両方をビルド)。

### 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-07-29 | 初版作成(全 10 章) |
| 2026-07-29 | 追補調査を反映。**08 章**に Voice Live のクォータ・テレフォニー統合(ACS)・日本リージョン制約、マルチモーダル生成の非同期ジョブと Sora 2 の RAI 制限、**E6 ファインチューニング運用**を追加。**07 章 9 節**をエッジ 3 形態(Foundry Local / Azure Local 版 / 切断コンテナ)に再構成し、**初版の誤り「オンプレ文書処理は DI コンテナが唯一の選択肢」を訂正**(Vision Read OCR も GA・切断対応)。**06 章**に公式のマルチテナンシー 4 方式比較と Responses API の分離課題を追加。**Azure OpenAI On Your Data の非推奨**を 04 / 10 章と期限表に反映 |
| 2026-07-30 | features 側の検証で判明した事実を反映: **08 章の Voice Live を「GA の明文なし」→「GA 一覧表で Preview と明記(ただし Voice Live 自身のページと表記不一致)」に更新** |
| 2026-08-01 | **Azure アイコンのアーキテクチャ図を導入。**代表 4 パターン(公式-B Baseline / A2 / B2 / D1)を `diagrams/*.py` → `images/*.png` で生成し 01・04・05・07 章に埋め込み。md2html.py に画像対応(`![...]` → `<img>`、html/ からの相対パス書き換え)を追加 |
| 2026-08-01 | **アーキテクチャ図を全 18 枚に拡充。**A1(A3/A4 統合)/ A5 / B1 / B3 / B4 / B5 / C2 / D3 / E1〜E6 の 14 枚を追加し全ユースケース章に埋め込み。構成が同型のパターン(公式-A/C、C1/C3、D2)は作図せず理由を diagrams/README に記載 |
| 2026-08-01 | **11 章(エージェント構成の判断フレームワーク)を新設。**「要件→エージェント構成の指標は事前に構築できるか、複数試作して比較するしかないか」への回答として、CAF ai-agents セクション(2025-12 新設: デシジョンツリー・単一 vs マルチの判断表)、AAC オーケストレーションパターン(複雑度の階段・5 パターン・アンチパターン)、Copilot Studio の公式上限ライン(30〜40 アクションで精度劣化・connected agents の多段連鎖不可・Foundry 接続はプレビュー)、業界指標(Anthropic 3 条件・LangChain 4 型)を整理。03 章・tech-selection-guide との対照表つき |
| 2026-09-04 | **casebook セット新設に伴う更新。**03 章 G2 表を公式 2026-08-14 版(File Search「PE 経由」表記・Tracing VNet Preview)で改訂、05 章 B2 に hosted agent の詰まりどころ、07 章 §3 のツール表・機能表を更新、10 章にアンチパターン A12〜A14(注入なし hosted agent / App Insights 接続なし / プロンプト二重化)を追加 |
| 2026-07-30 | **全 11 ファイルのファクトチェック(公式ドキュメント突合)と訂正を適用。**確定日の反映: On Your Data 廃止 **2026-10-14**、コンテナプロトコル 1.0.0 ブロック開始 **2026-07-31**。古い記述の更新: **Foundry Local GA(2026-04-09 公式ブログ)**、Toolbox GA、FLUX.2 GA、tsuzumi-7b Legacy(2026-08-31 リタイア)、Groundedness detection 6→4 リージョン、SharePoint「ライセンス必須」→ pay-as-you-go 併記、全遮断 PE のポータル対応。誤りの訂正: capabilityHost 変更は「プロジェクト再作成」でなく「capability host の削除・再作成」、MACAE の org(microsoft)、FT デプロイ上限 10/リソース、Cosmos DB コンテナー 3〜5 個(追加関係)、agent identity とマネージド ID の混同、ガードレール既定閾値「画像 Low」→ テキスト・画像とも Medium、File Search「固定」→ 既定値。ミスリードの限定: 「国内処理必須 → Data Zone(APAC)」を Regional Standard(Japan East)に分離、A2A「ポータル未対応」を incoming 有効化に限定、Front Door パターンのベースライン記事への帰属を Front Door 一般ドキュメントに修正、Cost Analysis「約5時間遅延」を時間非特定に。公式間不整合の両論併記: AI Red Teaming リージョン(2 vs 5)、Traces VNet(非対応 vs プレビュー)、azd コマンド列挙 |
| 2026-09-26 | **四半期定期更新(README・01・02・03・11)。**AAC 3 本は ms.date 2026-06-17 のままだが本文加筆を GitHub 履歴で確認し反映(Baseline: private MCP サブネット `snet-mcpServers`・hosted agent の egress / per-user 分離の適用条件・モデル×ツール選定の注意・ID 分離〈Assignment restrictions プレビュー〉、ALZ 版: spoke 要求 `/22`→`/21`)。**ステータス更新:** Routines GA(2026-09-24)、A2A ツール v1.0 GA、Copilot Studio の A2A 接続 GA(2026-04、11 章の「いずれもプレビュー」は誤り)、Toolbox 内 Tool search GA、Model router のリージョン拡大(GS 32 / DZ 23)、継続的評価=プレビュー、Azure Government で MCP が Yes。**期限:** プロトコル 1.0.0・初期プレビュー基盤・Assistants API を到来済みに。**訂正:** Japan West の Class A 非対応(解消)、Regional Standard の「単一リージョン処理」(正: geography 内)、RBAC「SDK 非対応と明記」(正: 記載なし)、Azure Functions ツール GA(正: 公式間不整合)、prompt agent の `FixedRatio` による % 分割(正: No traffic splitting)。**追記:** capability settings(プレビュー)による BYO 構成の変更=プロジェクト再作成、hosted agent ガードレールのフェイルオープン、2026-09-01 の Data Zone / Regional 価格プレミアム、Dynamic AI agents at scale の URL 特定、Copilot Studio の GitHub Copilot harness と Foundry 接続の前提(Activity エンドポイント) |
| 2026-09-29 | **features 差分更新(2026-09-29)の波及。**04: 「Foundry IQ の MCP エンドポイントはプレビュー API 必須」を訂正(KB の MCP は GA `2026-04-01` でも extractive で利用可。Agent Service 側の RemoteTool 接続はプレビュー)/ 05: hosted agent のユーザー委任アクセス(アプリ管理の OBO+`x-client-*` 転送、公式ページ 2026-09-28 新設)を認可パターンに追記 / 08: gpt-realtime-2.1 系が Voice Live 上でも GA(2026-09-29)、`mai-transcribe-2` 明示指定・`phrase_list` 対応。図(a5 の MCP ラベル・d1 の capability host 注記・b1 の Azure Functions (GA) ラベル)は別担当に波及を連絡 |
| 2026-09-30 | **Port 15(hosted agent × 委任アクセス)のライブ検証の波及。**09: §3.6「トレースに会話の中身を残すか(hosted agent の選定基準)」を新設 — App Insights の接続がプラットフォーム側トレース(会話の中身入り)の有効化と接続文字列のコンテナ注入を同時に起こし、コンテナ側の設定では中身を止められないこと、3 案(集約 / 2 つに分離 / 接続しない)と選び方。§3.1 のマスクの記述に限界を注記、§6.3 に会話の続きが agent 単位になる制約(版更新は未確認)、要点 7 とチェックリストを追加。05: Port 15 の実装例の記述をライブ済みに更新し 09 へ接続 |
| 2026-10-06 | **差分更新(2026-09-29〜10-06 の一次情報)。**09: §3.6 に第 4 案「同じ App Insights のまま中身だけ保護テーブル(`AppGenAIContent`)に隔離」を追加し、**旧記載「同じテーブルに入るので Protected では分けられない」を訂正**。ただし公式の「移行日 2026-09-30 以降は既定で専用テーブル」に対し **2026-10-06 の japaneast 実測(フラグ未登録)は従来テーブルとの二重書き** → 両論併記し、採用条件(フラグ登録または移行完了+Protected+ロール限定+`gen_ai.*` 以外に本文を書く計装の停止の 4 点、KQL で従来テーブルを確認)を明記。Agent 365 への送出(`a365LoggingEnabled` 既定 true)を案 3 の条件に追加。§4 に評価の権限(モデルを呼ぶ評価はアカウントスコープ、トレース評価はプロジェクト MI に Reader / Privileged Monitoring Data Reader)・合成評価器・`azure-ai-projects` 2.8.0 の「GA」と GA 一覧表の食い違い・データ生成の Japan West 対応。§6.3 に公式の本番リリース 6 段階と「既存セッションは作成時の版に束縛」を追加して probe 10 の実測と両論併記、緊急退避の第一手を `force=true` 削除から版固定セッションに変更、hosted agent のカナリア(90/10)の公式間不整合。§6.4 に Terraform の 2 経路。§1 に GPT-6.1 Sol と normalized token のキャッシュ消費(旧「キャッシュは一律 100% 控除」を限定)。05: ユーザー委任は toolbox 経由が公式推奨に → アプリ管理 OBO との使い分け表、Routines の既定配信 5 回。07: Agent 365 宛て FQDN・サービスタグの広さ・任意エンドポイント遮断の影響表、voice agents のサブエージェントの VNet 非対応。08: **Japan East でも realtime 系が Global standard で使える(旧「Japan East ではネイティブ speech-to-speech 不可」を訂正)**、Voice Live の WebRTC のプレビュー表記解除、voice agents 移行ガイドの比較、classic 連携の Deprecated、MAI-Transcribe-2-Streaming・MAI-Voice-2.1・料金ティア名変更。04: remote SharePoint の支払い方法、Foundry IQ in Copilot Studio GA、`auto` の公表値。02 / 01 / 10 / 11 に波及(10 にアンチパターン A16・A17)。図 `e1-voice` を再生成 |
| 2026-10-06 | **ラボの最新化+ライブ検証(LABS-FINDINGS A〜K)の還元。**09: §3.6 を probe 11(発生源 4 種すべて二重書き・`gen_ai.*` 以外の属性名と MAF のメッセージイベントは振り分け対象外・プラットフォーム側スパンはオプトインなしで本文を記録)で更新し、第 4 案の成立条件を **4 点**に。§3.1 に既定サンプラー(5 spans/秒)によるトレースの歯抜けと `az monitor app-insights query` の既定 1 時間、トレースを監査証跡にしない理由。§3.5・§4.3 に継続評価の条件(`sampling_rate` は百分率、エージェントエンドポイント経由の応答は failed)とルーブリックの `pass_threshold` 必須。§6.3 を「休止明けの版は構成で割れた(公式・Port 11 = 作成時の版 / probe 10 = 現行セレクタの版)」の表に書き直し、受入試験・エージェント名の分離・`stop_session` の扱い・`agent_reference.version` は答えた版ではない・同一 zip の再デプロイは既存の版を返す、を追加。04: AI Search Free で agentic retrieval が動いた実測、KB MCP 応答の API 版依存。08: Port 12 の Japan East `gpt-realtime-2.1-mini`(実効 `-global-standard`)・表外設定の受理・ネイティブ音声が決定論フローから外れる、CU usage の新費目。05 / 11: agent-as-tool は必須の相談を保証しない・HandoffBuilder の成果物欠落、Routines のライブ挙動。親が先に反映した分(05 の使い分け表の検証済み化、06 の normalized token 注記、09 §3.6 の再測定表、§6.3 の Port 11 実装例)とは重複させていない |
| 2026-10-10 | **11 章 §2 に Copilot Studio の非機能面の上限を追加。**上限ライン表にネットワーク制御(条件付きアクセス・IP ファイアウォールは可、受信経路をインターネットから外す手段は見当たらない)・モデルの版管理(既定モデルの自動更新、retired 後の猶予は最長 1 か月)・推論の処理場所(公式間の食い違い → proposal 03 §2)・課金単位(イベント課金 → proposal 02 Step 6)の 4 行。非機能面で Foundry に倒れる条件 3 つを判断として追記 |
| 2026-10-14 | **features 差分更新(2026-10-06〜10-14)の波及**。10: **`gpt-4.1-nano` のリタイアが 2027-04-14 に戻った**(3 度目の往復)ので期限表の行を移動し、On Your Data を「本日が期限当日」に、直近の期限(10-15 の転写モデル・TTS アバターの Jeff / Lisa 4 スタイル 2026-12)・Fireworks の Pay-per-token 終了・Grok の最低 6 か月提供を追記、A11 に 2026-10-14 の食い違い例、A17 に「公式の確認手順は従来テーブルの残存を見ない」を補強。08: **Voice Live の regions 表が処理スコープ表記に刷新**され日本リージョン表を書き換え(Japan East でも HD voices・mai-transcribe-2 は Global、旧表の HD voices ✗ は解消、Agent support 列は削除)、テレフォニーの公式推奨が voice agents(preview)へ、voice agents の toolbox・画像入力・料金・観測評価、DI / CU の選び方、Flex processing(preview、7 モデル)、Teams / M365 公開の受信経路と課金、**E6 の旧記載「gpt-4.1-nano は 2026-10-14 リタイア」を訂正**し FT 概要ページ・プレビュー OSS・managed compute への LoRA 配置・interactive training を追加。06: 既定ストリーミングの末尾漏れ(ガードレール・チェックリスト)、hosted agent のユーザー分離ページの整理(新機能ではない)・Foundry User の全セッション管理・MAF 既定ストアの分割と旧データ非互換。09: §3.6 にテレメトリ送出の既定変更(`azure-ai-agentserver-responses` 2.3.0 = background)・LangChain tracer の内容記録の既定・閲覧ロールの付与先、§4 に Learn のラベル外しと GA 一覧表の 3 者併記・トレース評価の 2.7.0 固定・Rubric 評価器と `score_model` の区別・評価レベル混在の食い違い、§1.5 に Bing ツールでキャッシュが効かない件、§5.2 に Flex、§6.2 に capability settings 設定ページの 301 とプロビジョニング ID の経路差、§6.4 に azd 拡張の破壊的変更。07: virtual-networks の Firewall 許可 FQDN の具体化、Browser Automation の GA 表明と閉域非対応の併存、Teams 公開の受信経路、invocations の `textField` 必須化、Model router の既定プールの Fireworks、Claude Haiku 5.5 / Grok 4.7 のデプロイ範囲、チェックリスト #20・#21。04: Serverless / S3 HD のインデクサーの閉域取り込み不可と日次クォータ、Search の自動生成 DNS ラベル、AI Search ツールと private endpoint、Foundry IQ の 401 / 502、MAF の context provider。02 / 05 / 01 / 03 / 11 / README に波及(capability settings の要確認注記、idle timeout の両論、Routines の `api-version=v1` 必須と JS 2.8.0 の creator ID、Model router の Fireworks、Memory の TTL、Teams 公開と「インターネットを経由しない」要件)。ウォッチリストに 14〜16 と公開ミラー消失後の差分の取り方を追加。**図 3 枚を描き直し**: e1-voice の注意枠(Japan East は realtime 系・HD 音声・転写とも Global 処理、アバター・ストリーミング転写なし、国内処理は gpt-4o〈Regional〉)、b2-hitl-automation の注記帯(idle 上限は Learn 60 分 / REST 仕様・azd 240 分)、d1-closed-network の副題(capability settings の設定ページ 301・要確認)。スライド用の切り出し画像は b2 / d1 とも不変(注記帯・副題は切り出し範囲外) |
| 2026-11-22 | **features 差分更新(2026-10-14 以降+Ignite 2026〈11-17 開幕〉)の波及。**全章に「最終更新」を追記。**ステータス:** voice agents(Learn・SDK・ブログ = GA / GA 一覧表 = Preview)、hosted の egress controls(Transform 等を除き GA)・long-running resiliency・サブネット IP 共有・external agents・Insights・managed compute を GA 側へ(GA 一覧表に載ったのは managed compute と外部エージェントのトレースだけで、残りは features と同じ書き方で両論併記)、Microsoft Copilot harness(preview、2026-12-01 課金開始)・memory snapshots・private CA trust・Policy 系・Cost in Foundry・Azure AI Gateway を新プレビューとして追加。**01:** Baseline の地雷にサブネット IP 共有・`192.168.0.0/24`・構成確定のタイミング・private CA trust と TLS 検査・Web search の経路差、CAF の中央ゲートウェイに Azure AI Gateway、RBAC の `agents/write`・ファイル分離・コスト閲覧、日本の案件の表に GPT-6.x の APAC Data Zone・managed compute・Policy 系の日本リージョンなし・評価リージョン・Modified Abuse Monitoring・音声の処理スコープ。**02:** L7 を除く 15 レイヤーを更新(Model router の再編・Copilot harness・Foundry IQ (Azure AI Search) への改称と `2026-10-01` の GA 範囲・KB の fail-open・Content Safety preview 6 機能の 2027-04-30 廃止・Bot Service 不要・7 段のサンドボックス・idle 待機の課金・azd 拡張 GA ほか)。**03:** G1〜G3・逆引き表・チェックリスト、「自前オーケストレーションは可観測性から外れる」を external agents で緩和。**04〜09:** 別担当の並行更新(04: Search `2026-10-01` の GA 範囲と ACL の GA・Serverless の両論・private ingestion / 05: Copilot harness・hosted の GA 群・MAF の要件変化・ツールガバナンス / 06: cost controls・Azure AI Gateway・サブネットの計画値・フィルター Off の訂正 / 07: egress 節の GA 化・閉域の新制約・データ所在の表・Modified Abuse Monitoring・Policy・エッジの期限 / 08: voice の 3 者割れと SIP の訂正・CU 2,000 ページと 24 時間保持・Language legacy 機能・Bot Service 不要・Managed / Programmed Training / 09: external agents への移行・Insights・評価の両論・cost controls・prompt cache 書込課金・azd GA と CLI の Deprecated)。**10:** 期限表をリタイア表 11-18 版で更新し「到来後に延びた日付」の扱いを追記、A18(KB をユーザートークンなしで呼ぶ)・A19(cost controls をハードリミットとして約束する)を追加。**11:** Copilot Studio のハーネス名が Microsoft Copilot harness 表記になった件と Foundry の同名ハーネスの区別、Foundry IQ 接続の範囲(Microsoft Copilot harness のエージェントのみ・1 接続)、Foundry エージェント接続は public preview のまま。**README:** 全案件共通に #14(KB の fail-open)、#5〜#7・#9・#12 を更新、期限表・早見表・ウォッチリスト 17〜20。**図 12 枚を描き直し:** a2(ACL 2 方式を GA に)・a5(クエリ計画・回答合成を GA、ソースの GA 範囲)・b1 / b2 / b3 / c2 / e2(注記帯のみ。b3 は beta バッジ → stable)・d1(egress controls を GA、委任サブネットの副題・`192.168.0.0/24`・閉域非対応の一覧)・d3(Read OCR の廃止日・期限の注記)・e1(題・副題の SIP、voice-based agent を「GA / 表は Preview」)・e4(Sora 2 のリタイアと fal)・e5(Bot Service ノードを「ボット登録〈Foundry が実施〉」に、処理の流れ ③ の文言を変更) |
| 2026-11-22 | **02・03・04・07・10・README:** Foundry IQ のナレッジベースにユーザートークンを渡さないときの挙動を訂正。「絞らずに返すと公式が明記」としていたが、Learn の foundry-iq-connect(ms.date 11-09)= 絞らずに返す、agentic-retrieval-how-to-retrieve(11-09)・query-time ACL(11-06)= ACL 付きの文書は返さない、と食い違うので出典つきの両論にした。あわせて閉域取り込みの tier(S2 / S3 / L1 / L2。Basic・S1 は不可)、medium effort の Japan West 非対応、KB 接続の例の API 版(`2026-11-01-preview`)を追記 |
