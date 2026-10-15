# 01. 要件シナリオ別プレイブック — 「この要件が来たら何を決め、どこで詰まるか」

[← ケースブック TOP](./README.md)

> **最終更新:** 2026-09-04(初版)/ 2026-09-26(ステータス変化の反映: Routines GA〈S-03〉、Voice Live の表記〈S-10〉、hosted agent のセッション上限・コンテナプロトコル 1.0.0〈S-06〉、サブネット容量・egress controls〈S-04〉。変更箇所は「※2026-09-26」)/ 2026-10-06(差分更新: toolbox 経由の利用者委任〈S-03 / S-06〉、Agent 365 への観測エクスポート・保護テーブル・Terraform の eject 制約〈S-04〉、voice agents と Japan East のリアルタイムモデル〈S-10〉、期限表〈S-11〉、Foundry IQ in Copilot Studio GA〈S-08〉。変更箇所は「※2026-10-06」)/ 2026-10-06(ラボの最新化+ライブ検証の還元: AI Search Free の agentic retrieval〈S-01〉、承認の評価〈S-03〉、保護テーブルの 4 点目とサンプラー〈S-04 / S-07 / 横断〉、音声の移行経路〈S-10〉) / 2026-10-14(差分更新: 既定ストリーミングの末尾漏れ〈S-05〉、hosted agent のユーザー分離の明文化と MAF ホスティングの既定ストア〈S-06〉、Voice Live の処理スコープ表記とテレフォニーの voice agents 誘導〈S-10〉、On Your Data の廃止日・gpt-4.1-nano の再延長・TTS アバターの期限〈S-11〉、capability settings ページの 301〈S-04〉、DI / CU の公式の選び方〈S-09〉、新 P-ID の参照を各シナリオと横断節に。変更箇所は「※2026-10-14」)
> SI で頻出する 10 の要件セットについて、**ゲート判定 → 推奨構成 → 却下した案と理由 → 詰まりどころ → 見積もり・契約で効く点**を 1 シナリオ 1 節で書く。[architecture 03 の 5 ゲート](../architecture/03-decision-guide.md)と [11 の判断フレームワーク](../architecture/11-decision-frameworks.md)を「要件の言葉」から逆に引けるようにしたもの。詰まりどころは [02 索引](./02-pitfalls-index.md)の P-ID で参照する。
> **前提:** 構成の詳細(図・数値・上限)は architecture 各章に置き、本ページは判断と根拠だけを書く。「本ドキュメントの判断」と明記した箇所は公式に書かれていない SI 側の判断。

## シナリオ一覧

