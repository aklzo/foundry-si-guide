# 03. 日本規制対応メモ(ISMAP / FISC / 個情法 / 医療)

[← 提案実務ガイド TOP](./README.md)

> **最終更新:** 2026-07-31 / 2026-09-26(Data Zone APAC・閉域ツール表・トレース VNet の現行表記、個情法 令和 8 年改正・AI 法関連の最新版、ISMAP の learn 掲載ページ、Work IQ の境界外処理を反映) / 2026-09-29(Fireworks on Foundry のデータ処理場所〈Microsoft 施設外・US のみ〉と claude-sonnet-5-5 を §2 に反映)/ 2026-10-06(§0 に観測データの層、§3 の保護テーブルの成立条件を 4 点に〈ラボ還元〉、§2 に Agent 365 のデータ所在、§3 にトレースの本文の保護〈保護テーブル。2026-10-06 実測の二重書きと両論〉、§7 の回答の型を追記。Fireworks の FAQ は再確認して内容の変更なし) / 2026-10-10(§2 に Copilot Studio を入口にする構成のデータ所在を追加。生成 AI の推論場所は Power Platform と Copilot Studio の公式記載が食い違うため両論を併記し、§7 の回答の型に反映) / 2026-10-14(§2 に Voice Live の処理スコープ〈機能ごとに別・リソースのリージョン外で処理されうる〉、新モデルの日本リージョン〈Grok 4.7 は Japan East / West の Global Standard、Claude Haiku 5.5・Microsoft-Decision-1 は APAC なし〉、Model router の既定プールに Fireworks、Prompt Optimizer の日本リージョン、ファインチューニングの新方式の所在、§6 に AI 生成コンテンツの来歴〈透明性規制、義務の履行は顧客責任〉)
> **免責: 本メモは SI の技術側が論点を整理するためのもの。法解釈・規制適合の最終判断は必ず顧客の法務・コンプライアンス部門と行うこと。**「検証済み」と記した項目は 2026-07 時点の learn.microsoft.com 現行ページで確認済みの事実([features](../features/README.md) / [architecture](../architecture/README.md) の調査に基づく)。

## 0. 前提: データフローの4層整理

規制の議論はまず「どのデータがどこへ行くか」を4層に分けると噛み合う:

| 層 | 内容 | 制御手段 |
| --- | --- | --- |
| ① 推論データ(プロンプト/応答) | モデルが処理する。**保存されない(stateless)・学習に使われない**と公式明記(検証済み) | デプロイタイプで処理地域を制御 |
| ② 保存データ(会話履歴・ファイル・ベクトル) | Agent Service 等が保存 | basic(MS 管理)/ standard(BYO リソース)、CMK、リージョン |
| ③ 悪用監視データ | 検出時にサンプルがレビュー対象(同一ジオ保存)。**自動レビューが既定、必要時に人間レビュー** | Modified 申請でデータ保存・人間レビューをオプトアウト可(検証済み。`ContentLogging=false` で確認可能) |
| ④ ツールの外部送信 | Web search / Bing 系はコンプライアンス境界外へ送信・**DPA 対象外**(検証済み)。**Work IQ(プレビュー)も「Foundry のサービス境界を越え、Azure コンプライアンス境界外で処理されうる」と明記**(work-iq ページ 2026-09 更新) | 機能を使わない(サブスクリプション単位無効化可)or 顧客合意 |
| ⑤ 観測データ(トレース・管理面)(2026-10-06 追加) | App Insights に送るトレース(hosted agent は接続するとプラットフォーム側で会話本文も記録)と、Microsoft Agent 365 へのエージェント活動データ(Agent 365 が有効なテナントでは既定で送信。保存場所は **Entra テナントのジオ**で、Foundry リソースのリージョンとは別の所在モデル) | App Insights の所在・本文の記録の有無・閲覧ロール(本文の保護テーブルは §3)/ Agent 365 はリソース単位で `a365LoggingEnabled=false`(Azure Policy で強制可) |

## 1. ISMAP(政府情報システム)

