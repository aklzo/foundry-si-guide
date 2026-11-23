# 04. 前提 Azure 知識マップ(Foundry 提案・設計に必要なサブセット)

[← 提案実務ガイド TOP](./README.md)

> **最終更新:** 2026-07-31 / 2026-09-26(資格表を更新: AI-102 退役 → AI-103。hosted agent の同時セッション上限、capability settings への移行中を注記)/ 2026-10-06(監視に保護テーブルと Privileged Monitoring Data Reader、ID に利用者委任の 2 方式、IaC に Terraform での hosted agent 管理を追加) / 2026-10-14(IaC に capability settings の設定ページの 301〈取り下げか移設中か要確認〉と AI Search のエンドポイントを組み立てない注意) / 2026-11-22(Azure AI Search → Foundry IQ (Azure AI Search) の改称、azd の Foundry 拡張の GA と `az cognitiveservices agent` の削除予定、サブネットの shared IP の GA・PE の予約範囲・TLS 検査と Entra、cost controls〈preview〉と Cost Management Reader、Azure Policy の新しい統制〈preview、日本リージョンなし〉、RBAC の注意 2 点、顧客 AKS への配置〈coming soon〉)
> 本リポジトリの調査ドキュメントは、いくつかの Azure 基礎知識を「知っている前提」で書かれている。**AZ-104(管理者)の全範囲は不要**で、必要なのは特定のサブセット+設計寄り(AZ-305)の観点。このマップは「どの知識が・どの設計判断で・なぜ要るか」を整理し、チームのオンボーディングとスキルギャップ確認に使う。

## 結論サマリー

- **最優先はネットワークと Entra ID。**閉域案件・ツール認証(OBO)はこの2つが分からないと設計も顧客説明もできない。
- **VM・ストレージ運用(AZ-104 の中核)はほぼ不要。**Foundry のマネージド路線ではコンピュートを直接運用しない。効くのはフロント(App Service)と self-host 比較(ACA/AKS)の場面のみ。
- 意外に効くのが**監視のコスト構造**(App Insights 取り込み課金)と **AI Search の SKU 設計**。月額を左右するのはトークン単価よりこの2つという案件も多い。

## 領域別マップ

必要度: 高 = これがないと提案・設計が成立しない / 中 = 特定の要件で必須になる / 低 = 特定構成のみ

### ネットワーク(必要度: 高)