| ID | 要件の言葉(顧客が言うこと) | 主構成 | 後戻りコストが最大の決定 |
| --- | --- | --- | --- |
| [S-01](#s-01-社内ナレッジ検索チャット-sharepoint-が主データ) | 「社内文書を検索して答えるチャットが欲しい。データは SharePoint」 | A1 → A2 / A4 | 「部署によって見える文書が違うか」 |
| [S-03](#s-03-承認付き業務自動化-hitl) | 「AI が案を作り、担当者が承認してから実行」 | B2 / B3 | 承認待ちの長さ(分か、日か) |
| [S-04](#s-04-閉域必須の規制業種-金融・公共) | 「インターネットに出ない構成で」 | D1 | VNet 注入の要否(作成時のみ) |
| [S-05](#s-05-顧客向け公開チャット) | 「Web / LINE で一般顧客に公開したい」 | C1 | 会話の認可(BOLA)とコスト上限 |
| [S-06](#s-06-マルチテナント-saas) | 「複数のお客様に SaaS として提供」 | C2 | テナント分離の単位とメータリング |
| [S-07](#s-07-既存システムへの-ai-機能追加-既存-aoai-資産の活用) | 「今の業務システムに AI を足したい」「AOAI は既に使っている」 | L2 = S(Responses API のみ)| Foundry の運用機能を捨てる合意 |
| [S-08](#s-08-copilot-studio-で始めた業務部門から-限界-と言われた) | 「Copilot Studio で作ったが精度・制御が足りない」 | Copilot Studio + Foundry hosted agent の二層 | 移行ではなく分業にできるか |
| [S-09](#s-09-文書・動画処理-idp) | 「帳票・契約書・研修動画を構造化して検索したい」 | E2(DI / CU + AI Search) | DI(決定論)か CU(LLM)か |
| [S-10](#s-10-音声エージェント-コンタクトセンター) | 「電話・音声で対話させたい」 | E1(Voice Live) | 国内処理要件との両立可否 |
| [S-11](#s-11-廃止期限駆動の移行案件) | 「Assistants / prompt flow / On Your Data / 旧 hosted agent で作ったものがある」 | 10 章の移行パターン | 期限までの猶予と状態データの扱い |

複数に跨る案件は、**後戻りコストが最大の決定を持つシナリオを主**にする(例: 「SharePoint RAG だが閉域必須」なら S-04 が主、S-01 が従)。

---

## S-01. 社内ナレッジ検索チャット(SharePoint が主データ)

**要件の言葉:** 「社内規程・マニュアルを検索して答えてほしい」「データは SharePoint にある」「まず PoC で効果を見たい」「運用は情シスが兼務」

**ゲート判定:**

| ゲート | 判定 | 根拠 |
| --- | --- | --- |
| G1 データ | 社外秘だが個人情報は少ない → Regional / Data Zone 可 | 国内処理必須なら Standard / Regional Provisioned(geography 型、Japan East / West。P-M03) |
| G2 ネットワーク | パブリック + Entra 認証で足りることが多い | 閉域なら S-04 へ |
| G3 制御 | 「検索して答える」のみ → Prompt agent(M) | 分岐・承認なし |
| G4 統合 | 新規 AI アプリが主役 → フル統合 | Teams 公開が出口なら P-X 系を確認 |
| G5 ライフサイクル | 1〜2 年・内製運用 → GA 機能のみ、IaC 必須 | プレビュー(SharePoint ツール・Work IQ)は代替可能な範囲に |

**推奨構成:** **A1(File Search)で PoC → 品質が出なければ A2(AI Search 自前索引)**。「部署によって見える文書が違う」なら**最初から A2**(GA 要件を満たす唯一の方式)。SharePoint ツール(A4)は「全員が M365 Copilot ライセンスを持つ」「ユーザー委任(OBO)で動く対話型のみ」のときだけ。

**決め手と却下案:**

- **File Search を本番に押し切らない。**チャンク 800 / 400・埋め込み固定で日本語長文・表主体の文書に合わないことがある(P-R01)。PoC は代表的な難しい文書 20〜30 件で測る
- **SharePoint ツールは「ライセンス+OBO+テキストのみ」の三重制約**(P-R09)。実行時に `User does not have valid license` で落ちるため、接続テストが通っても安心しない。ライセンスがない顧客には AI Search の SharePoint インデクサ案を並記
- **権限別表示は AI Search ツールでは実現できない**(P-R07)。「全員同じ」かどうかをヒアリングで必ず確認し、違うなら A2 で自前セキュリティフィルタ(architecture 04 の 4 方式)
- Foundry IQ(A5)は「複数エージェント / アプリでナレッジを共有」「ACL 同期」が要件のときに価値が出る。単一アプリなら過剰。Partial GA(P-R08)。※2026-09-26: Foundry IQ の MCP ツールは structured input(`{{placeholder}}`)でユーザートークンをリクエストごとに渡せるようになった(クエリ時の権限適用はプレビュー)。ただし**トークンを渡し忘れると権限付きソースが未フィルタで全件返る**(P-R07)ので、権限別表示を A5 で満たす場合は「トークン欠落時の挙動」を受入テストに入れる

**詰まりどころ:** P-R01・R05・R07・R09・R13(日本語アナライザー)・P-I05(API キーで始めてナレッジを足すと Entra 必須)・P-X12(Teams 公開でナレッジ付きだけ失敗)・P-R15(Free の agentic retrieval)・R16(ナレッジベース MCP の応答形は api-version 次第)・※2026-10-14: P-R17(Foundry IQ の retrieve の 401 / 502、SharePoint ソースはカスタム列を取り込まない)・P-M19(Bing 系ツールではプロンプトキャッシュが効かない)

**見積もり・契約で効く点:** AI Search のティア(閉域・本番・同時実行は Basic 以上、閉域なら PE 対応 SKU。※2026-10-06 訂正: 「Basic が実質の下限」ではない — Japan East はリージョン表の脚注で Free でも agentic retrieval とセマンティックランカーが使え、ナレッジベースの小規模 PoC は Free で動いた〈ナレッジソース・ナレッジベース各 3 個、1 サブスクリプション 1 サービス、PE 非対応〉= P-R15)/ M365 Copilot ライセンスの有無 / モデル更改(リタイア 12〜18 か月、P-M07)の運用を契約に含めるか / 評価ハーネス(20〜30 件の正解セット)を PoC の成果物に

**実証状況:** [port 4(corrective-rag)](../../../labs/maf-ports/ports/corrective-rag/README.md)・[port 10(Foundry IQ。2026-10-06 に Basic と Free の両方でライブ合格)](../../../labs/maf-ports/ports/db-routing-iq/README.md)・[probe 03(File Search)](../../../labs/foundry-probes/probes/03-file-search/NOTES.md)

---

## S-03. 承認付き業務自動化(HITL)

**要件の言葉:** 「AI が調査して実行案を提示」「担当者が承認してから実行」「誰が何を承認したか監査に残す」「失敗したステップだけ再開したい」

**ゲート判定:**

| ゲート | 判定 | 根拠 |
| --- | --- | --- |
| G3 制御 | **承認・分岐・再開 → コードファースト確定**(Prompt agent では足りない) | architecture 03 G3 |
| G2 | 基幹連携が社内網なら BYO VNet | ツールは MCP / OpenAPI(VNet サブネット経由) |
| G5 | 監査要件 → 業務監査ログはアプリ側に別途 | Foundry Tracing は 90 日・機微情報を含みうる(P-O08) |

**推奨構成:** **B2(MAF Workflow を hosted agent で実行、`RequestInfoExecutor` で HITL)**。承認待ちが数時間〜数日なら **B3(MAF + Durable Extension、Functions + DTS にホスト)**。ツールは Toolbox(MCP)経由で基幹 API へ(※2026-09-26: Toolboxes は GA)。**起動が「定時・指定日時・GitHub issue / Teams メッセージ」なら Routines(※2026-09-26: GA)でトリガーを持たせ、cron・Webhook 受信の自前配管を省く**。

**決め手と却下案:**

- **ポータルのビジュアル Workflows は 2026-12-01 廃止**なので選ばない。Logic Apps は「業務部門がデザイナーを触る」前提を維持したいときの B5
- **handoff パターンを one-shot 承認フローに使わない**(P-F02)。制御をコードで決められるなら決定的ルーティング(構造化出力 + switch-case)。順序・終了が確率的になる
- **チェックポイントはインメモリ既定**(P-F06)。水平スケールや数日の承認待ちには外部ストアか Durable Extension。hosted agent の中から DTS を使う公式パターンは未確認 → Durable なら Functions か自前コンピュートにホスト。※2026-09-26: hosted agent 専用の durable state store と long-running resilience が出たが**どちらもプレビュー**(P-H17・H18)。G5 で GA 限定なら判断は変わらない
- ※2026-09-26 **Routines(GA)を使う場合の注意**: 呼び出し ID は既定で agent identity。承認者・起票者の権限で OAuth ツールを呼ぶなら**作成時に** creator identity を選ぶ(更新では変えられず、azd 拡張は未対応 = P-A12)。creator は「ルーチン作成者本人」固定で、利用者ごとの委任にはならない。イベント起動の連携先は現状 GitHub issue と Teams チャネルのみ(それ以外のイベントは Webhook を自前で受ける)。CMK 非対応、Japan West を含む 5 リージョンは対象外(P-A11)。自己再起動の reminder ツールはプレビュー
- 更新系ツールには冪等キー・金額 / 権限 / 件数の上限チェックをツール側に置く(プロンプトで「10 万円以上は承認を取れ」は統制ではない)
- エージェントにガードレールを割り当てるとモデル側を完全上書きする(P-G05)。Tool call / Tool response の介入点を置き忘れると未スキャン
- ※2026-10-06: Routines の既定の再試行が**最大 5 回(5〜60 秒)**になり、Responses アクションは background 実行で、30 秒のタイムアウトは「受付」まで(P-A13)。**起動の重複を前提に**、更新系ツールの冪等キー(イベント ID で処理済みを判定)を必須にする。MAF 側でも、background 応答の再ポーリングで関数ツールが二重に実行される不具合が open(P-F16)。「失敗したステップだけ再開」は冪等キーなしでは二重実行と区別できない
- ※2026-10-06: 承認者・起票者の権限でツールを呼ぶなら、toolbox 経由の利用者委任が公式推奨(P-H26)。Routines の creator identity は作成者に固定で、作成者がアクセスや同意を失うと委任ツールの呼び出しが失敗する(P-A12 の注記)
- ※2026-10-06(port 14 のライブ再評価): MAF core の **`ToolApprovalMiddleware(auto_approval_rules=...)`** で「金額が上限以下は自動承認・超えたら人へ」の引数依存の承認はネイティブで書ける(09-29 の「`approval_mode` は静的なので書けない」は不正確だった)。ただし (1) 止めて同じセッションで再開する **pause & resume 型** (2) **DENY を表せない**(承認前は function middleware が走らないので、本来拒否すべき申請もまず人に回る)(3) 承認待ちが監査の連鎖に残らない。**チャット UI でその場で人が答える**ならネイティブで足り、**非対話の HITL キュー・DENY・遮断を含む監査を 1 か所で決定論的に**扱うなら middleware のまま([port 14](../../../labs/maf-ports/ports/governed-agent/README.md#検証結果2026-10-06-ライブ))。core 1.20 でセッションに紐づかないローカル承認は失敗側に倒れるようになったが、自作の agent-as-tool 層はこの fail-closed を受けない(P-F01 の注記)
- ※2026-10-06(ライブ): handoff は順序が正しくても**本文を書かずに handoff だけ呼ぶ**崩れ方がある(P-F17)。agent-as-tool は**必須の相談の発生を保証しない**(P-F18)。どちらも「必須の手順・成果物はグラフとコードで固定する」根拠になる

**詰まりどころ:** P-H05(publish で identity 変更)・H07(プロトコル選定)・H17・H18(長時間 workflow のチェックポイント)・P-A11・A12(Routines のリージョン・dispatch identity)・P-I07(audience)・P-F02・F04・F06・F13(一時エラーで workflow 全体が終了)・P-G05・P-X19(Functions ツールは standard のみ)・P-X20(MCP OAuth)・P-A13(Routines の再試行 5 回・受付と完了の違い)・P-F16(background の再ポーリングで二重実行)・P-H26・P-F17・F18(handoff と agent-as-tool の崩れ方)・※2026-10-14: P-A11 に「`api-version=v1` 省略で 400」がトラブル表で公式化、P-A12 に JS 2.8.0 の creator ID 指定と azd の対応 PR(未リリース)

**見積もり・契約で効く点:** hosted agent の compute(セッション × サイズ、P-H14)/ Durable Task Scheduler / 業務監査ログのストア / 「承認 UI」はスコープに入るか(Teams なら P-X 系)

**実証状況:** [port 3(handoff → switch-case)](../../../labs/maf-ports/ports/research-handoff/README.md)・[port 7(リング)](../../../labs/maf-ports/ports/game-design-team/README.md)・[port 14(middleware ガバナンス)](../../../labs/maf-ports/ports/governed-agent/README.md)・[port 13(agent-as-tool)](../../../labs/maf-ports/ports/services-agency/README.md)(2026-10-06 に port 7・13・14 をライブ再検証)。**Durable Extension・HITL の数日待ちは未実証**

---

## S-04. 閉域必須の規制業種(金融・公共)

**要件の言葉:** 「インターネットに出ない」「プライベートエンドポイントで」「監査で通信経路を説明できること」「データは国内」

**ゲート判定:**

| ゲート | 判定 | 根拠 |
| --- | --- | --- |
| G1 | 国内処理 → Standard / Regional Provisioned(geography 型、Japan East / West)。使えるモデル世代が落ちる(P-M03) | Data Zone APAC は国外含む |
| G2 | **閉域は最初のゲート。作成時に確定・後付け不可** | inbound(PE)と outbound(VNet 注入)は別物(P-N01) |
| G3 | 閉域で使えない機能から逆算 | Tracing VNet / Memory / Work IQ / Logic Apps / Browser 系。File Search は公式表(configure-private-link 2026-08-14 版)で「対応(private endpoint 経由)」になったが、Blob Storage のファイル連携は閉域で非対応 → Blob 上の文書は AI Search ツールへ([architecture 07 §3](../architecture/07-usecase-regulated-edge.md#エージェントツールの互換性)) |
| G5 | 長期・顧客保守 → GA のみ、IaC 必須 | ※2026-09-26 訂正(旧記載「capabilityHost の API は preview 版のみ — サービス面と分けて判断」は誤り): capabilityHosts / connections は安定版 ARM API(2025-06-01 以降)にもあり、**安定版を pin すれば GA 限定ポリシーと両立**(P-C06)。preview なのは後継の capability settings(2026-07-15-preview)。※2026-10-14: capability settings の設定ページが 301 で消え(転送先に記述なし)、取り下げか移設中か要確認(P-C06)。安定版の capabilityHosts を pin する判断は引き続き有効 |

**推奨構成:** **D1(standard setup + BYO VNet 注入 + PE)**。RAG は AI Search 自前索引一択、記憶は自前、観測主系は自前 OTel + App Insights(AMPLS)。hosted agent を使うなら**作成時に注入**。

**決め手と却下案(閉域で「動くはず」が壊れる断面):**

- **VNet 注入なしのエージェントは PE 付きのリソースに届かないことがある**(P-N21)。公式ツール表の「PE 経由で対応」は standard setup + 注入が前提で、注入は作成時のみ(P-N01)。インバウンド遮断だけの要件でも、閉域で hosted agent を使うなら注入つきで作る
- **PE を貼っただけでは outbound は閉じていない**(P-N01)。顧客の「閉域」を inbound / outbound / ツール別経路に分解して合意(Bing / Web / SharePoint Grounding はパブリック経路、P-N06)
- **Tracing VNet は Preview**(P-N14)。監査主系を Foundry トレースに置かない
- 「ポータルは見えるのに Playground が死ぬ」は DNS(6 ゾーン)が定番(P-N02)。踏み台(Bastion)をコストに積む
- 委任サブネットは /27 最小・/24 推奨。IP 枯渇はポータルに出ない(P-N05)。※2026-09-26: 公式は「/27 は本番に使わない」と明記し、容量表は /27 ≈ 20・/24 ≈ 250 セッション。hosted agent は枯渇時に 429 `subnet_exhausted`
- 閉域のツール呼び出しが約半分の確率で `TaskCanceledException` になるサービス側の既知問題がある(P-N20)。「リトライで通った = 顧客 DNS / NSG は正常」と判定しない
- ※2026-09-26: Routines(GA)は VNet 保護プロジェクトで追加設定なしに使えるが **CMK 非対応**(P-A11)。CMK 必須の規制案件ではスケジュール起動を自前(Functions タイマー等)に残す
- 評価・レッドチーミングは日本リージョンで完結しない(P-O07)。評価データが国外に出る点を所在方針に明記
- FW の TLS 検査がエージェント通信を壊す。Agent Service の固定 IP はない(P-N07)。※2026-09-26: hosted agent の network egress controls(**プレビュー**、ホスト名単位の Allow / Deny、Audit → Enforce)が使えるようになったが、公式は **Azure Firewall の補完であり置き換えではない**と明記(サービスタグ / IP 範囲ルールなし、prompt agent には効かない)。egress の統制主系は引き続き顧客 Firewall で設計し、egress controls は「エージェント定義に宛先ポリシーを持たせる」追加層として扱う(P-N07)
- ※2026-10-06: hosted agent の公式ホスティングライブラリは **Agent 365 へ観測データを送る**(`agent365.svc.cloud.microsoft`、TCP 443。Agent 365 が有効なテナントでは既定で有効)。FW で止めるとエージェントは動くが拒否ログが溜まり続ける → 使わないなら Foundry リソースで `a365LoggingEnabled=false`(変更後に始まったセッションから有効)、使うなら FQDN で許可(サービスタグ `AzureFrontDoor.Frontend` は Front Door 全体)(P-H27)。Agent 365 側のデータは Entra テナントの保存場所に置かれる点も所在の説明に入れる
- ※2026-10-06: 監査用に会話本文を残す場合、同じ App Insights のまま本文だけを保護テーブル(`AppGenAIContent` を Protected + Privileged Monitoring Data Reader)に隔離する公式の仕組みがある(preview)。ただし **2026-10-06 の実測では本文が従来テーブルにも残る「二重書き」**で、Protected にしただけでは隠れない(P-O13)。採用はフラグ登録か移行の完了・Protected 化・ロール付与に、※2026-10-06 ラボ還元で判明した **4 点目 —「`gen_ai.*` 以外に本文を書く計装(MAF のメッセージイベント・自前ログ)を止める」**(P-O18)を加えた 4 点がそろったことを KQL で確かめてから
- ※2026-10-06: azd の Terraform 出力(`azd ai agent init --infra=terraform`)は service の `network:`(PE・エージェント注入サブネット)を eject できない(P-C13)。閉域の IaC は Bicep のままにするか、AzAPI で自前に書く
- ※2026-10-06: 監視の主系を自前 OTel + App Insights にする場合、azure-monitor-opentelemetry 1.8.x の**既定サンプラー(5 スパン / 秒)でトレースが歯抜けになる**(P-O16)。`sampling_ratio=1.0` を設定し、取り込み量も見直す。トレースを監査の証跡の代わりにしない理由がもう 1 つ増えた。※2026-10-14: azure-monitor-opentelemetry 1.8.11(2026-10-07)でも既定サンプラーは変わらず、`sampling_ratio=1.0` は引き続き必要

**詰まりどころ:** P-H09(private ACR は 2026-06-25 以降のプロジェクト)・P-N01〜N20 のほぼ全部・P-I06(カスタムサブドメイン)・P-C06・C11・P-O06(評価はストレージ公開必須)・P-M03・P-H27(Agent 365 への観測エクスポート)・P-O13(保護テーブルの二重書き)・P-O18(`gen_ai.*` 以外の本文は振り分け対象外)・P-O16(既定サンプラー)・P-C13(Terraform の eject は `network:` 非対応)・※2026-10-14: P-N21(VNet 注入なしのエージェントは PE 付きの Search に繋がらないことがある)・P-A17(Browser Automation は GA 表明後も閉域非対応)・P-C17(Search の自動生成 DNS ラベル)・P-N12(PNA 無効時の M365 公開は受信が公衆インターネット経由)

**見積もり・契約で効く点:** 固定費(Bastion / Firewall / Premium SKU / PE 群、P-N16)/ CapHost 作成 30 分超・purge 20 分のデプロイ時間(P-N15)/ セルフホストランナー(P-N11)/ Regional Standard のクォータが桁違いに小さい(P-M03)

**実証状況:** **未実証**(labs は公開ネットワーク構成。VNet 注入つき hosted agent の構築は公開記事も対応後のものは見当たらない)

---

## S-05. 顧客向け公開チャット

**要件の言葉:** 「Web サイト / LINE で一般顧客に」「不特定多数」「炎上しない」「月額上限を守りたい」

**ゲート判定:**

| ゲート | 判定 | 根拠 |
| --- | --- | --- |
| G1 | 顧客個人情報 → PII マスキング(保存境界で)、会話ログの所在 | basic か standard か |
| G2 | 公開 + WAF + APIM | 閉域ではない |
| G3 | FAQ 中心なら Prompt agent、複雑なら hosted | — |
| G5 | SLA → プレビュー排除 | Guardrails for agents はプレビュー |

**推奨構成:** **C1(App Gateway / WAF + APIM + Prompt / hosted agent + Guardrails)**。認証は外部 IdP → フロントで変換。

**決め手と却下案:**

- **BOLA を自前で潰す**(P-A05)。conversation ID を渡せば誰の会話でも読める。所有権検証をリクエストごとに
- **コストのハードリミットは Foundry にない**。APIM の `llm-token-limit` + 予算アラート + 自作の自動停止。429 / 403 の両方をハンドリング(P-X16)。直接キーを禁止しないとゲートウェイを迂回される
- **コンテンツフィルターはフェイルオープン**(P-G03)。`content_filter_results` の検証を必須実装に。Prompt Shields の誤検知はドメイン別に計測(P-G02)。日本語は `ensure_ascii` の罠(P-G01)
- ストリーミングは既定フィルタ(非同期フィルタは表示済み内容の取り消しが要る、P-G04)。※2026-10-14: 既定ストリーミングでも応答の末尾(試験では約 15〜30 語)がガードレール適用前に届きうると公式に注記された。禁止語・個人情報の流出が許されない画面は非ストリーミングにするか、最終区切りをアプリ側で再検査してから表示を確定する(P-G12)
- Claude を選ぶならフィルタを APIM / アプリ側で(P-M05)

**詰まりどころ:** P-A05・P-G01〜G04・G11(hosted agent のストリーム出力モデレーションが無言でスキップ)・P-X15〜X17・P-M05・M06(model router が Grok へ。※2026-10-14: Fireworks の 3 モデルも既定プールに入った)・P-M12(PTU 誤設定の請求事故)・P-M16・M17・P-X16(※2026-10-06: `llm-token-limit` の並列時の超過の実測)・P-G12(※2026-10-14: 既定ストリーミングでも末尾が漏れうる)

**見積もり・契約で効く点:** WAF チューニング工数 / APIM のティア / PTU か Standard か(スパイクは spillover。※2026-10-06: GPT-6 系の PTU はキャッシュ入力も容量を消費する = P-M16)/ 評価と継続評価(judge のクォータ、P-O06。※2026-10-06: 合成評価器〈preview〉で複数の評価をジャッジ 1 回に束ねられる = [proposal 02](../proposal/02-cost-estimation.md))/ 低遅延の割増(priority processing)は応答の `service_tier` で効果を確かめる(P-M17)/ RAG を含むなら AI Search の SKU(※2026-10-06: Japan East なら Free で agentic retrieval の小規模 PoC が可能。公開本番は Basic 以上 = P-R15)

**実証状況:** [probe 07(ガードレール)](../../../labs/foundry-probes/probes/07-guardrails/NOTES.md)・[probe 05(model router)](../../../labs/foundry-probes/probes/05-model-router/NOTES.md)。**WAF / APIM を含む公開構成の E2E は未実証**

---

## S-06. マルチテナント SaaS

**要件の言葉:** 「複数のお客様に同じエージェントを提供」「テナントごとに課金」「テナント間でデータが混ざらない証明」

**ゲート判定:** S-05 に加えて **G4 = テナント分離の単位**(プロジェクト / デプロイ / 索引 / 会話)と **L11 = APIM が事実上必須**(テナント別メータリング)。

**推奨構成:** **C2(hosted agent + コンテナプロトコル 2.0.0 + テナント別索引 + APIM)**。会話は standard setup(BYO Cosmos)か自前セッションストア。

**決め手と却下案:**

- **hosted agent は 1 セッション内の複数ユーザー多重化がプロトコル 2.0.0 前提**(1.0.0 は 2026-07-31 からブロック。※2026-09-26: 現行の isolate-sessions-per-user ページは「1.0.0 は非サポートでプラットフォームがブロック」とだけ書き、日付の記載はない)。利用者の分離は、中間層が呼び出しごとに **`x-ms-user-identity`** ヘッダーで対象ユーザーを指定し(中間層の ID に `…/agents/endpoints/UserIdentityImpersonation/action` をカスタムロールで付与。組込みロールには含まれない)、コンテナ側はプラットフォームが注入する `x-agent-user-id` を読む(※2026-09-26 訂正: 旧記載「`x-agent-user-id` で分離」はコンテナ側の話で、呼び出し側はこのヘッダーを送らない。multiplex-session-users 参照)。テナント別の状態は durable state store のユーザー単位パーティションでも持てるが**プレビュー**(P-H17)
- ※2026-10-14: 公式 4 ページ(isolate-sessions-per-user ほか、ms.date 2026-10-13)の整理で境界が明文化された(新機能ではない)— `x-ms-user-identity` で**委任された利用者どうしはプラットフォームが隔てない**(境界は委任あり / なしの間だけ)、意図的にセッションを共有する multiplex でもコンテナが自分で保存するデータは自動では分かれない(保存キーを `(agent_session_id, user_id)` に)、プロジェクトの Foundry User は全利用者のセッションを一覧・管理できる(P-H30)。テナント = 利用者のまとまりとしてセッションを割り当てる設計では、セッション ID を中間層がサーバー側の認証済み ID から作ることを受入条件にする。MAF ホスティングの既定ストアはユーザー ID × セッション ID で分けて保存し、ライブラリ更新後は旧データを読まない(P-F20)。azd で分離を試すときは `--new-session --new-conversation`(P-C15)
- **同一アカウント内の全プロジェクトがモデルデプロイを共有**(P-N15)。プロジェクト単位のモデル分離が要件ならアカウントを分ける(クォータ分割・PE 追加)
- Responses API はテナント分離が難しいと公式に書かれている(architecture 06)。会話・ファイル・vector store の名前空間を自前で
- 実行時のツール上書き(`vector_store_ids` 等)でテナント別ナレッジを切り替えられる(バージョンを増やさない)。ただし File Search の attributes フィルタは効かない報告(P-R01)
- チャージバックは「次元設計 → 単価 → 自動化」の順(P-X17)。高カーディナリティで監視コストが跳ねる
- ※2026-10-06: toolbox の利用者委任(OAuth identity passthrough)は**利用者のテナントと Foundry プロジェクトのテナントが一致**している必要があり、クロステナントのトークン交換は非対応(P-H26・P-X20)。「顧客テナントの利用者が、顧客側のシステムを本人の権限で使う」SaaS はこの方式では組めないので、顧客テナントごとに Foundry を置くか別の方式を検証する

**詰まりどころ:** P-A05・P-N05(セッション = IP)・P-N15・P-X15〜X17・P-H06(カナリア不可。※2026-10-06: 公式ページ間で記載が割れた)・P-H14(セッション × サイズ課金)・※2026-10-14: P-H30(委任された利用者どうし・multiplex のコンテナ側データ)・P-F20・P-C15・P-A16(Memory の scope は `x-memory-user-id` で別ヘッダー)

**見積もり・契約で効く点:** 委任サブネット /24(閉域なら)/ テナント数 × プロジェクト数の Cosmos RU / APIM Premium / 同時セッション上限(※2026-09-26 更新: hosted agent の同時セッションは**サブスクリプション × リージョン単位**で既定 2,000〈Japan East・East US 2 等 7 リージョン〉/ 1,000〈その他〉、全アカウント・プロジェクト合算。超過は `session_quota_exceeded` / `regional_session_quota_exceeded`、増枠はサポート依頼。VNet 注入構成ではさらに**委任サブネットの IP 数**(既定 1 セッション = 1 IP、/24 ≈ 250)で頭打ちになる 2 段構え = P-N05。旧記載「既定 50」は根拠ページの現行版と一致しない)

**実証状況:** **未実証**(labs は単一テナント)。公式の 4 方式比較(architecture 06)と C2 図まで

---

## S-07. 既存システムへの AI 機能追加 / 既存 AOAI 資産の活用

**要件の言葉:** 「今の業務システムにチャットを足したい」「認証・監査は既存のまま」「Azure OpenAI は既に使っている」「他クラウドも使うのでロックインは避けたい」

**ゲート判定:** **G4 = 既存システムが主**。Foundry はモデル + プラットフォームツールの供給元(L2 = S)。

**推奨構成:** **既存アプリ内オーケストレーション + Responses API のみ利用**(architecture 10 §2.5)。既存 AOAI リソースは Foundry リソースへ非破壊アップグレード(§2.4)。

**決め手と却下案:**

- **Foundry の運用機能(Tracing / Evaluations / エージェント公開)を捨てることになる**点を提案時に明示(P-O01)。トレースだけは自前 OTel で部分的に取り戻せる
- 「後で Foundry に載せ替える」は無料ではない。ツール定義は移るがオーケストレーションは書き直し。載せ替えの判断材料として評価ハーネスを先に作る
- AOAI アップグレードは CMK 利用リソースは申請フォーム、既存 PE 付きはポータル不可(architecture 10 §2.4)。`foundryAutoUpgrade` の drift を IaC で検知
- gpt-5 系へのモデル更改でパラメータが壊れる(P-M01)。ライブラリが勝手に付与する `temperature` / `max_tokens` を grep で見つけられない
- API キー運用のまま OBO ツール(AI Search 等)を足すと Entra 必須(P-I05)

**詰まりどころ:** P-O01・P-M01・M07・M15(新モデル直後のプロジェクト面 500)・P-I05・I06・P-A01(v1 / v2 混在)・P-A03(Assistants 廃止)・P-F14(既存の LangChain / llama-index 系と `openai>=3` 必須の Foundry SDK が同居できない)・P-O16(※2026-10-06: 自前 OTel の既定サンプラーでトレースが歯抜け)・P-O17(`az monitor app-insights query` の既定 1 時間)

**見積もり・契約で効く点:** 自前オーケストレーションの保守工数 / モデル更改の運用(契約論点)/ 評価基盤を最初に作るか

**実証状況:** [tech-selection-guide §1-3](../../tech-selection-guide.md#1-3-フレームワーク書き換えコストの実測感全ポート)(フレームワーク書き換えの実測感)

---

## S-08. Copilot Studio で始めた業務部門から「限界」と言われた

**要件の言葉:** 「Copilot Studio で作ったが回答精度が上がらない」「ツールが増えて誤選択する」「基幹 API を叩きたい」「業務部門が引き続き触りたい」

**ゲート判定:** architecture 11 §2 の乗り換えシグナル 3 つ — **30〜40 アクション超 / 多段のエージェント階層 / 決定的ワークフローが業務クリティカル** — に当たるものだけがプロコード側。

**推奨構成:** **二層構成**: Copilot Studio = 体験層(対話の入口・M365 チャネル・業務部門の保守)、Foundry hosted agent = 業務固有の複雑な処理。接続は connected agent(プレビュー)か **Responses エンドポイント直叩き(HTTP ツール)**。

**決め手と却下案:**

- **「移行」ではなく「分業」にする。**開発者不在のまま Foundry へ「機能アップグレード」として移行するのが最頻の失敗(P-X06)。コスト所有(Azure)・サポート窓口・CI/CD・監視が変わる
- **connected agent は本番で壊れやすい**: テストパネルでは動くのに Teams / M365 Copilot チャネルで定型エラー(P-X02)。Activity プロトコルの有効化は REST / SDK のみでポータルに出ない(P-X01)。本番は Responses エンドポイント直叩きを第一候補に
- Foundry 側の出力は「プレーンテキスト・短文」に制約する出力契約を仕様化(Markdown 表・引用・ストリーミングは Teams で描画失敗)
- Copilot Studio 側の課金: 125% 超で全エージェント停止、推論モデルは 100 倍クレジット(P-X05)
- 単一 vs マルチは CAF の 3 条件(architecture 11 §3)。「役割分担があるからマルチ」は理由にならない
- ※2026-10-06: **Foundry IQ in Microsoft Copilot Studio が GA**(Tech Community 2026-10-01。Azure Private Link + Power Platform の VNet 対応で、Search サービスの公開アクセスなしに接続できる。リンク先の Learn ページの題は「(Preview)」のまま — 要確認)。限界の理由が「ナレッジの精度」だけなら、hosted agent を挟まず Copilot Studio から Foundry IQ のナレッジベースに直結する案を、二層構成より先に検討できる(権限別の表示は利用者ごとの出し分けを受入試験に)
- ※2026-10-06: Foundry エージェントを Teams / M365 Copilot に公開して公開者以外が使えない場合の公式の対処が出た(`BotServiceTenant` への切り替えか Foundry Agent Consumer の付与。PATCH は認可方式の配列ごと置き換える = P-I08 の注記)。azd で Activity プロトコル付きの hosted agent を deploy すると Bot の重複判定で失敗する不具合も open(P-C14)

**詰まりどころ:** P-X01〜X06・P-X10(Teams SSO は Foundry にない)・P-I08(公開後の認可)・P-C14・P-X11(Teams から OBO で MCP は不可)・P-I12(Agent ID 無効化の挙動差)・※2026-10-14: P-X08(ゲストユーザーは公開エージェントを呼び出せない)・P-N12(PNA 無効時はアプリパッケージ ZIP を管理センターでアップロードする代替)

**見積もり・契約で効く点:** 受託範囲を「connected agent として呼ばれる Foundry hosted agent」に切る / Copilot Studio 側のクレジット試算(1 対話あたり)/ 接続がプレビューである点の明示(G5)

**実証状況:** **未実証**(labs に Copilot Studio 接続なし)。公式ドキュメント + Q&A の失敗事例のみ

---

## S-09. 文書・動画処理(IDP)

**要件の言葉:** 「請求書・契約書を読み取って構造化」「研修動画を検索できるように」「紙をスキャンした PDF」

**ゲート判定:** 定型帳票(信頼度スコア重視)は **Document Intelligence(決定論)**、非定型・可変レイアウト・マルチモーダルは **Content Understanding(LLM)**。CU は新ポータル未対応(classic)・BYO モデル接続必須・リージョン限定。

※2026-10-14: 公式ブログ(devblogs 2026-10-07「Azure Document Intelligence and Azure Content Understanding: a practical guide」)は、**新規クラウドの OCR / Layout は CU の `prebuilt-read` / `prebuilt-layout`**(LLM・埋め込みを使わず決定論的、同期 / 非同期 API)を推奨し、要件を満たしている既存の DI ワークロードは移行不要、オンプレ・切断環境は DI コンテナ、ラベル付き学習データがある高定型のカスタム帳票は DI カスタム、と整理した。上の「定型 = DI(決定論)」は抽出・カスタム帳票の話として読み、OCR / Layout 単体には当てはめない([features 07](../features/07-foundry-tools.md))。

**推奨構成:** **E2(非同期パイプライン: CU / DI → 正規化 → AI Search 索引 → エージェント)**。大量処理は Batch(50% 割引)。

**決め手と却下案:**

- **CU の罠 13 点**(P-D01): セグメントが先頭・末尾を覆わないと発話が消える、重複セグメント、アナライザーは実質イミュータブル(PUT 上書きが黙って無視)、defaults は再デプロイで再登録、ソフト削除 → パージ → 同名再作成で内部モデル解決が壊れる
- **請求が 2 か所に分かれる**(P-D02): LLM / 埋め込みトークンは Foundry モデルデプロイ側。代表ファイルで `usage` を実測してから見積もる(動画 1 時間 ≈ $2.7〜2.9 の実測)
- CU 動画は 1 FPS・512×512(P-D03)。「画面上の細かい文字の転記」「高速動作の検知」は単体では満たせないと明示
- 評価設計の落とし穴: 回答値の動画間衝突、「動画を問わない」ans@k(cu-video-rag §1-11)。正解セットの一意化を先に
- 日本語アナライザー未指定は事故(P-R13)

**詰まりどころ:** P-D01〜D04・P-D10(※2026-10-06: CU の usage に新しい費目 cached-input)・P-R13・P-M03(CU のリージョン)

**見積もり・契約で効く点:** CU の contextualization トークン別建て / advanced レート(agentic・ラベル付き)/ ページ・サイズ上限 / 前処理(画像入り PDF・文字エスケープ正規化)の工数

**実証状況:** **[cu-video-rag](../../../labs/cu-video-rag/README.md)**(104 本・111 クエリ・ragas、CER 0.44%、ans@3 0.67、コスト $12。2026-10-06 の 4 本スモークでも同じ傾向)

---

## S-10. 音声エージェント(コンタクトセンター)

**要件の言葉:** 「電話で受け付けたい」「リアルタイムで対話」「日本語」「通話録音は国内に」

**ゲート判定:** **G1 国内処理 × リアルタイム音声は現時点で両立しない**(P-M08: 音声モデルは Japan East に遅い。Japan East は Voice Live 対応だがネイティブ音声モデル非提供)。SIP 非対応(ACS か既存 PBX が別途)。

※2026-10-06: Speech のリージョン表(2026-09-30)で Japan East の Voice Live に `azure-realtime` / `gpt-realtime-2.1` / `gpt-realtime-2.1-mini` が **Global standard** で追加され、「Japan East はネイティブ音声モデル非提供」は当てはまらなくなった(当時の表とは一致していた。状況の変化)。ただし Global standard なので、**ネイティブ音声(speech-to-speech)× 国内処理は引き続き両立しない**(Data Zone 版は japaneast にない)。国内処理が要件なら、テキストモデルを japaneast の Standard(表では `gpt-4o`)にする cascaded 構成か BYOM を候補にし、音声認識・合成を含む全経路の処理場所を確認する(architecture 08 E1)。新しい voice agents(preview)は Teams Phone extensibility / Twilio の組込みテレフォニーを持つ(SIP 直結ではない)。

※2026-10-14: Speech の regions の Voice Live タブ(2026-10-08)が**処理スコープ**(Global / Data zone / Regional)の表記になり、「Voice Live は音声認識・HD 音声合成・LLM 推論がそれぞれ別の処理スコープを持ち、リソースのリージョン外で処理されうる」と明記された。Japan East で Regional(国内処理)になる LLM は **gpt-4o と phi4-mm-realtime(preview)だけ**で、音声機能は HD voices = Global・mai-transcribe-2(preview)= Global・mai-transcribe-2-streaming = 提供なし。LLM を gpt-4o にしても、HD 音声や MAI-Transcribe を選ぶとその部分は国外処理になりうる。国内処理を要件にするなら gpt-4o + `azure-speech` の書き起こし + 非 HD の音声が候補だが、`azure-speech` と非 HD 音声の処理スコープは表に記載がないので Microsoft に確認する(P-M08)。

**推奨構成:** **E1(Voice Live API、3 層分離: 音声非依存コア / テキスト / 音声)+ ACS**。UI / オーケストレーションは日本、音声処理だけ Global の分離案を最初から提示。

※2026-10-06: 新規構築なら **voice agents(`kind: voice`、preview)**も候補 — speech-to-speech とテキストモデルの両方、サービス管理のモデル(デプロイ不要)、Teams Phone / Twilio の組込みテレフォニー、音声パイプライン全体のトレース、録音は opt-in。G5 でプレビューを許容できないなら従来どおり Voice Live API(GA)+ ACS。Voice Live と Agent Service(classic)の連携は 2026-08-31 で非推奨になり、Voice Live × 新 Agent Service の構成から voice agents への移行ガイド(migrate-from-voice-live、2026-09-30)が出た(移行は新しいエージェント名で作り直し、既存のテキストエージェントはサブエージェントとして再利用可)。

※2026-10-14: Voice Live のテレフォニーのページ(voice-live-telephony 2026-10-08)は、コールセンターは voice agents(preview)のネイティブ電話連携(Teams Phone extensibility / Twilio)を使い、既存の Voice Live テレフォニー(アクセラレーターを含む)も voice agents へ移行するよう誘導する形に変わった。アプリ側で電話連携を持つ場合だけ Call Center Voice Agent Accelerator + ACS(ACS 番号か SIP の direct routing)。**推奨経路がプレビューになった**ので、本番のコールセンター案件は「GA の Voice Live API + ACS(アプリ管理)」と「preview の voice agents のネイティブ連携」を分けて提示する。

**決め手と却下案:**

- **Voice Live のステータスは面ごとに違う**(※2026-09-26 訂正: 旧記載「Voice Live はプレビュー(GA 一覧表)」は Agents 連携面の表記を API 全体に広げていた)。Voice Live API 単体は GA、GA 一覧表の「Agents — Voice Live」は Preview のまま(2026-09-23 取得版)、devblogs 7・8 月号は「Hosted Agents with Voice Live は GA」と明言 → 採用面ごとに [features 07](../features/07-foundry-tools.md) で確認し、提案書には根拠 URL を併記。ガードレールは組込みで変更・無効化不可(P-G06)。修正が要件なら BYO model 経路
- 日本語の誤認識・言語自動検出・EOU の早発はロケール固定・フレーズリスト・EOU 設定で(P-D05)
- ACS 連携は 24 kHz / 16 kHz のリサンプリング・再接続・監視を初期スコープに(P-D06)
- gpt-realtime はピーク時間帯に ResponseFailed、WebSocket 1006(P-D07)。単一リージョン前提にしない。OpenAI 直のサンプルをそのまま移植しない
- 音声非依存コアを分離すると移植とテストの両方に効く(port 12)
- ※2026-10-06: voice agents の実測(Microsoft 社員の 300 ターン): 接続の確立 3.72〜12.37 秒、利用者の体感の典型 1.3〜1.5 秒(マネージド gpt-realtime-2.1 / cascaded gpt-4o-mini)、cascaded を gpt-5 にすると 3.45 秒。Foundry のモニタ値は VAD の判定後からでサブ秒に見える(P-D08)。SLO は利用者側の時計で定義し、接続は会話の前に張る
- ※2026-10-06: voice agents の制約 — サブエージェント(既存のテキストエージェントを専門家として呼ぶ)は VNet 分離プロジェクトで非対応、WebRTC は自前デプロイのモデルと hosted conversation engine に非対応(WebSocket を使う)。Voice Live の WebRTC how-to は GA 表記になった(2026-10-01。GA 一覧表での裏付けはない)。※2026-10-14: WebRTC の制約の記述は現行の migrate-from-voice-live(2026-10-06 版)から消え、一般表現だけになった(解消か移動かは要確認 — P-D08)
- ※2026-10-06(port 12 ライブ): **Japan East のリソースで移行経路 `gpt-realtime-2.1-mini`(書き起こし whisper-1)が通過**した。ただし `session.updated` の実効モデル名は `gpt-realtime-2.1-mini-global-standard` で **Global standard 処理**(国内処理にはならない)。表にないモデル × 書き起こしの組合せも受理されるが動作の保証ではない(P-D09)。ネイティブ音声モデルは応答が長く(受信音声が約 3.8 倍)、エスカレーション判定の後も質問を続けて決定論の次質問から外れた → **「LLM は口、決定論は頭脳」の分業(音声非依存コア)を保つ**。既定の gpt-4.1-mini は Azure OpenAI のリタイア表で Deprecated(2027-04-14 退役)
- ※2026-10-14: voice agents に toolbox をコードで添付できるようになった。遅延対策として、まず tool search なしで試し、tool search はツールが 10〜15 個を超える大きな toolbox で使う(P-D08)。標準音声の TTS の 429 は多くの場合クォータではなく、その音声 × リージョンのバックエンド容量不足で、クォータを上げても解消しない(P-D11)

**詰まりどころ:** P-D05〜D09・P-M08・P-G06・※2026-10-14: P-D11(TTS の 429 は容量不足)

**見積もり・契約で効く点:** Voice Live のセッション上限・クォータ(architecture 08 E1)/ ACS の通話料 / マイク・電話の実機検証環境 / プレビュー依存の明示(Agents 連携面・BYO model・voice-based prompt agent〈`kind: voice`〉はプレビュー)/ ※2026-10-06: voice agents の費用はモデルのホスティング(managed / self_deployed)・音声トークン・接続時間・ツール・録音やアバターで決まる。GPT-Live(全二重)を WebRTC で使うと 1 セッション最低 15 秒の課金(WebSocket は対象外)([proposal 02](../proposal/02-cost-estimation.md))/ ※2026-10-14: voice agents のトレースに載る推定コスト属性(`microsoft.foundry.voice.estimated_cost.*`)は請求記録ではない(請求は Cost Management)/ TTS アバターの標準アバター(Jeff の全スタイル・Lisa の 4 スタイル)は 2026 年 12 月から利用不可 — アバターを使う案件は代替アバターの選定を含める

**実証状況:** [port 12(claim-voice-live)](../../../labs/maf-ports/ports/claim-voice-live/README.md)(WebSocket 接続 + ツールループまで。2026-10-06 に Japan East で `gpt-realtime-2.1-mini` の移行経路も通過。**実機音声・電話は未実証**)

---

## S-11. 廃止期限駆動の移行案件

**要件の言葉:** 「Assistants API で作ったものがある」「prompt flow で組んだ」「ハブベースのプロジェクト」「Azure OpenAI On Your Data で RAG」「去年の hosted agent プレビューで作った」

**ゲート判定:** 期限(architecture 10 §1)と **状態データの扱い**が全て。

| 資産 | 期限 | 状態データ | 移行先 |
| --- | --- | --- | --- |
| Assistants API / Agents v1 | 2026-08-26 / 2027-03-31 | **移行されない**(自前エクスポート) | Responses API(P-A03) |
| hosted agent 旧基盤 | 2026-08-20(EOS 済み) | 再デプロイ | 新基盤(P-H15) |
| ビジュアル Workflows | 2026-12-01 | YAML は hosted agent でなら実行継続 | MAF(推奨)/ Logic Apps / A2A |
| On Your Data | 2026-10-14(※2026-10-06 時点で残り 8 日。※2026-10-14: 本日が廃止日。ページは「will be retired」の未来形のままで、廃止後の挙動の記載はない) | チャンク / 厳密度の挙動差 | Agent Service + Foundry IQ(P-R12) |
| prompt flow | 2027-04-20 | — | MAF |
| ハブベース(classic) | 未発表(投資停止) | プレビュー期の Agent state は対象外 | Foundry プロジェクト(自動ツールなし) |
| ※2026-10-06 追加: モデル(直近の期限。リタイア表 2026-09-28 版) | ~~gpt-4.1-nano 2026-10-14~~(※2026-10-14 更新: 2027-04-14 に戻った。3 度目の往復で、本日のリタイアは発生しない)/ gpt-4o-transcribe・gpt-4o-mini-transcribe・gpt-4o-mini-tts・sora-2 10-15 / Cohere-command-a-plus-05-2026 10-16 / gpt-image-1 10-23 / claude-haiku-4-5 11-15・claude-opus-4-5 11-24・claude-sonnet-4-5 11-30(3 つとも 10-19 から延長)/ codex-mini 11-15 / o1・o3・o3-mini・o4-mini 系 11-19 / gpt-4o(2024-05-13)12-09 / tts・tts-hd・whisper・gpt-realtime-mini 12-15(期限到来済み: MAI-Image-2.5 系 10-01、Kimi-K2.7-Code 10-03。※2026-10-14 追加: `FW-Kimi-K2.6`・`FW-Kimi-K2.7-Code`・`FW-Inkling` の Pay-per-token 09-25 — リタイア表に載らない期限、P-M18)/ ※2026-10-14 追加: Grok 4.7 以降の GA モデルは「最低 6 か月提供」(P-M07) | 状態データなし(デプロイの差し替え。PTU は自動で上がらない) | 表の後継(o 系 → gpt-5.6-sol / gpt-5.6-terra、claude-sonnet-4-5 → claude-sonnet-5-5、gpt-4o → gpt-5.6-sol 等)。評価で品質を確かめてから切り替える(P-M07) |
| ※2026-10-06 追加: Voice Live × Agent Service(classic) | 2026-08-31(非推奨化済み) | — | Voice Live × 新 Agent Service、または voice agents(preview、S-10) |
| ※2026-10-06 追加: Anomaly Detector | 2026-10-01(サービス終了済み。Learn のドキュメントも 2026-10-05 にアーカイブ) | — | 本セットでは後継を未調査(案件ごとに確認) |
| ※2026-10-14 追加: TTS アバターの標準アバター | 2026 年 12 月(月単位の表記のみ。Jeff の全スタイルと Lisa の graceful-sitting / graceful-standing / technical-sitting / technical-standing) | — | 他の標準アバター・カスタムアバター(standard-avatars 2026-10-12 版。実在の俳優ベースのアバターは俳優とのライセンス契約に依存と明記) |

**決め手と却下案:**

- **棚卸しから始める。**Assistants の利用箇所を一括発見する単一ツールはない(P-A03 の 4 手法)。エンドポイント形式(`openai.azure.com/openai/assistants` vs `services.ai.azure.com/api/projects/...`)で世代判定
- **SDK の世代混在**(P-A01・A02): `azure-ai-projects` 1.x と 2.x は非互換。上位フレームワーク(SK / MAF / LangChain)経由でも明示 pin
- **SK / AutoGen → MAF は「再実装 + 回帰評価」として見積もる**(P-F07)。import 置換でテストは通るのに挙動が違う。ゴールデン会話 20 本以上、旧経路を 1 リリース残す
- 旧 hosted agent 記事は読み替えが必要(P-H15)。`agent.yaml` → `azure.yaml`、LangGraph アダプタは廃止(P-F10)
- classic の Managed VNet はエージェント outbound を守らない(P-N17)。閉域化しようとせず新プロジェクトへ
- ※2026-10-06: **リタイア表は往復改訂される**(Claude 4.5 系は 10-19 から 11 月へ延長。gpt-4.1-nano は 10-14 のまま)。延長を当てにせず、期限の 1 か月前には後継モデルで評価を終える計画にする(P-M07)。On Your Data(10-14)と gpt-4.1-nano(10-14)は同じ日に来る。※2026-10-14 更新: gpt-4.1-nano は 2027-04-14 に戻り(2026-09-07 → 09-26 → 10-14 で 3 度目の往復)、同じ日ではなくなった。期限当日の直前まで動いた前例なので、延長も前倒しも当てにせず、期限の 1 か月前に評価を終える計画を変えない。Fireworks のモデルにはリタイア表にない期限がある(P-M18)

**詰まりどころ:** P-A01〜A03・A10・P-H15・P-F01(MAF のマイナー破壊的変更)・F07・F10・P-R12・P-N17・P-M07(リタイア表の往復改訂)

**見積もり・契約で効く点:** 会話履歴の移行(なし前提)/ 2 クライアント構成への改修範囲 / 評価基盤(移行の合否判定)/ 期限内に PoC → 本番が収まるか(7-3)

**実証状況:** [tech-selection-guide §1-3](../../tech-selection-guide.md#1-3-フレームワーク書き換えコストの実測感全ポート)(13 パターンの書き換え実測)・[port 11](../../../labs/maf-ports/ports/hn-briefing-hosted/README.md)(新基盤 hosted agent)

---

## シナリオ横断で毎回効くもの

- **評価ハーネスを先に作る。**S-01 / S-07 / S-11 の「載せ替え・移行の合否」は同一データセットでの比較で判定する。「選定は指標で、検証は評価で」(architecture 11 §7)。※2026-10-14: 評価ハーネスの SDK の版はワークフローごとに割れている(トレース評価は Learn が `azure-ai-projects==2.7.0` に固定、traces→dataset・合成データセットは 2.8.0 以上、Simulation seed は 2.8.0 では作れない)。Quality Grader は実行できなくなり、turn 専用評価器を conversation レベルで使ったときの扱いは公式間で食い違う(P-O22〜O25)。CI ゲートは「期待した評価器の結果がそろっていること」まで検査する
- **RBAC 伝播(P-I02)と「読めるのに実行できない」(P-I01)** は全シナリオの初期障害の定番。CI/CD に伝播待ちを入れる
- **記事の日付を見る。**hosted agent は 2026-04 以前の記事が旧基盤前提(P-H15)。features / architecture の「最終更新」と突き合わせる
- **プレビュー不使用ポリシーは「サービス面」と「IaC の API version」を分ける**(P-C06)。一律禁止だと GA 機能が使えなくなる。※2026-09-26: capabilityHosts は安定版 API があるため当初の根拠例は成り立たない(P-C06 訂正)が、「サービスは GA でも SDK 面が beta 名前空間」(Routines の `client.beta.routines`、P-A11)のような食い違いは残るので、原則自体は有効
- **公式ページ間の食い違いは日付つきで両論併記し、採用前に実測する。**※2026-10-06 時点の例: hosted agent の版間カナリア(新しい本番昇格ページには手順あり / 概念・構成ページは非対応、P-H06)、既存セッションの版(公式と Port 11 は作成時の版に束縛 / probe 10 は休止明けに現行版 — 同日の 2 構成で割れた、P-H25)、トレース本文の専用テーブル(公式は 2026-09-30 以降は専用テーブルのみ / 実測は二重書き、P-O13)、Agent 365 へのエクスポート(設定ページは自動 / 概念ページは SDK の明示構成が必要、P-H27)、Browser Automation(ページは preview / `azure-ai-projects` 2.8.0 は GA のツール型)。※2026-10-14 時点で増えた例: hosted agent の idle timeout の上限(REST 仕様・azd = 240 分 / Learn = 60 分、P-H13)、turn 専用評価器を conversation レベルで使ったとき(スキップ / エラー、P-O25)、Browser Automation(ツールページ本文が GA を表明 / 移行表・TOC は preview、P-A17)、Learn の機能ページから「(preview)」が外れたのに GA 一覧表は Preview のまま(Rubric 評価器・traces→dataset・合成データセット・会話評価とシミュレーション・Agent optimizer — SDK = GA / Learn = ラベルなし / GA 一覧表 = Preview の 3 者併記)、既定ストリーミングの検査(同じページに「返す前に検査済み」と「末尾は適用前に返りうる」、P-G12)
- **観測の配線は 3 行目(サンプリング)まで。受入試験は「最終状態」で判定する。**※2026-10-06 ラボ還元: azure-monitor-opentelemetry 1.8.x の既定サンプラー(5 スパン / 秒)でトレースが歯抜けになる(P-O16)。`az monitor app-insights query` は既定で直近 1 時間しか見ない(P-O17)。評価は提出が通っても run が `failed` になる・継続評価のランが並んでも全件 `failed` になる・検索が失敗しても空のレポートが正常終了する(P-O19・O21・F19)— 「動いた」ではなく結果の状態と中身で判定する。※2026-10-14: `azure-ai-agentserver-responses` 2.3.0 でテレメトリ送出の既定が background になり、要求の完了時点でトレースが届いている保証がなくなった(P-H20)ので、受入試験のトレース確認は取り込み遅延を見込んで行う