- **learn.microsoft.com 上に Foundry と ISMAP を結びつける記述は見当たらない**(2026-07 調査時点。検証済み)。learn の ISMAP オファリングページ( https://learn.microsoft.com/en-us/compliance/regulatory/offering-ismap 、2026-06-02 更新)は対象を「Azure, Microsoft Dynamics 365, and other Microsoft online services」/ Japan East・Japan West ほか 40 リージョンと**包括的に**記すのみで、個別サービス名の列挙はない(2026-09-26 確認)。
- 政府案件では **ISMAP クラウドサービスリスト( https://www.ismap.go.jp/ )で対象サービスの登録状況を案件ごとに確認する**のが先決。Azure 全体が登録されていても、**個別サービス(Foundry / Agent Service / 各ツール)が対象範囲に含まれるかは別問題**。
- 確認手順: ① ISMAP ポータルで Microsoft の登録サービス一覧を取得 → ② 構成で使う Azure サービスを列挙([01 ヒアリング](./01-hearing-sheet.md)の構成候補から)→ ③ 差分(未登録サービス)を特定し、代替構成か所管との調整かを判断。
- 政府(府省庁)案件では、デジタル庁の **DS-920「行政の進化と革新のための生成AIの調達・利活用に係るガイドライン」**(Normative、最終改定 2026-06-12)が生成 AI 調達・利活用のルールになる。調達仕様・リスク評価の要求事項を先に確認する( https://www.digital.go.jp/resources/standard_guidelines )。
- **プレビュー機能は避ける**: Azure Government 向けページには「Preview 機能は GA と同等のコンプライアンス保証(FedRAMP 等)を持たない場合がある」と明記されている(検証済み)。日本の認証でも同じ前提で扱うのが安全。

## 2. データ所在(全規制共通の土台)

| 論点 | 事実(検証済み) | 提案での扱い |
| --- | --- | --- |
| 推論の国内処理 | **geography 型(Standard / Regional Provisioned)を Japan East / Japan West に置いた場合のみ日本国内処理**(「customer-specified Azure geography 内で処理、運用目的で geography 内のリージョン間処理あり」)。Data Zone (APAC) は「APAC 域内のいずれかの国」で処理 — 現行の対象リージョンは豪・日・韓・星・印で、**Microsoft が予告なくリージョンを追加しうる**と明記(deployment-types 2026-08-06 版 / region-availability 2026-09-03 版) | 「国内必須」なら geography 型。geography 型は新モデルの提供が最後で日付保証なし → モデル提供状況・クォータは Japan East / West で個別確認。Data Zone / Regional は Global 比の価格プレミアムあり(2026-09-01 改定、[02 コスト手順](./02-cost-estimation.md))。※2026-10-14: **Voice Live は例外扱い**と公式に明記された — Speech の regions ページは「Azure Speech は作成リージョンで保存・処理するが、Voice Live は音声認識・HD 音声合成・LLM 推論がそれぞれ別の処理スコープを持ち、リソースのリージョン外で処理されうる」と書き、Japan East で Regional(国内)になる LLM は gpt-4o と phi4-mm-realtime(preview)だけ、HD voices と mai-transcribe-2 は Global。音声案件は LLM・書き起こし・音声合成の処理スコープを別々に確認して説明する(`azure-speech` と非 HD 音声は表に記載がないので Microsoft に確認。[Speech regions(Voice Live タブ)](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions?tabs=voice-live)・[casebook P-M08](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト)) |
| 保存データ | 保存は指定ジオグラフィ内。standard setup なら BYO リソース(Cosmos/Storage/AI Search)を Japan East に置ける | 保存層の所在は構成で完全制御可能と説明できる |
| ファインチューニング | Global Training は**データ所在保証なし**。リージョナル学習を選ぶ。※2026-10-14: プレビューの OSS 4 モデル(Muse-Glimmer-30B / Qwen3.6-35B-A3B / Qwen3.8-27B / gpt-oss-120b)の学習は Global / Developer のみ、新しい interactive training(preview・申請制)は日本リージョン非対応、Data zone training は US のみ([fine-tuning overview](https://learn.microsoft.com/en-us/azure/foundry/fine-tuning/overview)) | FT 案件はトレーニングタイプを明示。データ所在の要件がある案件は Azure OpenAI 系の Standard training(リソースのリージョン内で学習。対応リージョンはモデルごとに確認)と比べて判断する |
| 安全性評価・Red Teaming | 対応リージョンは国外のみ(日本非対応)。**評価のためにプロンプト・応答が国外に渡る**。※2026-10-14: ポータルの Prompt Optimizer(instructions の書き直し)の対応 15 リージョンのうち日本は **Japan West のみ**(Japan East のリソースではボタン自体が出ない — [prompt-optimizer](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/prompt-optimizer)) | 使うなら明示合意、使わないなら構成から除外 |
| Task adherence(ガードレール) | データが指定 Geo 外(US/EU)で処理される可能性を公式明記 | 同上 |
| Claude 等パートナーモデル | Hosted on Azure 版は US 系(Data Zone US)。**日本国内処理の選択肢はない**(2026-07 時点。models-from-partners 2026-09-21 版でも Claude の Data Zone は US のみ・APAC なし。2026-09-28 追加の `claude-sonnet-5-5` も同じ)。**Fireworks 経由の `FW-*` モデルは推論が Fireworks の GPU 上で行われ Microsoft 施設外に出る**(Fireworks は Microsoft のサブプロセッサで DPA の範囲内。提供は現時点で US のみ・SOC 1 Type 2 非準拠 — [Fireworks privacy & compliance FAQ](https://learn.microsoft.com/en-us/azure/foundry/how-to/fireworks/privacy-compliance-faq) 2026-09-28 新設。2026-10-06 再確認: 語句の修正のみで内容の変更なし) | 国内要件がある案件では Azure OpenAI 系を選ぶ。`FW-*` は候補から外す。※2026-10-14: 新モデルの日本リージョン — `claude-haiku-5-5`(GA)も APAC リージョンなし(Global Standard は US 8 リージョン + Sweden Central、Data Zone は US)、`Microsoft-Decision-1` は US / EU のみ。一方 **`grok-4.7`(GA)は Global Standard に Japan East / West を含む**(Data Zone は US のみ)が、Global Standard なので国内処理ではない。Model router の既定プールに Fireworks の 3 モデルが入った(事前デプロイ不要)ので、router を使う構成で `FW-*` を除外するには model subset で絞る([casebook P-M06](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト)) |
| Agent 365 へのエージェント活動データ(2026-10-06 追加) | Foundry のデータ(エージェント・デプロイ・ログ)は**リソースのリージョン**に保存されるが、Agent 365 に流れた活動データ(インベントリ・分析・ガバナンス)は **Entra テナントの保存場所(ジオ)**に保存される。リージョン型からテナント型の所在モデルに移る、と公式が明記。Agent 365 が有効なテナントでは Foundry リソースの収集設定が既定で有効で、公式ホスティングライブラリを使う hosted agent はトレースを自動送信する([agent-365-integration](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-365-integration) 2026-08-26 / [configure-agent-365-data-collection](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/configure-agent-365-data-collection) 2026-09-29) | 国内要件がある案件はテナントの保存場所(ジオ)を確認し、要件に合わなければ対象の Foundry リソースだけ収集を止める(リソース単位で選べる)。閉域では送信先 `agent365.svc.cloud.microsoft` の扱いも合意する([casebook P-H27](../casebook/02-pitfalls-index.md#a-hosted-agent)) |
| Copilot Studio を入口にする構成(2026-10-10 追加) | **保存**は環境のジオ(日本 = Japan East / West。[data-location](https://learn.microsoft.com/en-us/microsoft-copilot-studio/data-location) 2026-04-29 版)。M365 系機能の活動データ(会話ログを含む)はユーザーの Exchange メールボックスの地域。**生成 AI の推論場所は公式間で食い違う(2026-10-10 確認)**: Power Platform の [Move data across regions](https://learn.microsoft.com/en-us/power-platform/admin/geographical-availability-copilot)(2026-10-01 版)の表は、日本でホストされた環境の Azure OpenAI のホスト先を **United States**、Bing を United States とし、日本以外でも「Move data across regions」に同意しないと一部の生成 AI 機能は動かないと書く。一方、Copilot Studio の [モデル選択ページ](https://learn.microsoft.com/en-us/microsoft-copilot-studio/authoring-select-agent-model)(2026-09-18 版)の standard harness の表では、日本の列で**既定モデル GPT-5.5 Chat に cross-geo 表記がない**(GPT-4.1 / GPT-5 Chat / Claude 各モデルは「GA (cross-geo)」= 地域外で処理されうる)。experimental / preview モデルは地域外で処理・保存されうると明記 | 「国内処理」が要件の案件では、どちらが現行の扱いかを Microsoft に書面で確認し、試験環境で「Move data across regions」をオフにして既定モデル・生成回答・Bing の可否を実測してから回答する。確認までは「保存は国内、推論は国外の可能性あり」と説明する([casebook P-X24](../casebook/02-pitfalls-index.md#k-copilot-studio-m365-apim-業務連携)) |

## 3. 個人情報保護法

- **プロンプトに個人データを含める構成**は、Azure OpenAI の位置づけ(処理の委託)を前提に利用目的・委託先管理の整理を顧客法務と行う。技術側が用意する材料:
  - data-privacy ページの「NOT リスト」(他の顧客に提供されない / OpenAI に提供されない / モデル改善に使われない / 許可なく基盤モデルの学習に使われない。検証済み)
  - **悪用監視のオプトアウト状況**: 既定では検出サンプルの保存+レビューがある。Modified 申請が通れば保存・人間レビューなし(`ContentLogging` 属性で客観的に示せる。検証済み)
- **要配慮個人情報**(病歴等)を扱う場合は、悪用監視オプトアウト+閉域+保存層 BYO を揃えるのが説明しやすい構成。
- **運用ログ(トレース)に入る個人データ**(2026-10-06 追加): hosted agent は App Insights を接続するとプラットフォーム側で会話本文(ツール結果を含む)を記録する([casebook P-O12](../casebook/02-pitfalls-index.md#g-観測と評価))。安全管理措置(アクセス制御)の説明材料として、本文の属性を専用テーブル `AppGenAIContent` に分け、テーブルを Protected にして **Privileged Monitoring Data Reader** の保持者だけが読める公式の仕組み(preview)がある(PIM で時限付与も可)。ただし **① 早期有効化フラグの登録か移行の完了 ② Protected 化 ③ ロール付与 ④ `gen_ai.*` 以外に本文を書く計装(MAF のメッセージイベント・自前ログ)を止める の 4 点がそろって初めて成立**し(④は 2026-10-06 のラボ還元で追加、[casebook P-O18](../casebook/02-pitfalls-index.md#g-観測と評価))、公式は移行日 2026-09-30 以降の新規取り込みを既定で専用テーブルのみとしているが、**2026-10-06 の japaneast 実測(フラグ未登録)では本文が従来テーブルにも残る二重書き**で、通常の Log Analytics Reader で読めた。顧客に「閲覧者を限定している」と説明する前に、従来テーブルに本文が残っていないことを KQL で確かめる([casebook P-O13](../casebook/02-pitfalls-index.md#g-観測と評価))。有効化した後の利用者への告知・保持期間・アクセス制御は顧客の責任(公式)なので、利用目的・保存期間の整理に含める。
- ガードレールの **PII 検出/リダクションはプレビュー**(検証済み)。「PII を自動でマスクします」を確約に使わない。個人情報保護委員会の生成 AI に関する注意喚起(利用目的・本人通知まわり)も法務確認の際に参照。
- **令和 8 年改正個人情報保護法(2026-07-10 成立・07-17 公布)**: 統計作成等を行う第三者への提供の同意不要化(AI 開発等の統計処理目的)、顔特徴データ等の利用停止請求、課徴金制度の新設、子どもの個人データの規律強化など。**施行は一部を除き公布から 2 年以内の政令で定める日**で、政令・規則・ガイドラインは個人情報保護委員会が整備中(2026-09 時点)。長期案件では施行日と改正ガイドラインを法務確認の論点に入れる( https://www.ppc.go.jp/personalinfo/legal/r8kaiseihogohou/ )。
- **AI 固有の国内ルール(法的拘束力の強さが異なる)**: AI 法(人工知能関連技術の研究開発及び活用の推進に関する法律。2025-06-04 公布・09-01 全面施行)/ 同法に基づく「適正性確保に関する指針」(AI 戦略本部 2025-12-19 決定)/ **AI 事業者ガイドライン 第 1.2 版**(総務省・経産省 2026-03-31。AI エージェントの定義を本編に追加)。SI は「AI 提供者」側の整理を求められうるため、顧客の AI ガバナンス規程とあわせて確認する( https://www8.cao.go.jp/cstp/ai/ai_act/ai_act.html ・ https://www.meti.go.jp/shingikai/mono_info_service/ai_shakai_jisso/20260331_report.html )。

## 4. 金融(FISC 安全対策基準)

- Microsoft は FISC 対応のリファレンス(対応状況の整理資料)を **Service Trust Portal( https://servicetrust.microsoft.com/ )**で提供している。案件では最新版を取得し、構成要素(Foundry / AI Search / APIM 等)ごとの対応状況を顧客の FISC チェックリストへマップする。
- 技術構成の定石は [architecture 07(規制業種)](../architecture/07-usecase-regulated-edge.md) の閉域構成: BYO VNet 注入(**作成後変更不可**)+ Private Endpoint + standard setup(BYO 3点)+ CMK(一部リージョンのみ)。
- 金融で刺さりやすい注意点(検証済み):
  - **Risks & safety モニタリング(悪用状況ダッシュボード)は classic ポータル専用**で新ポータル未移植(ステータスもプレビュー)
  - 閉域では Logic Apps / Browser Automation / Computer Use / Image Generation / Fabric data agent 等が使えない(configure-private-link 2026-08-14 版のツール表)。File Search は同表で「Supported(private endpoint 経由)」に変わったが、Blob 上のファイルを使う連携は閉域では非対応(Blob の文書をそのまま使うなら AI Search ツールへ寄せる)。Bing / Web search / SharePoint は閉域でも動くが公開エンドポイント経由
  - トレースの VNet 対応: configure-private-link 2026-08-14 版の制限表から Traces 行は消えたが、GA 一覧表は「Tracing VNet = Preview」かつ「Traces は network isolation に完全には対応していない」と記載 — 安全側は「監査ログは閉域外に出る前提で設計」
  - Customer Lockbox は**非サポート**(セキュリティベースラインに明記)

## 5. 医療(3省2ガイドライン)

- 論点は「医療情報システムの安全管理」への対応: データ所在(§2)+ アクセス制御 + 監査証跡。
- 技術側の対応部品: Entra ID 必須認証(Agents は API キー不可)/ RBAC(Foundry 5ロール)/ トレース・App Insights の監査ログ設計(保持年限は Log Analytics 側で)/ Purview 監査(従量課金有効化が前提。検証済み)。
- 診療情報を含む RAG は、悪用監視オプトアウト+閉域+国内処理(geography 型 = Standard / Regional Provisioned を Japan East / West に配置)の3点セットを基本形として提示。

## 6. 契約・知財まわり(業種横断)

| 論点 | 事実(検証済み) | 顧客説明のポイント |
| --- | --- | --- |
| DPA 対象外機能 | Web search / Grounding with Bing は DPA 対象外・地理境界外送信・別課金 | 使う場合は契約上の扱いを明示合意。不要なら無効化(サブスクリプション単位可) |
| AI 生成コンテンツの来歴・透明性(2026-10-14 追加) | provenance-disclosure(2026-10-09 版)は、EU AI Act の AI 生成コンテンツの透明性に関する行動規範・カリフォルニア AI 透明性法・C2PA の文脈を挙げ、「Microsoft の AI システムは画像・音声・動画・テキストに来歴情報を含めていく」方針と、**透明性義務の評価と履行は顧客の責任**(Microsoft は対応モデルで来歴技術を提供し、検出手段の情報を公開する)を明記。対象はモデル表に載るもの(画像: gpt-image 系〈gpt-image-2.5-flare / -sunburst を追加〉・MAI-Image 系、音声: MAI-Voice 1 / 2、テキスト: Claude の一部)で、TTS アバターの生成動画には C2PA の content credentials が自動付与される。来歴は真偽・著作者を証明せず、編集・再保存・変換で失われうる | EU・カリフォルニア向けに生成物を出す案件では、来歴の付与・表示の義務を顧客法務と確認し、モデル選定で来歴対応の有無を確かめる(表にないモデル〈MAI-Voice-2.1 等〉の対象可否は要確認)。「来歴が付く = 義務を満たす」とは説明しない([provenance-disclosure](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/content-safety/provenance-disclosure)) |
| 著作権(CCC) | Customer Copyright Commitment には条件がある: Protected material 検出等の構成が前提になり得る。**非同期フィルターのストリーミング遅延分は CCC 対象外の可能性**を公式明記 | 「規約通りのガードレール構成を維持すること」を運用要件に含める |
| Claude の安全機構 | **Foundry の組み込みコンテンツフィルターは Claude に適用されない**(Anthropic 側の安全機構+自前で Content Safety を構成) | マルチモデル構成ではモデルごとに責任分界が異なることを図で説明 |
| プレビュー機能 | SLA なし・仕様/課金変更あり・コンプライアンス保証が GA と異なる場合あり | **「プレビュー利用同意書」を取る**か、GA のみ構成+プレビュー UI 無効化(`AZML_DISABLE_PREVIEW_FEATURE`) |
| モデルリタイア | GA 後 12〜18 か月でリタイア(強制移行。温度感 18 か月・安全側 12 か月) | 保守契約に「モデル移行対応」と再見積もり条項を入れる |

## 7. 顧客からの定番質問と回答の型

| 質問 | 回答の型 |
| --- | --- |
| 「入力したデータが AI の学習に使われませんか」 | ①推論データは保存されず学習に使われない(公式 NOT リスト)。②ただし悪用監視で検出時サンプル保存があり得る → オプトアウト申請の説明。③ Web 検索系ツールは別枠(DPA 対象外)なので使う/使わないを合意 |
| 「データは国内に留まりますか」 | 4層に分けて回答: 保存=構成で国内固定可 / 推論=geography 型(Standard / Regional Provisioned、Japan East / West)なら国内 / 悪用監視=同一ジオ / ツール=機能による(Web 系は境界外)。※2026-10-10: Copilot Studio を入口にする構成では §2 の Copilot Studio 行で別に答える(推論場所の公式記載が食い違うため、確認前は「推論は国外の可能性あり」) |
| 「誰が会話ログを見られますか」 | RBAC(5ロール)+ プロジェクト分離 + トレースの閲覧権限(Log Analytics Reader)で説明。Microsoft 側は悪用監視の限定レビューのみ(オプトアウト可)。※2026-10-06: 本文だけを保護テーブルに分けて Privileged Monitoring Data Reader の保持者に限定する仕組みもある(§3。2026-10-06 実測では二重書きで、成立を KQL で確認してから説明)。Agent 365 を使うテナントでは活動データがテナントのジオに送られる点も添える(§2) |
| 「AI が変なことを言ったら止められますか」 | ガードレール(モデル向け GA / エージェント向けプレビュー)+ ブロックリスト + HITL 設計。**「完全には防げない」前提で評価・監視・人間承認の多層防御**を提案するのが誠実 |

## 出典(主要)

- データプライバシー: https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy
- 悪用監視: https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/abuse-monitoring
- デプロイタイプ(処理地域): https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/deployment-types
- Speech のリージョンと Voice Live の処理スコープ(2026-10-14 追加): https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions?tabs=voice-live
- AI 生成コンテンツの来歴(2026-10-14 追加): https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/content-safety/provenance-disclosure
- セキュリティベースライン: https://learn.microsoft.com/en-us/security/benchmark/azure/baselines/azure-ai-foundry-security-baseline
- Service Trust Portal(FISC 等): https://servicetrust.microsoft.com/
- ISMAP ポータル: https://www.ismap.go.jp/
