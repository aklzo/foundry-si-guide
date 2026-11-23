# 01. 要件ヒアリングシート(質問 → 構成への分岐)

[← 提案実務ガイド TOP](./README.md)

> **最終更新:** 2026-07-31 / 2026-09-04(casebook への導線・閉域範囲の確認を追加)/ 2026-09-26(Routines GA・同時セッション上限・閉域ツール表・Data Zone APAC・廃止到来を一次情報で同期) / 2026-09-30(4-7 会話の中身をログに残すかを追加)/ 2026-10-06(4-7 に保護テーブル案〈2026-10-06 実測の二重書きと両論。同日のラボ還元で成立条件を 4 点に〉と Agent 365 への送信、4-8 利用者委任の方式、6-5 本番リリースと IaC を追加。1-3 のカナリア、0-2・5-3・7-3、クイックマップの音声行を更新) / 2026-10-10(Phase 0.5「どこで作るか」5 問を追加: 利用者・件数と 1 件あたりの処理・システム改修か・M365 Copilot の保有割合・閉域 / 国内処理の明文化。判定のしかた、Copilot Studio 案件での使い方、クイックマップ 3 行、アウトプット 0 を追加) / 2026-10-14(7-3 の期限〈On Your Data は本日、gpt-4.1-nano は 2027-04-14 に再延長、Grok の最低 6 か月・Fireworks の表外の期限・TTS アバター〉、4-8 に委任された利用者どうしの分離、5-1 に M365 公開の従量課金とゲスト不可、5-3 に Browser Automation のページ本文の GA 表明、クイックマップの音声行〈処理スコープ・テレフォニーの voice agents 誘導〉) / 2026-11-22(1-5 評価の正解と注釈の担い手・6-6 実行基盤〈prompt agent の既定ランタイム / Copilot harness / hosted / 自社 AKS〉・7-4 コストの閲覧権限と予算の止め方を追加。3-1 の同時セッション〈shared subnet IPs の GA〉、4-1 の閉域〈egress controls GA・Azure Policy の統制は日本リージョンなし・TLS 検査と Entra・PE の予約範囲・閉域で voice の電話不可〉、4-3 の Web search の経路、5-1 の Bot Service 不要、5-2 の OpenAPI と MCP、5-3 の Browser Automation、2-5 の評価の所在、7-2・7-3、クイックマップの音声・閉域行を更新)
> 初回〜2回目のヒアリング(60〜90分)を想定。各質問に「なぜ聞くか」と「回答が構成に与える影響」を付けてある。**回答をこのシートに沿って埋めると、[architecture のユースケース型](../architecture/README.md)のどれかに落ちる**ように設計している。

## 使い方

- Phase 0〜7 を順に聞く。全部で 40 問前後だが、Phase 1 の回答で無関係な Phase は飛ばせる。
- **Phase 0.5(どこで作るか)は、Foundry を使うと決まる前の案件だけで聞く。**Copilot Studio と Foundry のどちらで作るか、そもそも既存システムへの組み込みにするかをここで決める。
- **太字の質問は「聞き漏らすと提案後に手戻りが発生する」地雷質問**。時間がなければ太字だけでも埋める。
- 末尾の「回答 → 構成クイックマップ」で構成候補とリスク一覧に変換する。

## Phase 0: 前提確認(5分)

| # | 質問 | なぜ聞くか | 回答 → 構成への影響 |
| --- | --- | --- | --- |
| 0-1 | **既存の Azure 利用はあるか。あるならサブスクリプション/Landing Zone の管理体制は?** | Foundry リソースを既存ガバナンス(Policy / RBAC / ネットワーク)に載せるか、新規に作るかが変わる | 既存 LZ あり → CAF 準拠で application landing zone へ配置([architecture 01](../architecture/01-official-baselines.md))。なし → 基盤構築から見積もりに含める |
| 0-2 | **Microsoft 365 / M365 Copilot の利用状況は?**(ライセンス種別まで) | SharePoint ツールは M365 Copilot ライセンス or Retrieval API 従量課金が必要。Work IQ API は Copilot Credits 従量(コネクタ経由の M365 ツールのみユーザーごとのライセンスが要る場合あり)。Teams/M365 公開の可否も決まる | Copilot あり → SharePoint/Work IQ 経路が最短。なし → Retrieval API 従量課金の費用を見込むか、AI Search 経由の RAG に倒す(※2026-10-06: Foundry IQ の remote SharePoint ソースを従量課金〈preview〉で使う場合も、テナントに最低 1 つの Copilot ライセンスが有効化の前から利用中ずっと必要) |
| 0-3 | 既存の AI 利用(Azure OpenAI 直、他社 LLM、Copilot Studio 等)はあるか | 移行・共存の設計が要る。AOAI リソースは Foundry リソースへ非破壊アップグレード可 | AOAI あり → アップグレードパス([features 01](../features/01-platform-projects.md))。Copilot Studio あり → 接続はプレビュー |

## Phase 0.5: どこで作るか — Copilot Studio / Foundry / 既存システムへの組み込み(10分)(2026-10-10 追加)

Foundry を使うと決まる前の案件(Copilot Studio に関心がある顧客、業務課題の相談から入った案件)で、**作る場所を先に決める**ための 5 問。業務の中身(1-1)を聞きながら埋めてよい。Foundry を使うことが決まっている案件では飛ばす。