| トピック | どの設計判断で使うか | 本リポジトリの該当箇所 |
| --- | --- | --- |
| VNet / サブネット / サブネット委任 | BYO VNet 注入(`Microsoft.App/environments` 委任、/27 以上・本番は /24 起点〈/27 は本番非推奨と明記〉、**作成後変更不可**)のサイジングと IP 設計。hosted agent は既定 1 セッション = 1 IP なので同時セッション数から逆算。アドレス空間は RFC1918 を推奨(RFC 6598 の可否は公式ページ間で揺れ)。※2026-11-22: **shared subnet IPs が GA** になり、セッションは IP を共有する(計画上 /24 = 60,000 セッション)— 逆算の対象はサブスクリプション × リージョンの同時セッションクォータに変わった。新たに **PE を `192.168.0.0/24` に置かない**(サンドボックス内部と重なる)・VNet と重ねてはいけない予約範囲の一覧、ネットワーク構成は最初の hosted agent 作成時に確定、が加わった([casebook P-N05・N24](../casebook/02-pitfalls-index.md#d-ネットワークと閉域)) | [architecture 07](../architecture/07-usecase-regulated-edge.md) |
| Private Endpoint / Private DNS ゾーン | 閉域のインバウンド設計(Foundry は DNS ゾーン3種)。PE は自動作成されない。※2026-11-22: BYO Cosmos DB 等の private DNS ゾーンは**エージェントサブネットのある VNet にリンク**する(ハブだけにリンクすると Agents ページがタイムアウト)。カスタム DNS からは 168.63.129.16 への転送が要る([casebook P-N22](../casebook/02-pitfalls-index.md#d-ネットワークと閉域)) | 同上 |
| Azure Firewall / UDR / 強制トンネリング | アウトバウンド制御。Managed VNet の FQDN ルールで Firewall が自動作成・SKU 変更不可。※2026-11-22: FW の **TLS 検査**はエージェントサブネットの Entra / マネージド ID の通信(`login.microsoftonline.com` など 3 FQDN)を除外する(private CA trust は効かない = [casebook P-N23](../casebook/02-pitfalls-index.md#d-ネットワークと閉域))。hosted agent の egress controls は GA になったが Firewall の補完 | 同上 |
| Application Gateway / WAF | 顧客向け公開の入口。WAF のチャット誤検知チューニングは頻出論点 | [architecture 06](../architecture/06-usecase-customer-facing.md) |
| NAT / SNAT / サービスタグ / FQDN 許可リスト | egress 許可リストの設計(AzureActiveDirectory タグ等)、SNAT 枯渇 | [architecture 07](../architecture/07-usecase-regulated-edge.md) |

学習リンク: AZ-104 のネットワークモジュール群 + https://learn.microsoft.com/ja-jp/azure/private-link/ ・ https://learn.microsoft.com/ja-jp/azure/firewall/

### ID(Entra ID)(必要度: 高)

| トピック | どの設計判断で使うか | 本リポジトリの該当箇所 |
| --- | --- | --- |
| アプリ登録 / API 権限 / 管理者同意 | Work IQ(`WorkIQAgent.Ask` 委任権限 + Global Admin 同意)等の BYO アプリ構成 | [features 04](../features/04-tools-knowledge.md) |
| **OAuth2 On-Behalf-Of(OBO)フロー** | SharePoint / Fabric 系ツールは OBO 必須(サービスプリンシパル不可)。「ユーザーの権限でデータを引く」仕組みの説明責任 | 同上 |
| マネージド ID(システム/ユーザー割当) | 接続の認証・CMK の前提条件・キーレス構成(`disableLocalAuth`) | [features 01](../features/01-platform-projects.md) |
| RBAC のスコープ設計 | Foundry 5ロール(User / Project Manager / Account Owner / Owner / Agent Consumer)+ agent スコープ。改名中は GUID 指定。※2026-11-22: `agents/write` を持つ主体はエージェントを介さずにモデルを呼べる、エージェントスコープの割り当てはプロジェクトのファイルを分離しない(信頼境界はプロジェクト)、**Foundry のロールではコストが見えない**(Cost Management Reader を RG / サブスクリプションに別付与)([casebook P-I14〜I16](../casebook/02-pitfalls-index.md#c-id-と-rbac)) | 同上 |
| 利用者委任の 2 方式(2026-10-06 追加) | hosted agent が利用者の権限でツールを呼ぶとき、**toolbox 経由**(OAuth identity passthrough。公式推奨、同一テナント必須、利用者に Foundry Agent Consumer)か、**アプリ管理 OBO**(中間層が OBO でトークンを取り `x-client-*` で渡す)か。どちらも OBO / 同意 / audience の理解が前提 | [01 ヒアリング 4-8](./01-hearing-sheet.md#phase-4-セキュリティ・規制-15分)・[casebook P-H26](../casebook/02-pitfalls-index.md#a-hosted-agent) |
| agent identity とマネージド ID の区別 | prompt agent はプロジェクト共通の agent identity(サービスプリンシパル)を共有 — 監査説明で混同しない | [architecture 05](../architecture/05-usecase-agent-automation.md) |

学習リンク: https://learn.microsoft.com/ja-jp/entra/identity-platform/ (特に v2.0 フロー解説)

### 監視・ログ(必要度: 中 — コスト直結)

| トピック | どの設計判断で使うか | 本リポジトリの該当箇所 |
| --- | --- | --- |
| App Insights / Log Analytics の**取り込み課金と保持** | トレース全量記録は高額。サンプリング・保持年限・エクスポート設計 | [architecture 09](../architecture/09-operations.md)・[02 コスト手順](./02-cost-estimation.md) |
| KQL の基礎 | 監査要件(誰が何を聞いたか)の抽出、ダッシュボード自作 | 同上 |
| **保護テーブル(Protected tables)と Privileged Monitoring Data Reader**(2026-10-06 追加) | 会話本文を運用ログに残すときに閲覧者を限定する(本文属性の専用テーブル `AppGenAIContent` を Protected にする。Log Analytics Reader では読めなくなり、トレース評価を回すプロジェクト MI にも同ロールが要る)。テーブル単位の RBAC・ワークスペースのアクセス制御モード(Require workspace permissions)の理解が前提。2026-10-06 の実測では従来テーブルとの二重書きで、Protected だけでは隠れない。振り分けの対象は `gen_ai.*` の属性名だけ(MAF のメッセージイベント・自前ログの本文は対象外 = casebook P-O18)。azure-monitor-opentelemetry 1.8.x の既定サンプラー(5 スパン / 秒)でトレースが歯抜けになる点も監視設計の基礎知識に(P-O16) | [architecture 09](../architecture/09-operations.md)・[casebook P-O13・O14](../casebook/02-pitfalls-index.md#g-観測と評価) |
| Azure Monitor アラート / アクショングループ | 予算アラート(**ハードリミットは存在しない**。※2026-11-22: Foundry の cost controls〈preview〉で GPT / o-series の超過を HTTP 429 で止められるようになったが、PTU・ツール・hosted は対象外で判定できなければ通す。アラートは Event Grid 経由 = [casebook P-M25](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト))、クォータ逼迫検知 | [02 コスト手順](./02-cost-estimation.md) |
| OpenTelemetry の概念 | Foundry トレーシングは OTel ベース。MAF / LangGraph 計装の共通言語 | [features 05](../features/05-observability-evaluation.md) |

### ガバナンス(必要度: 中)

| トピック | どの設計判断で使うか | 本リポジトリの該当箇所 |
| --- | --- | --- |
| サブスクリプション設計 / 管理グループ | hosted agent の同時セッション上限・モデルクォータは**サブスクリプション×リージョン単位**(同時セッション既定 2,000〈Japan East 等〉/ 1,000、申請で引き上げ可。limits-quotas-regions 2026-09-07 版)→ 引き上げで足りなければサブスクリプション分割 | [architecture 06](../architecture/06-usecase-customer-facing.md) |
| Azure Policy | 承認済みモデル限定(GA)・プレビューモデル禁止(プレビュー)・プレビュー UI 無効化タグ。※2026-11-22: エージェント種別・hosted のコンテナイメージ・ツール(`toolControls`)・egress を縛る組み込み定義が加わったが、**いずれも preview で Canada Central / Spain Central / Korea Central のみ**(日本リージョンなし、反映 30〜60 分)。Model router では Azure Policy は作成・更新時だけ評価し、要求時のルーティング先は絞らない([casebook P-N25・M22](../casebook/02-pitfalls-index.md#d-ネットワークと閉域)) | [features 01](../features/01-platform-projects.md) |
| Landing Zone(CAF) | AI は通常ワークロードとして application landing zone へ。共有 vs 専用の5条件 | [architecture 01](../architecture/01-official-baselines.md) |
| タグ / Cost Management | チャージバック(project タグはプレビュー)・部門按分。※2026-11-22: Foundry ポータルの Manage > Cost(preview)はコストを 8〜24 時間遅れで出し、エージェント名のタグは 2026-11 以降の利用から。閲覧には Cost Management Reader が要る([casebook P-I16](../casebook/02-pitfalls-index.md#c-id-と-rbac)) | [02 コスト手順](./02-cost-estimation.md) |
| IaC(Bicep / Terraform) | Foundry は `Microsoft.CognitiveServices/accounts`。**capability host / ネットワーク注入は冪等更新が効かない**という Foundry 固有の癖。capability host は後継の **capability settings**(プレビュー、API `2026-07-15-preview`、UK South / Canada Central のみ、既存プロジェクトへの追加・変更不可)へ移行中( https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-capability-settings 、2026-09-22 版)。※2026-10-06: Terraform で hosted agent を扱う公式手順が出た — azd の `--infra=terraform`(インフラのみ)と AzAPI の `azapi_data_plane_resource`(名前付きエージェントまで管理)。eject は閉域の `network:` 構成に非対応([casebook P-C13](../casebook/02-pitfalls-index.md#j-iac-cli-ci-cd))。※2026-10-14: capability settings の設定ページ(上記 URL)は 301 で agents/environment-setup(capability settings の記述なし)へ転送されるようになり、取り下げか移設中か要確認。当面は安定版 ARM API の capability host を基準に学ぶ([casebook P-C06](../casebook/02-pitfalls-index.md#j-iac-cli-ci-cd))。AI Search の管理 API `2026-09-01-preview` の自動生成 DNS ラベル(preview)を使うとエンドポイントが `<name>-<label>.sg.search.windows.net` になるので、IaC ではサービス名からエンドポイントを組み立てず `properties.endpoint` を読む([casebook P-C17](../casebook/02-pitfalls-index.md#j-iac-cli-ci-cd))。※2026-11-22: **azd の Foundry 拡張群が GA**(2026-11-05、`microsoft.foundry` 1.0・`azure.ai.agents` 1.x、azd 1.37.0 以上)になり、CI/CD の標準の CLI は azd。GA の前後に破壊的変更(`toolboxes` への改名・preview 機能の `AZD_ALPHA_ENABLE_AGENTS_*` opt-in・評価コマンドの別拡張化)があるので版を固定して学ぶ([casebook P-C18](../casebook/02-pitfalls-index.md#j-iac-cli-ci-cd))。**`az cognitiveservices agent` は Deprecated で、2027-02-28 後の最初の Azure CLI リリースで削除**(P-C01)。hosted agent の egress 規則を含む RAI ポリシーは安定版 `2026-09-01` で書く(古い api-version のエクスポートは egress 規則が落ちる = P-N25)。チームの環境構築は Foundry Dev Pack(2026-11-18 GA)で一括導入できる | [architecture 09](../architecture/09-operations.md) |

学習リンク: https://learn.microsoft.com/ja-jp/azure/cloud-adoption-framework/ ・ https://learn.microsoft.com/ja-jp/azure/well-architected/

### データサービス(必要度: 中 — RAG / standard setup で必須)

| トピック | どの設計判断で使うか | 本リポジトリの該当箇所 |
| --- | --- | --- |
| **AI Search の SKU / レプリカ / パーティション** | RAG の月額固定費の支配項。ベクトルクォータは**サービス作成日で異なる**。S3 HD はナレッジベース不可。※2026-11-22: 製品名は **Foundry IQ (Azure AI Search)** に改称(リソース種別 `Microsoft.Search`・`*.search.windows.net`・API 版・RBAC ロール名・課金メーター名は不変で、学ぶ中身は同じ)。Serverless は閉域の取り込み(private ingestion)ができず Dedicated と相互移行できない、インデクサーは累積 48 時間 / 24 時間の窓を共有する — SKU の選定で閉域の要否を先に決める([casebook P-R19](../casebook/02-pitfalls-index.md#e-rag-とナレッジ))。データプレーンの安定版 `2026-10-01` で LLM クエリプランニング・answer synthesis が GA | [architecture 04](../architecture/04-usecase-chat-rag.md) |
| Cosmos DB の RU/s | standard setup の BYO 要件(最低 3,000 RU/s/プロジェクト、Responses 利用で実質 5,000) | [architecture 07](../architecture/07-usecase-regulated-edge.md)・09 |
| Blob Storage(SAS / ライフサイクル) | ファイル取り込み・BYO ストレージ・監査ログエクスポート | — |

### コンピュート(必要度: 低 — 特定構成のみ)

| トピック | いつ必要になるか |
| --- | --- |
| App Service | チャット UI / API のフロントをホストする場合(ベースライン構成の一部)。コードファーストエージェントを Foundry 外でホストする選択肢 |
| Container Apps(+ dynamic sessions) | Code Interpreter の基盤理解、Custom Code Interpreter、自前サンドボックス実行 |
| AKS | 大規模 self-host(LangGraph 等を Foundry に載せない判断をした場合)のみ。**Foundry マネージド路線では不要**。※2026-11-22: Foundry の hosted agent を**顧客の AKS クラスター上で動かす配置(BYO-AKS)**が coming soon(限定プレビュー受付中、public preview は 12 月上旬が目標。Learn の手順は未公開)。採用するとクラスター・ネットワーク・ノードプール・容量の運用は顧客側になるので、AKS の知識の必要度が上がる |
| VM | ほぼ不要(セルフホストランナー〈閉域 CI/CD 用〉くらい) |

## 資格との対応

| 資格 | 本マップとの関係 |
| --- | --- |
| AZ-104(Azure Administrator) | ネットワーク・ID・ガバナンスのモジュールは有効。**VM / ストレージ運用の章はスキップ可**。 https://learn.microsoft.com/ja-jp/credentials/certifications/azure-administrator/ |
| AZ-305(Solutions Architect) | 本リポジトリの用途(構成の設計判断)に最も近い。非機能要件 → 構成のマッピング訓練として有効。 https://learn.microsoft.com/ja-jp/credentials/certifications/azure-solutions-architect/ |
| AI-103(Azure AI Apps and Agents Developer Associate) | **AI-102(Azure AI Engineer Associate)は 2026-06-30 に退役**し、後継はこの AI-103(Python + Microsoft Foundry でのエージェント / 生成 AI 開発が中心)。Foundry 固有部分は本リポジトリの方が新しい・深いが、Speech / Vision / Language 系の基礎補完に使える。 https://learn.microsoft.com/ja-jp/credentials/certifications/azure-ai-apps-and-agents-developer-associate/ (退役一覧: https://learn.microsoft.com/en-us/credentials/support/retired-certification-exams 。AI-900 試験も同日退役し、Azure AI Fundamentals は AI-901 に置換) |

## 読む順序の推奨(オンボーディング)

1. **[features README](../features/README.md)** — 用語と 2025-11 改編の全体像(30分)
2. Entra ID の OBO フロー解説(外部)→ **[features 04(ツール)](../features/04-tools-knowledge.md)**(1時間)
3. **[architecture 03(判断ガイド)](../architecture/03-decision-guide.md)** → 担当案件のユースケース章(2時間)
4. 閉域案件の担当者のみ: Private Link / Firewall の基礎(外部)→ **[architecture 07](../architecture/07-usecase-regulated-edge.md)**(2時間)
5. 提案担当: **[01 ヒアリングシート](./01-hearing-sheet.md)** + **[02 コスト手順](./02-cost-estimation.md)**(1時間)