| # | 質問 | なぜ聞くか | 回答 → 構成への影響 |
| --- | --- | --- | --- |
| 0.5-1 | **利用者は誰か。社員か、社外のお客様か。普段 Teams や M365 Copilot でチャットを使う人か** | Copilot Studio の強み(M365 のチャネル、業務部門が自分で保守できること、M365 Copilot 利用者の社内向け利用は課金なし)が効くのは「チャットを使う社員」のときだけ | 社員かつチャットを使う → Copilot Studio が第一候補。チャットを使わない現場(製造・物流・店舗・介護など)→ 画面を増やさず、既存システム・電話・LINE・紙の後ろに AI を組み込む([S-07](../casebook/01-scenario-playbook.md#s-07-既存システムへの-ai-機能追加-既存-aoai-資産の活用) / [S-09](../casebook/01-scenario-playbook.md#s-09-文書・動画処理-idp))。社外のお客様 → 窓口への組み込みの受託開発([S-05](../casebook/01-scenario-playbook.md#s-05-顧客向け公開チャット)) |
| 0.5-2 | **月間の件数と、1 件あたりに起きる処理(ツール呼び出しの回数・文書のページ数・推論の有無)は** | Copilot Studio はイベント課金(アクション 5・文書 8 / ページ・推論は premium の per-token など)、Foundry はトークン課金。「件数 × 1 件あたりの差」が Foundry の固定費と運用工数を超えるかで、安い方が入れ替わる | 件数が少ない会話中心 → Copilot Studio。件数の多い自律処理・ページ処理・推論の多用 → Foundry 側も試算して比べる([02 Step 6](./02-cost-estimation.md#step-6-copilot-studio-copilot-credits-と比べるとき-2026-10-10-追加)) |
| 0.5-3 | 既存の業務システムをコードで改修する案件か(SI が開発・保守を持つか)。それとも業務部門が自分で作って育てるか | AI の部分を同じコードベース・IaC・CI/CD に入れられるか。Copilot Studio で作ると、1 つのシステムの中にローコードとコードの 2 つの開発・運用方式が混ざる | システム改修 → AI を部品として組み込む(Foundry のモデル+評価・監視。必要なら Agent Service)。業務部門が育てる → Copilot Studio |
| 0.5-4 | M365 Copilot のライセンスを、想定する利用者の何割が持っているか(0-2 を利用者の範囲まで具体化) | 保有者が本人の ID で使う社内向けの利用は Copilot Studio の課金がかからない(公正利用の範囲。computer use は対象外)。この場合 Foundry はコストで勝てない | 大半が保有 → 社員向けは Copilot Studio。未保有が多い → 0.5-2 の試算で比べる |
| 0.5-5 | **閉域(インターネット非経由)や推論の国内処理が、社内規定などの要件として明文化されているか** | 接続元の IP や端末の制限だけなら、Copilot Studio でも Entra の条件付きアクセスで満たせる。通信経路を閉じられるのは Foundry だけ。推論の国内処理は Copilot Studio の公式記載が食い違っていて未確定、Foundry は従量なら旧世代モデルのみ(新しいモデルは Regional PTU) | 明文化あり → Foundry(Phase 4 の 4-1・Phase 2 の 2-5 へ。[architecture 11 §2](../architecture/11-decision-frameworks.md#copilot-studio-の上限ライン-一次情報で確認できたもの)・[03 §2](./03-japan-compliance.md#2-データ所在-全規制共通の土台))。「社外や私物端末から使わせない」程度 → Copilot Studio + 条件付きアクセスで足りる |

**判定のしかた:** 5 問がすべて Copilot Studio 側なら、Foundry の SI は提案しない(Copilot Studio の案件として進め、Foundry IQ や BYO モデルを部品として使うかだけ検討する)。1 つでも Foundry 側に当たれば、Foundry を使う理由を**業務オーナーや情報システム部門が合意できる要件の文**で 1 行書けるか確かめる(例:「月 5 万件の受注処理を 1 件 X 円以下で」「現場は今の端末のまま使う」)。書けない理由(「コードの方が自由度が高い」など)しかないなら開発者都合の選定なので、Copilot Studio に戻す。Copilot Studio の利用が進んだ後に限界やコストの壁に当たった場合は [S-08](../casebook/01-scenario-playbook.md#s-08-copilot-studio-で始めた業務部門から-限界-と言われた)(二層構成)。

**Copilot Studio の案件の中での使い方:** Copilot Studio の導入や作成支援の場でもこの 5 問を聞き、Foundry 側に当たった要望(件数の多い処理・画面のない業務・社外向けの窓口・既存システムの改修・閉域)は「対象外」として捨てずに記録しておく。この記録がそのまま Foundry の SI の案件候補になる。

## Phase 1: 業務・目的(10分)

| # | 質問 | なぜ聞くか | 回答 → 構成への影響 |
| --- | --- | --- | --- |
| 1-1 | **解決したい業務課題は何か。「誰が・何を・どれくらいの頻度で」やる業務か** | ユースケース型の判定が全ての起点 | 下の型判定表へ |
| 1-2 | 人間が最終確認するか、AI の出力がそのまま業務に流れるか(HITL の有無) | ガードレール・Task adherence・評価の要件レベルが変わる | 自動実行 → エージェント向けガードレール(プレビュー)依存のリスク説明が必須 |
| 1-3 | 失敗時の業務影響は?(誤答が金銭・法的リスクになるか) | 評価・観測性・段階リリースへの投資水準を決める | 高リスク → 評価 CI/CD ゲート + 継続的評価(プレビュー)+ 段階リリース。**エージェントのバージョン間トラフィック分割は prompt / hosted とも非対応**(FixedRatio は 1 バージョン 100% のみ。configure-agent 2026-09-11 版)→ カナリアは別エージェント名で検証 → 切替、または前段(APIM 等)で振り分け。※2026-10-06: 新しい本番昇格ページ(deploy-hosted-agent-production、preview 表記)は azd で版間カナリア(90 / 10 → 100)の手順を載せたが、概念・構成ページは「非対応」のまま — 公式間で食い違い、未実測([casebook P-H06](../casebook/02-pitfalls-index.md#a-hosted-agent))。前提にするなら PoC で実測する。本番リリースの手順は 6-5 |
| 1-4 | 成功指標は何か(工数削減率、応答時間、解決率など) | PoC の合否基準と評価器の選定に直結 | 指標 → [評価器マッピング](../features/05-observability-evaluation.md) |
| 1-5 | **「正しい回答」を誰が決めるか。評価用の正解(golden dataset)を誰が作って承認し、本番の会話に誰が 👍 / 👎・期待する答えの注釈を付けるか**(2026-11-22 追加) | Foundry の Human in the loop(preview)は「トレースに注釈 → 評価データセット(行ごとの採点基準を自動生成)→ golden dataset」の流れを持つが、注釈を付ける人と golden を承認する人がいないと回らない。注釈の書き込みは閲覧と別の権限、ルーブリックは最大 20 次元 | 業務側に正解を決める担当がいる → 注釈と golden の承認を運用体制に入れ、書き込み権限(App Insights への書き込み)を設計する([casebook P-O26・O31](../casebook/02-pitfalls-index.md#g-観測と評価))。いない → PoC の成果物に「SI が作る正解セット 20〜30 件+業務側のレビュー」を入れ、継続評価は自動の評価器だけで始める。外部エージェント(LangGraph 等)は人手評価の対象にできない(P-O30)。Japan West では HITL のデータセット化に使う data generation の対応が要確認 |

**ユースケース型判定**(1-1 の回答から):

| 回答の特徴 | 型 | 参照章 |
| --- | --- | --- |
| 社内文書を検索して答えてほしい | 社内 RAG / チャット | [architecture 04](../architecture/04-usecase-chat-rag.md) |
| 定型業務を自動でやってほしい(申請処理、レポート作成等) | 業務自動化エージェント | [architecture 05](../architecture/05-usecase-agent-automation.md) |
| 顧客・会員向けに公開したい | 顧客接点(外部公開) | [architecture 06](../architecture/06-usecase-customer-facing.md) |
| 規制業種 / 閉域必須 / オンプレ・エッジ | 規制・エッジ | [architecture 07](../architecture/07-usecase-regulated-edge.md) |
| 音声・文書処理・画像生成・FT が主目的 | 特化ユースケース | [architecture 08](../architecture/08-usecase-specialized.md) |

## Phase 2: データ(15分)

| # | 質問 | なぜ聞くか | 回答 → 構成への影響 |
| --- | --- | --- | --- |
| 2-1 | **根拠にしたいデータはどこにあるか**(SharePoint / ファイルサーバー / DB / Fabric / SaaS / 紙) | RAG の取り込み経路とツール選定が決まる | SharePoint → SharePoint ツール(プレビュー・Copilot ライセンス要件)or AI Search インデクサ。DB/Fabric → Fabric data agent(プレビュー)or NL2SQL 自前。紙 → Content Understanding / DI の前処理をスコープに追加 |
| 2-2 | **データ量と更新頻度は?**(GB・件数、日次/週次/リアルタイム) | File Search(手軽・制御弱)か AI Search(制御強)か Foundry IQ かの分岐。インデックス更新設計の工数 | 小規模・静的 → File Search。大規模・要チューニング → AI Search。マルチソース・複数エージェント共有 → Foundry IQ(一部 GA、ポータルはプレビュー) |
| 2-3 | **データの機密区分は?(社外秘 / 個人情報 / 要配慮個人情報の有無)** | 閉域要否・ガードレール PII(プレビュー)・Purview 連携・[03 規制メモ](./03-japan-compliance.md)の適用範囲 | 個人情報あり → 個情法整理(委託構成)+ abuse monitoring の説明を準備 |
| 2-4 | ユーザーごとに見せてよいデータが違うか(アクセス制御の粒度) | セキュリティトリミングは RAG 設計の難所 | ユーザー別 → OBO 系ツール(SharePoint/Fabric、サービスプリンシパル不可)か、AI Search のセキュリティフィルタ自前実装。**全員同じ → 大幅に簡単になる**ので必ず確認 |
| 2-5 | データを国外に出せるか(処理・保存それぞれ) | デプロイタイプと機能制約が決まる | 国内限定 → **Standard / Regional Provisioned(geography 型。Japan East / Japan West)のみ**(Data Zone APAC は「APAC 域内のいずれかの国」で処理 — 現行の対象リージョンは豪・日・韓・星・印で、予告なく追加されうる)。Data Zone / Regional は Global 比の価格プレミアムあり([02 コスト手順](./02-cost-estimation.md))。安全性評価・Red Teaming・Task adherence は国外処理あり → 除外 or 合意。※2026-11-22: 新しい safety rubric 評価器(preview)も Americas / Europe のみで日本なし、Insights(GA)は Japan East / West 可。「APAC 域内でよい」なら GPT-6 世代は 6.1-sol / 6.1-terra / 6.2-astra / 6.2-sol の Data Zone Standard(APAC)が選べるようになった。managed compute(GA)は Data Zone が US / EU のみで、日本は Global のみ([03 §2](./03-japan-compliance.md#2-データ所在-全規制共通の土台)) |

## Phase 3: ユーザー・規模・SLA(10分)

| # | 質問 | なぜ聞くか | 回答 → 構成への影響 |
| --- | --- | --- | --- |
| 3-1 | **利用者は誰で何人か。ピーク同時利用は?** | クォータ・PTU 判断・hosted agent のセッション上限に直結 | hosted agent の同時セッションは 2 段の上限: ①**サブスクリプション×リージョンの既定クォータ 2,000(Japan East 等 7 リージョン)/ 1,000(その他)**(申請で引き上げ可)、② VNet 注入時は**委任サブネットの使用可能 IP**(既定 1 セッション = 1 IP。/26 で約 50・/27 で約 17、申請で 1 IP あたり 10 セッションまで)。本番は /24 起点。大規模 → prompt agent 中心(IP を消費しない)or クォータ引き上げ / サブスクリプション分割。※2026-11-22: **② は実質外れた** — shared subnet IPs が GA(2026-11-18)になり、セッションは IP を共有する(計画上 /27 = 7,500・/24 = 60,000 セッション)。上限は ① のクォータで決まり、サブネットを広げても増えない。本番 /24 以上の推奨は不変([casebook P-N05](../casebook/02-pitfalls-index.md#d-ネットワークと閉域)) |
| 3-2 | 応答時間の要求は?(対話的 / 数秒待てる / バッチで良い) | モデル選定・デプロイタイプ・キャッシュ設計 | バッチ可 → Batch(50%引き・24h ターゲット・SLA なし)。対話 + 安定 → PTU 検討 |
| 3-3 | **可用性・SLA の要求水準は?** | プレビュー機能は SLA なし。マルチリージョン DR は「再構築」戦略が基本 | 高 SLA → プレビュー機能を構成から排除([features の GA 一覧](../features/README.md))+ spillover / model router でフェイルオーバー |
| 3-4 | 利用の波は?(営業時間集中 / 平準 / 月次ピーク) | PTU の損益分岐と spillover 構成 | ピーク型 → PTU + Standard spillover のハイブリッド([02 コスト手順](./02-cost-estimation.md)) |

## Phase 4: セキュリティ・規制(15分)

| # | 質問 | なぜ聞くか | 回答 → 構成への影響 |
| --- | --- | --- | --- |
| 4-1 | **閉域(インターネット非経由)が必須か。それは要件か希望か** | BYO VNet 注入は**作成後の変更不可**。最初に決めないと作り直しになる | 必須 → [architecture 07](../architecture/07-usecase-regulated-edge.md) の「使えない機能一覧」から設計を始める(Browser Automation / Computer Use / Image Generation / Logic Apps / Fabric data agent 等が非対応。File Search は公式表で 2026-08-14 版から「Supported(private endpoint 経由)」に変わった)。**「閉鎖」の範囲(インバウンド遮断のみか、egress まで統制し外部 SaaS・パッケージ取得も禁止か)も同時に確定**する — CI/CD・搬入・監視の設計と見積もりが別物になる。※2026-11-22: hosted agent の **egress controls は GA**(Transform ルールを除く)になったが、secret 参照ヘッダーと **Azure Policy による egress・エージェント種別・ツールの統制は preview で Canada Central / Spain Central / Korea Central のみ**(日本リージョンで「ポリシーで強制する」設計はまだ組めない — P-N25)。顧客の FW が **TLS 検査**をするなら Entra / マネージド ID の 3 FQDN を検査から除外する合意が要る(private CA trust〈preview〉では解決しない — P-N23)。既存のアドレス計画に `192.168.0.0/24` の PE があれば移設が要る(P-N24)。ネットワーク構成は最初の hosted agent の作成時に確定する。**閉域プロジェクトでは voice agents の電話チャネル(Teams Phone / Twilio / SIP)と発信が使えない**(P-D12)ので、電話窓口の要件があれば同時に確認する |
| 4-2 | 業種の規制・ガイドラインは?(FISC / 3省2 / ISMAP / 社内基準) | [03 規制メモ](./03-japan-compliance.md)の該当節を適用 | 政府 → ISMAP 登録状況の確認が先決。金融 → FISC 対応整理 + 閉域 |
| 4-3 | **Web 検索・外部サービス呼び出しを許容するか** | Web search / Bing 系は **DPA 対象外・地理境界外送信・別課金** | 不許容 → Web グラウンディング機能を全て外す(サブスクリプション単位で無効化も可)。※2026-11-22: web search は **prompt agent への直付け = Web IQ / toolbox 経由 = Grounding with Bing** に分かれ、DPA 非適用・地理境界外への転送の明記は Bing 側の注記。許容する場合も「どの経路で使うか」まで合意する([casebook P-R18](../casebook/02-pitfalls-index.md#e-rag-とナレッジ)) |
| 4-4 | 認証は?(Entra ID / 外部 IdP / 匿名) | Agents は Entra ID 必須(API キー不可)。顧客向けは別途 IdP 統合 | 外部 IdP → フロント側で変換。B2C 相当の設計を工数に |
| 4-5 | 監査要件は?(誰が何を聞いたかの記録・保持年限) | トレース(ポータル90日)+ App Insights 保持設計 + Purview | 長期保持 → App Insights/Log Analytics のエクスポート設計と課金を見積もりへ |
| 4-6 | CMK(顧客管理キー)要件はあるか | CMK は一部リージョンのみ・CMK→MMK 不可逆 | 要件あり → リージョン可否を先に確認 |
| 4-7 | **エージェントの会話の中身(利用者の入力・回答・参照した社内文書)を運用ログに残してよいか。残すなら誰が読めるか(Microsoft Agent 365 など Foundry の外の管理面への送信を含む)** | hosted agent は App Insights を接続すると、プラットフォーム側で会話の中身(ツール結果を含む)まで記録し、コンテナ側の設定では止められない(2026-09-30 実測)。利用者の権限で絞った文書も、トレースの閲覧者には全部見える。※2026-10-06: 本文だけを専用テーブルに分けて保護する公式の仕組み(preview)と、Agent 365 への活動データの送信(Agent 365 が有効なテナントでは既定で有効)が選択肢・論点に加わった | 残せない → App Insights を接続せず、コンテナのログだけを運用向けに送る / 残すが閲覧者を分けたい → App Insights を 2 つに分ける / 運用担当が読んでよい → 既定の 1 つに集約。判断基準と得失は [architecture 09 §3.6](../architecture/09-operations.md#3-6-トレースに会話の中身を残すか-hosted-agent-の選定基準)。4-5 の監査要件(何を・何年残すか)と矛盾しないかも同時に確認する。**※2026-10-06: 第 4 の選択肢 —「同じ App Insights のまま本文だけ保護テーブルに隔離」**(本文属性を専用テーブル `AppGenAIContent` に振り分け、Protected にして Privileged Monitoring Data Reader の保持者だけが読む。運用担当はメタデータだけ見る)。**① 早期有効化フラグの登録か移行の完了 ② テーブルの Protected 化 ③ ロール付与 ④ `gen_ai.*` 以外の場所に本文を書く計装(MAF のメッセージイベント・自前のログ)を止める の 4 点がそろって初めて成立**する(④は 2026-10-06 のラボ還元で追加 — 振り分けの対象は `gen_ai.*` の属性名だけで、MAF のメッセージイベントは `AppTraces` に残る = [casebook P-O18](../casebook/02-pitfalls-index.md#g-観測と評価))。公式は移行日 2026-09-30 以降の新規取り込みを既定で専用テーブルのみとしているが、**2026-10-06 の japaneast 実測(フラグ未登録)では本文が従来テーブルにも残る二重書きで、通常の Log Analytics Reader で読めた** → この案を選ぶなら「従来テーブル(AppDependencies / AppTraces)に本文が残っていないことを KQL で確かめる」工程(`az monitor app-insights query` は既定で直近 1 時間しか見ないので期間を明示 — casebook P-O17)と、フラグ登録(サブスクリプション全体の設定変更)の合意を見積もりに入れる([casebook P-O13・O14](../casebook/02-pitfalls-index.md#g-観測と評価))。トレース評価・継続評価を使うなら、評価を回すプロジェクト MI にも同じロールが要る。**Agent 365 を使うテナント**では、Foundry リソースのエージェント活動データ(公式ホスティングライブラリを使う hosted agent のトレースを含む)が既定で Agent 365 に送られ、保存場所は Foundry のリージョンではなく **Entra テナントのジオ** → 送らないならリソース単位で `a365LoggingEnabled=false`(閉域では FW の拒否ログ対策にもなる、[casebook P-H27](../casebook/02-pitfalls-index.md#a-hosted-agent)) |
| 4-8 | **エージェントが利用者本人の権限で社内システム・SaaS を呼ぶ必要があるか。あるなら、利用者と Foundry は同じ Entra テナントか、どの画面・チャネルから使うか**(2026-10-06 追加) | 利用者ごとに見えるデータ・できる操作が違うなら「誰の権限で呼ぶか」が構成を決める。2026-09-28〜29 の公式更新で、hosted agent からの利用者委任は **toolbox 経由が公式推奨**になった(MAF は `FoundryToolbox` / `AddFoundryToolboxes`) | 対応ツール・OAuth 準拠の SaaS・同一テナント → **toolbox 委任**(OAuth identity passthrough。利用者に Foundry Agent Consumer 以上が要り、クロステナント不可)/ 自社 API で判定と監査を自前で持ちたい・利用者に Foundry のロールを配りたくない → **アプリ管理 OBO**(中間層が委任トークンを `x-client-*` で渡す。比較は [port 15](../../../labs/maf-ports/ports/delegated-access-hosted/README.md#マネージドな代替-toolbox-の-oauth-id-パススルー))/ 利用者の権限が不要 → エージェント自身の ID。どの方式でも**権限の違う 2 人で出し分けを確かめる受入試験**を見積もりに入れる(401 / 403 が出ないまま別の利用者の権限で動く失敗がある — [casebook P-H26](../casebook/02-pitfalls-index.md#a-hosted-agent))。Teams 公開からの委任は不可([P-X11](../casebook/02-pitfalls-index.md#k-copilot-studio-m365-apim-業務連携))、利用者のテナントが違う SaaS 型は 2-4 とあわせて別方式を検討。※2026-10-14: 中間層が `x-ms-user-identity` で利用者を委任する方式では、**委任された利用者どうしはプラットフォームが隔てない**(どの利用者をどのセッションに入れるかはアプリの責任。セッションを共有する設計ではコンテナ側の保存データも自分で分ける)と公式に明文化された — 受入試験の「2 人で出し分け」に「同じセッションに入れたときの保存データ」も含める([casebook P-H30](../casebook/02-pitfalls-index.md#a-hosted-agent)) |

## Phase 5: 既存資産・統合先(10分)

| # | 質問 | なぜ聞くか | 回答 → 構成への影響 |
| --- | --- | --- | --- |
| 5-1 | 出力先はどこか(Teams / 既存 Web / 新規 UI / API / M365 Copilot) | チャネル構成が決まる | Teams/M365 → 公開フロー GA(Bot Service 必要。※2026-11-22: **別途の Azure Bot Service リソースは不要**になった — publish-copilot 2026-11-12 版、REST は `performBotRegistration: true`。[casebook P-X07](../casebook/02-pitfalls-index.md#k-copilot-studio-m365-apim-業務連携))。既存 Web → フロント実装 + WAF([architecture 06](../architecture/06-usecase-customer-facing.md))。※2026-10-14: Teams / M365 に公開したエージェントは、Microsoft 365 Copilot ライセンスのない利用者も Copilot Chat で使えるが、SharePoint や Copilot コネクタなどの共有テナントデータにアクセスする利用は**従量課金になりうる**(公式のトラブル表の注記)。ゲストユーザーは呼び出せない(プロジェクトのテナント一致が必要)。閉域(PNA 無効)で公開する場合も受信は公衆インターネット経由になる([casebook P-X08 / P-N12](../casebook/02-pitfalls-index.md#k-copilot-studio-m365-apim-業務連携)) |
| 5-2 | 呼び出したい既存システム・API はあるか(認証方式も) | ツール選定: OpenAPI ツール(GA)/ Functions(standard のみ。新 Agent Service での可否は公式間で記載が矛盾 → 要確認、[features 04](../features/04-tools-knowledge.md))/ MCP(GA)/ A2A(`a2a` 型は 2026-09 GA)/ Logic Apps コネクタ(プレビュー) | OAuth2 必須の SaaS → Logic Apps コネクタは OAuth2 非対応(プレビュー)に注意。※2026-11-22: **OpenAPI ツールも OAuth の identity passthrough に非対応**(toolbox に入れても不可)と明記されたので、利用者本人の権限で呼ぶ API は MCP サーバーにする(P-X25)。APIM / AI Gateway 経由の MCP は Foundry による自動登録が廃止され、ゲートウェイ側でルートを作って URL を入れる(P-X26) |
| 5-3 | RPA・既存自動化(Power Automate 等)との棲み分けは? | エージェント化する範囲の合意 | 画面操作が必要 → Browser Automation / Computer Use は**プレビュー+リスク警告あり**。本番は避けるか限定。※2026-10-06: Browser Automation は Learn のページは preview のまま(リージョン表に Japan East が載った)だが、`azure-ai-projects` 2.8.0 は GA のツール型を追加 — ステータスは両論で扱う。※2026-10-14: ツールページ本文が「generally available」と明記し h1 の「(preview)」も外れたが、移行ガイドの対応表は「Public Preview」・TOC は「(preview)」のままで両論は続く。閉域は GA 表明後も非対応(Under development)なので、閉域案件の画面操作の自動化には使えない([casebook P-A17](../casebook/02-pitfalls-index.md#b-agent-service-コア))。※2026-11-22: devblogs(10-19・11-18)は GA を明言し、セッション録画・Live View などが GA に。閉域は configure-private-link の表が「Supported」に変わった一方 toolbox-network-isolation は「Not supported」で割れており、引き続き閉域案件には入れない。**prompt agent に Key Vault の資格情報を渡すとモデルが値を参照できる**と概要ページにあるので、ログインを伴う画面操作は hosted / コード側で資格情報を隠す |

## Phase 6: 運用体制・スキル(10分)

| # | 質問 | なぜ聞くか | 回答 → 構成への影響 |
| --- | --- | --- | --- |
| 6-1 | **引き渡し後、誰が運用するか(顧客内製 / SI 運用委託 / ハイブリッド)** | 構成の複雑度上限が決まる | 顧客内製・非開発者 → ポータル中心(prompt agents)。開発チームあり → MAF / hosted agents も選択肢 |
| 6-2 | 顧客側の開発スキルは?(Python/.NET、Azure 経験) | portal vs MAF vs LangGraph の分岐([learning-plan](../../learning-plan.md) の選定軸) | LangChain 資産あり → LangGraph を hosted agent として持ち込む案 |
| 6-3 | プロンプト・ナレッジの更新は誰がやるか | 運用設計(バージョニング・評価ゲート)の工数 | 業務部門更新 → ポータルのバージョン管理 + 評価の自動ゲートを提案 |
| 6-4 | モデル更新(リタイア強制移行)への追従体制は? | GA モデルは約18か月でリタイア。**運用契約に「モデル移行対応」を含めるか**は契約論点 | 含める → 定期評価の再実行を運用メニュー化 |
| 6-5 | **エージェントの新しい版を本番に出すのは誰が・どの手順で承認するか。IaC のツール指定(Bicep / Terraform)はあるか**(2026-10-06 追加) | hosted agent の既定ルーティングは latest 追従で、版を作るとそのまま本番(Teams / M365 の公開先を含む)に出る。公式は 2026-09 に「本番を版にピン留め → 候補を専用セッションで検証 → 切り替え」の手順と、Terraform での管理方法を出した | 承認ゲートあり → ピン留めと候補検証の手順を runbook・CI に入れ、本番に書き込むツールを 1 つに決める([casebook P-H28](../casebook/02-pitfalls-index.md#a-hosted-agent))。Terraform 指定 → azd の `--infra=terraform`(インフラだけ。版は `azd deploy`)か、AzAPI で版まで管理するかを決める。**閉域(PE・注入サブネット)は eject 非対応**なので、Bicep か自前の AzAPI で書く工数を見積もる([P-C13](../casebook/02-pitfalls-index.md#j-iac-cli-ci-cd))。版間の % 分割(カナリア)は公式間で記載が割れている(1-3) |
| 6-6 | **エージェントをどの実行基盤で動かすか — prompt agent(既定のランタイム / Microsoft Copilot harness)/ hosted agent(Microsoft 管理のサンドボックス)/ 顧客の AKS** (2026-11-22 追加) | 2026-11 に選択肢が増えた。**Copilot harness**(preview)は prompt agent のまま、Microsoft 運用のエージェントループとサンドボックスでファイル処理・シェル・サブエージェント・skills を使える(作成時のみ選択、Japan West・East US 2 不可、BYOM・Memory 不可、**2026-12-01 からサンドボックスに従量課金**)。**顧客 AKS への配置(BYO-AKS)**は限定プレビュー受付中で、public preview は 12 月上旬が目標(Learn の手順は未公開) | 指示とツールだけで足りる → prompt agent(既定)。ファイル処理・コマンド実行・多段の委任を自前のコードなしで → Copilot harness(プレビューの許容と 12 月からの費用、Shell の権限設計 = [casebook P-A18・A22](../casebook/02-pitfalls-index.md#b-agent-service-コア))。依存やランタイムを自分で管理・長時間実行 → hosted agent(long-running resilience は GA)。**クラスター・ノード・ネットワークを自社で持ちたい** → BYO-AKS は現時点で提案の前提にせず、プレビューの開始を待って評価する(egress controls・private CA trust の記述はマネージドの hosted agent が対象で、AKS 側は顧客の責任) |

## Phase 7: 予算・スケジュール・リスク許容度(5分)

| # | 質問 | なぜ聞くか | 回答 → 構成への影響 |
| --- | --- | --- | --- |
| 7-1 | 予算レンジ(初期 / 月額ランニング) | 構成の足切り。閉域は固定費(Firewall / PE / APIM)が支配的になる | [02 コスト手順](./02-cost-estimation.md)で概算 |
| 7-2 | **プレビュー機能の利用を許容するか(SLA なし・仕様変更あり)** | Foundry は有用機能の多く(Memory / Foundry IQ ポータル / エージェント向けガードレール / Monitoring 等)がプレビュー(Routines は 2026-09-24 に GA。GA 一覧表で最新を確認) | 不許容 → GA のみ構成([features README の Feature readiness](../features/README.md))+ プレビュー UI 無効化(`AZML_DISABLE_PREVIEW_FEATURE` タグ)を提案に含める。※2026-11-22: Ignite 2026 で GA と発表されたものの多くは GA 一覧表では Preview のまま、または行がない(voice agents・Insights・egress controls・Agent optimizer など)。GA 一覧表で GA になったのは managed compute と外部エージェントのトレース。「GA だけ」の顧客には GA 一覧表を正として両論で説明する |
| 7-3 | PoC → 本番のスケジュール感 | 廃止日程(On Your Data 2026-10-14、Workflows 2026-12-01、Agents classic 2027-03-31 等。Assistants API は 2026-08-26 に廃止済)との衝突確認 | 期間内に廃止到来 → 最初から後継 API で作る。※2026-10-06: 直近は On Your Data と gpt-4.1-nano が 2026-10-14、gpt-4o-transcribe 系・gpt-4o-mini-tts が 10-15、o1 / o3 / o4-mini 系が 11-19、Claude 4.5 系が 11 月(10-19 から延長。リタイア表は往復改訂される)。一覧は [casebook S-11](../casebook/01-scenario-playbook.md#s-11-廃止期限駆動の移行案件)。※2026-10-14 更新: On Your Data は**本日 2026-10-14 が廃止日**(ページは未来形のまま。残っていれば即時の切り替え)。gpt-4.1-nano は 2027-04-14 に戻り(リタイア表の 3 度目の往復)、同日ではなくなった。ほかに、Grok 4.7 以降の GA モデルは「最低 6 か月提供」の別枠、Fireworks の一部モデルの Pay-per-token はリタイア表にない期限(2026-09-25)で終了済み、TTS アバターの標準アバター(Jeff の全スタイル・Lisa の 4 スタイル)が 2026 年 12 月から利用不可([casebook P-M07 / P-M18](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト))。※2026-11-22: 直近は **Workflows 廃止 2026-12-01(残り 9 日)**、Copilot harness の課金開始 12-01、claude-sonnet-4-5 11-30、MAI-Transcribe-2-Streaming 12-04、MAF(Python)の旧メモリ API の削除 2026-12-31 以降。2027 年は gpt-4o 2024-05-13 01-14(PTU・Batch は手動移行)、Microsoft-Decision-1 02-04、`az cognitiveservices agent` の削除(02-28 後の最初の CLI リリース)、Agents (classic) 03-31、gpt-4.1 系 04-14、Content Safety の preview 6 機能(Groundedness detection など)04-30、Control Plane のカスタムエージェント 05-07。**Azure Language の CLU / CQA など legacy 7 機能は 2029-03-31**(FAQ ボット系の提案に明記)。o-series の後継は Batch・Regional Standard で提供されない([casebook S-11](../casebook/01-scenario-playbook.md#s-11-廃止期限駆動の移行案件)・P-M21) |
| 7-4 | **コストを誰が見て、予算を超えたら止めるか。止めるならどこで止めるか**(2026-11-22 追加) | Foundry のコスト画面(Manage > Cost・Fleet)は **Foundry のロールでは見えない**(Cost Management Reader を RG / サブスクリプションに別付与。データは 8〜24 時間遅れ、エージェント名の内訳は 2026-11 以降の利用から)。cost controls(preview)は予算超過を HTTP 429 で止められるが、**対象は GPT / o-series だけ**で PTU・ツール料金・hosted のコンピュートは数えず、判定できなければ通す | 見る人を決めてロールを構築手順に入れる([casebook P-I16](../casebook/02-pitfalls-index.md#c-id-と-rbac))。止める要件あり → cost controls を「上限保証ではない一次の歯止め」とし、APIM / AI Gateway のトークン上限と Azure の予算アラートを併用する(P-M25・X16)。cost control を付けたプロジェクトは削除できないので、検証環境の後片付けの手順に入れる([02 コスト手順](./02-cost-estimation.md)) |

## 回答 → 構成クイックマップ

| ヒアリング結果の組み合わせ | 構成候補 | 主なリスク・確認事項 |
| --- | --- | --- |
| 社員向け・チャットで使う・M365 Copilot の保有者が多い・件数は中程度(Phase 0.5)(2026-10-10 追加) | Copilot Studio(Foundry は使わないか、Foundry IQ / BYO モデルを部品として) | 30〜40 アクション超・多段の階層・決定的ワークフローが業務クリティカル、のどれかが出たら [S-08](../casebook/01-scenario-playbook.md#s-08-copilot-studio-で始めた業務部門から-限界-と言われた) の二層構成 |
| チャットを使わない現場・既存システムの改修(Phase 0.5)(2026-10-10 追加) | 既存システムに AI を部品として組み込む(S-07 / S-09 / S-03) | Agent Service まで使うか、モデル呼び出し+評価・監視だけで済ませるか([S-07](../casebook/01-scenario-playbook.md#s-07-既存システムへの-ai-機能追加-既存-aoai-資産の活用)) |
| 件数の多い自律処理・ページ処理(Phase 0.5)(2026-10-10 追加) | 入口が Copilot Studio なら重い処理だけ Foundry へ(二層)、入口がなければ Foundry 単独 | 分岐点の試算([02 Step 6](./02-cost-estimation.md#step-6-copilot-studio-copilot-credits-と比べるとき-2026-10-10-追加))。比較は estimator と試作で測ったトークン量で |
| 社内 RAG + データは SharePoint + 内製運用弱 | prompt agent + SharePoint ツール(or AI Search)+ ポータル運用 | SharePoint ツールはプレビュー / Copilot ライセンス or 従量課金 |
| 社内 RAG + 大規模・検索品質重視 | prompt agent + AI Search(自前インデックス)、将来 Foundry IQ | ベクトルクォータはサービス作成日依存 / セキュリティトリミング自前 |
| 業務自動化 + 多段オーケストレーション | MAF(コードファースト)+ hosted agents | ビジュアル Workflows は 2026-12-01 廃止のため使わない |
| 顧客向け公開 + 大規模 | App Gateway/WAF + APIM + prompt agents + ガードレール | WAF 誤検知チューニング / 同時セッション・クォータ設計 / BOLA 対策自前 |
| 閉域必須(金融等) | BYO VNet 注入 + standard setup(BYO 3点)+ PE | **ネットワーク構成は作成時のみ**・使えないツール多数・Firewall 等の固定費。※2026-11-22: egress controls は GA だが Azure Policy での統制は日本リージョンなし、FW の TLS 検査は Entra の通信を除外、閉域では voice の電話チャネル不可([casebook P-N22〜N25](../casebook/02-pitfalls-index.md#d-ネットワークと閉域)) |
| 国内データ処理必須 | Standard / Regional Provisioned(Japan East / West)+ 評価は国外の扱いを合意 | Japan リージョンのモデル提供状況・クォータを個別確認(geography 型は新モデルの提供が最後)/ Regional 価格プレミアム |
| 音声(電話受付・リアルタイム対話)(2026-10-06 追加) | Voice Live API(GA)+ ACS。新規でプレビューを許容できるなら voice agents(preview、Teams Phone / Twilio の組込みテレフォニー) | ネイティブ音声 × 国内処理は両立しない(Japan East のリアルタイムモデルは Global standard。国内処理なら Standard のテキストモデルで cascaded か BYOM を検討)/ 接続確立の待ち時間(実測 3.7〜12.4 秒)/ プレビュー依存([casebook S-10](../casebook/01-scenario-playbook.md#s-10-音声エージェント-コンタクトセンター))。※2026-10-14: Voice Live は機能ごとに処理スコープが別で、Japan East で国内(Regional)処理になる LLM は gpt-4o と phi4-mm-realtime(preview)だけ、HD 音声・mai-transcribe-2 は Global と公式に明記された。テレフォニーのページはコールセンターを voice agents(preview)のネイティブ電話連携へ誘導する形に変わった(推奨経路がプレビュー)。※2026-11-22: voice agents は Learn・SDK・ブログで GA(GA 一覧表は Preview のまま → 両論)。**閉域プロジェクトでは電話番号チャネルと発信が非対応**。Voice Live の SIP 直結は preview で日本リージョンなし。録音ファイルの文字起こし(Fast transcription)は「リソースのリージョンまたはデータゾーン内」と明記([casebook P-D12・D13](../casebook/02-pitfalls-index.md#l-文書処理と音声)) |
| 文書処理中心 | Content Understanding(+ DI)+ Batch | CU は BYO モデル接続必須 / ページ・サイズ上限 |

**シナリオ別の判断根拠と詰まりどころ:** 上表の構成候補ごとに、ゲート判定・却下案とその理由・詰まりどころ(P-ID)・見積もりで効く点を [casebook 01 要件シナリオ別プレイブック](../casebook/01-scenario-playbook.md) に整理してある(社内 RAG = S-01、承認付き自動化 = S-03、閉域 = S-04、顧客向け = S-05、SaaS = S-06、既存組込み = S-07、Copilot Studio 引き継ぎ = S-08、文書・動画処理 = S-09、音声 = S-10、廃止期限駆動の移行 = S-11)。

## ヒアリング後のアウトプット(提案までの ToDo)

0. **作る場所の判定**(Phase 0.5 の結果)と、Copilot Studio にしない場合はその理由を要件の文で 1 行(2026-10-10 追加)
1. 構成候補 1〜2 案(architecture 該当章の構成図をベースに)
2. **プレビュー依存リスト**(機能名・現ステータス・GA 見込み不明の明記)— features から抽出
3. **廃止日程との衝突チェック**(features README の期限表)
4. 概算月額レンジ([02](./02-cost-estimation.md) の手順で)
5. 規制・契約の論点リスト([03](./03-japan-compliance.md) から該当分)
6. **詰まりどころリスト**(該当シナリオが参照する [casebook 02](../casebook/02-pitfalls-index.md) の P-ID)— 提案書のリスク欄と設計レビューのチェック項目に転記する
7. **評価とコストの体制**(1-5・7-4 の結果: 正解セットと注釈の担い手、コストを見る人のロールと予算の止め方)(2026-11-22 追加)
