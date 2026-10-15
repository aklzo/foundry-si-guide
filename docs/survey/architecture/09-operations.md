# 09. 運用アーキテクチャ(キャパシティ・BCDR・可観測性・評価・コスト・CI/CD)

[← アーキテクチャ TOP](./README.md)

> **最終更新:** 2026-07-30(公式ドキュメントとの突合検証で訂正) / 2026-09-26(hosted agent 同時セッション上限・デプロイ種別・Prompt caching・評価リージョン/シナリオ・Monitor 設定・トラフィック分割などを 2026-09 時点の一次情報で再検証)/ 2026-09-30(§3.6 hosted agent のトレースの中身と閲覧者の選定基準、§6.3 会話の続きの agent 単位の制約を Port 15 のライブ検証から追加。同日、§6.3 に版更新・ロールバック・旧版削除と会話の継続を foundry-probes probe 10 の実測で追加)/ 2026-10-06(§3.6 に第 4 案「同じ App Insights のまま中身だけ保護テーブルに隔離」〈`AppGenAIContent`、2026-09-30 から既定の振り分け〉と Agent 365 への送出を追加、§4 に評価の権限・合成評価器・`azure-ai-projects` 2.8.0、§6.3 に公式の本番リリース手順と「既存セッションは作成時の版に束縛」の両論併記・カナリアの公式間不整合、§6.4 に hosted agent の Terraform、§1 に GPT-6.1 Sol と normalized token のキャッシュ消費を反映) / 2026-10-14(差分更新: §3.6 に `azure-ai-agentserver-responses` 2.3.0 のテレメトリ送出の既定〈background〉・LangChain tracer の内容記録の既定・Privileged Monitoring Data Reader の付与先・公式の確認手順の限界、§4 に Learn のラベル外しと GA 一覧表の 3 者併記・トレース評価の版固定〈2.7.0〉・Rubric 評価器と `score_model` の区別・評価レベル混在の食い違い、§1.5 に Bing ツールでキャッシュが効かない件、§5.2 に Flex processing と Model router の既定プール、§6.2 に capability settings 設定ページの 301 とプロビジョニング ID の経路差、§6.3〜6.4 に invoke の版束縛の記述と azd 拡張の破壊的変更を追加)

ユースケースを問わず横断で効く運用設計をまとめる。**この領域は「Foundry がやってくれない範囲」が広く、見積もりの抜けが出やすい。**

## この章の要点(先に結論)

1. **Foundry は自動フェイルオーバーも DR も提供しない。**「Foundry itself doesn't provide automatic failover or disaster recovery」と明記されている。マルチリージョンは自前設計。
2. **Agent Service の状態(会話・エージェント定義)には DR 機能がない。**「復旧はレプリカの昇格ではなく再構築で行う」。Cosmos DB の継続バックアップが唯一の救済で、**インシデント発生後には有効化できない。**
3. **エージェントの blue-green / canary は組み込み機能がない。**必要ならエージェント API の前段にルーティング層(APIM 等)を自分で置く。**※2026-10-06:** hosted agent の本番昇格ページ(preview)は同一エンドポイントで 90/10 のカナリアを示しており、「分割不可」と書く他の公式ページと食い違う(§6.3)。
4. **Azure Monitor のレガシー `Latency` メトリクスを使ってはいけない。**Azure OpenAI 用に設計されておらず誤った診断になると明記されている。
5. **リスク・安全性評価と AI Red Teaming は日本リージョンで実行できない。**評価用に別リージョンのプロジェクトを構える設計になる。
6. **capabilityHost は作成後に更新できない。**構成変更は **capability host の削除・再作成**が前提(プロジェクト削除は不要。同名+異構成での再作成は 400 になる)で、IaC の冪等更新が効かない。
7. **hosted agent は App Insights を接続すると、プラットフォーム側で会話の中身(ツール結果を含む)まで記録され、コンテナ側の設定では止められない。**中身を残せない要件なら「接続しない」を最初に選ぶ。**公式は 2026-09-30 以降、中身(GenAI の機微属性 7 種)を専用テーブル `AppGenAIContent` に振り分けるとする**ので、閲覧者を分けたいなら「同じ App Insights のままそのテーブルを Protected にする」(preview)か「App Insights を 2 つに分ける」を選ぶ(§3.6)。振り分けは既定だが、**閲覧制限(Protected 化)は自分で設定しない限り掛からない。**ただし **2026-10-06 の実測(フラグ未登録)では本文が従来の `AppDependencies` と `AppGenAIContent` に二重書きされ、従来テーブルの本文は通常のリーダーで読めた**ので、案 4 は「フラグ登録または移行完了 + Protected + ロール限定 + `gen_ai.*` 以外に本文を書く計装の停止」の 4 点をそろえ、従来テーブルに本文が残っていないことを KQL で確認してから採る([実測] [probe 11](../../../labs/foundry-probes/probes/11-trace-content-routing/NOTES.md) 2026-10-06)。
8. **hosted agent の版を切り替えても、起動中の会話は作成時の版のまま応答し続ける(公式・実測とも一致)。休止(idle 経過・`stop_session`)明けの版は 2026-10-06 の実測で構成によって割れた** — 公式と Port 11(MAF ホスティング)は作成時の版、probe 10(Agent Server SDK だけの最小エージェント)は現行セレクタの版(`version_ref` 固定も同じ)。原因は未切り分け(§6.3)。本番は「production を具体版にピン留め → 候補を版固定セッションで検証 → 昇格 → 新しいセッションで確認」の公式手順で出し、**受入試験に「`stop_session` 後・idle 明けにどの版が答えるか」を入れる**。旧版で会話を最後まで続けさせたいならエージェント名を分ける。応答の `agent_reference.version` は答えた版ではない。

---

## 1. キャパシティ設計

### 1.1 デプロイ種別の選択

デプロイ種別は「**データ処理範囲(Global / Data Zone / Regional)× 課金形態(Standard / Provisioned / Batch)**」のマトリクスで決まる。SKU 名がそのまま ARM 上の識別子になる。

| 種別 | SKU コード | データ処理 | 課金 |
|---|---|---|---|
| Global Standard | `GlobalStandard` | 任意の Azure リージョン | 従量。最大クォータ |
| Global Provisioned | `GlobalProvisionedManaged` | 任意の Azure リージョン | PTU 予約 |
| Global Batch | `GlobalBatch` | 任意の Azure リージョン | **50% 割引**・24h 目標 |
| Data Zone Standard | `DataZoneStandard` | データゾーン内(US / EU / APAC) | 従量 |
| Data Zone Provisioned | `DataZoneProvisionedManaged` | データゾーン内 | PTU 予約 |
| Data Zone Batch | `DataZoneBatch` | データゾーン内 | **50% 割引**・24h 目標 |
| Standard(リージョナル) | `Standard` | **指定した Azure ジオグラフィ内**(運用目的でジオ内の別リージョンで処理されうる) | 従量 |
| Regional Provisioned | `ProvisionedManaged` | 指定した Azure ジオグラフィ内(同上) | PTU 予約 |
| Developer | `DeveloperTier` | 任意の Azure リージョン(**データレジデンシ保証なし**) | 従量。**FT モデル評価専用・SLA なし・24 時間で自動削除** |
| Instant(プレビュー) | (デプロイ不要。公式は「デプロイ種別ではない」と明記) | 任意の Azure リージョン | 従量。**プレビュー中は West US 3 のプロジェクトのみ** |

> **2026-09-26 確認:** [deployment-types](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/deployment-types)(ms.date 2026-08-06 / 最終更新 2026-08-12)は Standard / Regional Provisioned の処理範囲を「customer-specified Azure geography 内(運用目的でジオ内のリージョン間処理がありうる)」と記載しており、旧記載の「単一リージョン」は不正確だった。日本の場合は Japan ジオグラフィ内に留まる。Data Zone Batch も同ページの比較表に並ぶ。

**Global / Data Zone の可用性トレードオフ:** 「Global Standard と Data Zone Standard では、プライマリリージョンでサービス中断が起きると、そのリージョンにルーティングされた全トラフィックが影響を受ける」と明記。

### 1.2 クォータ

- **Quota Tiers(Free Tier〈Tier 0〉+ Tier 1〜6)**に移行済み。初期割当は現使用量と Microsoft との契約関係(EA / MCA-E)で決まり、**使用量増加で自動昇格する。**オプトアウトは `Microsoft.CognitiveServices/quotaTiers` API(プレビュー)。
- **2026-05-07 以降、サブスクリプション単位のクォータプールへ順次移行中。**Global Standard は同一モデル・バージョンで**全リージョン共通の単一プール**、Data Zone Standard はデータゾーンごとのプール。ポータルの Quota ページの `Scope` 列が `Global` / `Data Zone` なら移行済み、リージョン名なら旧方式。
- **Usage tiers(レイテンシ変動の閾値):** テナント全体の月間トークン(全サブスクリプション・全リージョン合算、モデル単位)が一定量を超えると、**レイテンシが 2 倍以上に振れうる**と明記されている。閾値はモデルにより大きく異なり、**約 40 億(o1)〜8,000 億(gpt-5-nano)トークン/月**(gpt-5.5 / gpt-5.6-sol は 250 億、gpt-5.4 は 500 億。[quotas-limits](https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits) 2026-08-20 版で確認。旧記載「250 億〜1,500 億」は範囲が誤り)。Batch と Provisioned には適用されない。

**アーキテクチャに効くハードリミット:**

| 項目 | 値 |
|---|---|
| Foundry リソース / リージョン / サブスクリプション | 100 |
| プロジェクト / リソース | 250(**フルスケール時の実効は約 25**) |
| モデルデプロイ / リソース | 32 |
| PTU / デプロイ 最大 | 100,000 |
| カスタム HTTP ヘッダー数 | 10(超過で **HTTP 431**)。**将来 API ではパススルー廃止予定のため依存禁止** |
| **hosted agent 同時セッション**(既定) | **2,000 / サブスクリプション / リージョン**(Canada Central / East US 2 / **Japan East** / North Central US / South Africa North / Southeast Asia / Sweden Central)、**その他の hosted 対応リージョンは 1,000**。全 Foundry アカウント・プロジェクト合算で、プロビジョニング中・実行中のセッションのみカウント(idle / stopped は含まない)。増枠はサポート申請。超過時は 429 `session_quota_exceeded` / `regional_session_quota_exceeded`(2026-09-26 確認: [limits-quotas-regions](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/limits-quotas-regions) ms.date 2026-09-07。旧記載「50」から変更) |
| エージェントあたりツール / バージョン | 128 / 1,000(Agent Service 固定上限) |
| クライアントタイムアウト推奨 | 推論モデル最大 29 分 / 非ストリーミング 29 分 / **ストリーミング 60 秒** |

### 1.3 PTU サイジング

**基本性質:** PTU は**モデル非依存**(同じクォータで任意の対応モデルをデプロイ可)。ただし **Global / Data Zone / Regional は別クォータプール**で相互流用できない。そして **クォータ ≠ キャパシティ** — 「PTU クォータがあってもキャパシティが利用可能とは限らない」。削除・縮小で解放したキャパシティが戻る保証もない。

**最小デプロイ単位:** Global / Data Zone = **15 PTU(増分 5)**、Regional = **25〜50 PTU(増分 25〜50)**。

**サイジング式:**

```
Input TPM       = Peak RPM × 平均プロンプトトークン
Output TPM      = Peak RPM × 平均応答トークン
Normalized TPM  = Input TPM × (1 - キャッシュ率) + (output:input 比 × Output TPM)
必要 PTU        = Normalized TPM ÷ (Input TPM per PTU)  → 増分単位に切り上げ
```

公式のワークショップ例(gpt-5.2、Data Zone Provisioned、1,000 RPM / プロンプト 200 トークン / 応答 20 トークン):

- キャッシュなし: 200,000 + 8×20,000 = 360,000 → 360,000 ÷ 3,400 = 105.88 → **110 PTU**
- キャッシュ率 50%: 100,000 + 160,000 = 260,000 → 76.47 → **80 PTU**(**約 27% 削減**)

**モデル選択が PTU 効率を大きく変える。**同じ 1 PTU あたりの Input TPM が、gpt-4.1 = 3,000 に対し gpt-4.1-nano = 59,400(約 20 倍)。**小型モデルで足りるタスクを大型モデルに投げると PTU コストが桁で変わる。**

**GPT-6 系は別方式:** `gpt-6-astra`(2026-09-03)/ `gpt-6-sol`(2026-09-22)/ **`gpt-6.1-sol`(2026-09-29)**は上記の output:input 比ではなく、**トークン区分ごとの正規化コストの合計**で Normalized TPM を出す専用手順になっている(1 PTU あたり 600 / 3,000 / 3,000。gpt-6.1-sol のレイテンシ目標は 99% > 50 TPS)。**この方式ではキャッシュ済み入力もキャッシュ書き込みも PTU 容量を消費する**(短コンテキストの重みはキャッシュ読取 0.1〈gpt-6.1-sol は 0.05〉・キャッシュ書込 1.25・出力 5.0、長コンテキストは入力 2.0・出力 7.5)。旧版は「すべてのデプロイでキャッシュトークンは使用率から 100% 控除」と一律に書いていたが、**2026-10-02 版で「normalized token accounting を使わないモデルだけ」に限定された**([provisioned-throughput-sizing](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/provisioned-throughput-sizing) ms.date 2026-10-02、2026-10-06 確認)。また `gpt-image-2` は Global / Data Zone でも最小 100 PTU・増分 100 と例外的。

**運用上の注意:** PTU デプロイは**一時停止できない(削除のみが課金停止)。**課金は分単位で即時反映されるが、「トラフィックに合わせて PTU を上下させる運用は非推奨」(コストで Reservation に劣り、スケールアップ時にキャパシティが無い可能性がある)。推奨形は **PTU でベースライン + Standard でスパイク。**

### 1.4 Spillover(PTU → Standard の溢れ処理)

**前提:** 同一 Foundry リソース内に、同一モデル・同一バージョンの Provisioned デプロイと Standard デプロイの両方が必要。

- 設定は ARM の `properties.spilloverDeploymentName`(デプロイ単位)またはヘッダー `x-ms-spillover-deployment`(リクエスト単位)。**両方設定するとデプロイプロパティが優先。**
- 発動条件は `429`(PTU 枯渇)/ `400`(長コンテキスト)/ `500` / `503`。
- **監視上の落とし穴:** 溢れた分は **PTU 側の 429 としてカウントされない**(Standard 側に `IsSpillover=True` の `200` として記録される)。**PTU の 429 件数で飽和を判断すると誤る。**
- 公式推奨は「**すべての global / data zone provisioned デプロイで spillover を有効にせよ**」。ただし PTU 優先処理のため追加レイテンシが発生しうる。
- 対象モデル: 旧版は「Azure OpenAI モデルのみ(DeepSeek / Llama は非対応)」と記載していたが、現行の [spillover ページ](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/spillover-traffic-management)(ms.date 2026-06-18)にはこの制限記述が見当たらない(要確認)。前提条件は「同一モデル・バージョンの従量課金デプロイが 1 つ以上あること」。Agent Service 経由のリクエストでも spillover は動作すると明記。

### 1.5 Prompt caching

- **条件:** プロンプト最低 **1,024 トークン**、かつ**先頭 1,024 トークンが完全一致。**以降は 128 トークン単位でヒット。**1 文字違えばヒットしない。**
- **保持ポリシー(gpt-5.5 以前):** `prompt_cache_retention` で `in_memory`(非アクティブ 5〜10 分、最終使用から 1 時間以内に必ず消去)/ `24h`(extended。最大 24 時間)を選ぶ。**gpt-5.4 以前の既定は `in_memory`、gpt-5.5 は extended が既定。**128 トークン単位のヒットも gpt-5.5 以前のみ。
- **gpt-5.6 以降は仕組みが変わった:** `prompt_cache_retention` は適用外(非推奨)で、**`prompt_cache_options.ttl`(`30m` のみ・既定。最低 30 分保持)**と**キャッシュブレークポイント**(implicit / explicit モード。1 リクエストで新規書込は最大 4 つ)で制御し、`prompt_cache_key` で関連リクエストのヒット率を上げる。旧モデルにこれらのパラメータを送ると 400。
- **課金:** Standard はキャッシュ読取が入力単価から割引、**Provisioned は最大 100% 割引(PTU 使用率から全額控除)。****※2026-10-06: GPT-6 Astra / Sol / 6.1 Sol(normalized token accounting)は例外**で、キャッシュ読取・書込が重みに応じて PTU を消費する(§1.3)。キャッシュ率でサイジング例の「-27%」を見込むのは GPT-5.x 以前のモデルに限る。
- **⚠ gpt-5.6 以降はキャッシュ書き込みが課金対象**(それ以前は無料)。Standard(従量)では `usage` に **`cache_write_tokens` が別掲される**ので読取(`cached_tokens`)と書込を比較して監視する(PTU-M ではブレークポイントも `cache_write_tokens` も非対応)。書込課金を避けたい Standard リクエストは `prompt_cache_options.mode=explicit` + ブレークポイントなしでキャッシュを無効化できる(2026-09-26 確認: [prompt-caching](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching) ms.date 2026-08-11。旧記載「書込は別掲されず cached_tokens でしか監視できない」「新しいモデルは既定 24h」は更新)。
- **設計への効き方:** システムプロンプト・ツール定義・共通コンテキストを**プロンプトの先頭に固定配置**し、可変部分を後ろに置く。これだけで PTU 必要量が 2〜3 割変わる。
- **⚠ Grounding with Bing Search / Custom Search を使うとキャッシュがヒットしない(2026-10-14 追加):** bing-tools(ms.date 2026-10-12)の既知事項に、両ツールが毎リクエストに現在時刻入りの指示を追加するためプロンプトキャッシュがヒットしない、と追記された。Bing ツールを付けたエージェントでは、長いシステムプロンプトをキャッシュ前提で見積もったコスト・PTU は成立しない(Web search ツールには同様の記載なし)

### 1.6 Batch

- Global Standard 比 **50% 割引**、**24 時間目標。**データゾーン内処理が要るなら **Data Zone Batch(`DataZoneBatch`)**も同条件で使える(モデル可用性は要確認)。`completion_window` は **`24h` 固定**(他の値を指定するとジョブが失敗する)。
- 24 時間を超えてもジョブは失効せず実行継続する。`expired` は「24 時間ウィンドウ内に完了できなかった」の意味。
- **クォータは「enqueued tokens」でオンライン系と完全分離。**ファイル投入時にトークン数がカウントされ終端状態まで占有する。
- 入力ファイル最大 200MB(BYO Blob なら 1GB)、1 ファイル最大 100,000 リクエスト。
- **設計への効き方:** 「夜間に全文書を分類する」「過去ログを一括要約する」といった処理を**リアルタイム経路から切り離して Batch に回すだけでモデルコストが半減する。**PoC 段階でこの切り分けを設計に入れておく。

---

## 2. 信頼性・BCDR

### 2.1 責任分界

| 層 | 責任 | 対応 |
|---|---|---|
| Agent Service コントロールプレーン / capability host | Microsoft | ゾーン冗長(Microsoft 側で担保) |
| **状態ストア(Cosmos DB / AI Search / Storage)** | **顧客** | 冗長化・バックアップ・レプリケーション設定 |
| Key Vault | Microsoft(自動フェイルオーバー) | 両リージョンで同一インスタンス使用 |
| Application Insights | 顧客 | **リージョンごとに作成** |
| Container Registry | 顧客 | geo-replication 有効化 |
| Foundry プロジェクト | 顧客 | 各リージョンで作成 |

**Basic セットアップは「人的ミスや自動化による損失に対してほぼ復旧能力を提供しない」**と明記。本番は Standard 一択。

### 2.2 マルチリージョン戦略と RTO/RPO(公式目安)

| 戦略 | 概算 RTO | 概算 RPO | 相対コスト |
|---|---|---|---|
| Hot/hot | 数分 | ほぼゼロ | 最高 |
| Hot/warm | **30 分〜2 時間** | 数分〜数時間 | 中 |
| Hot/cold | **2〜8 時間** | 数時間 | 最低 |

**復旧できないもの:** Foundry プロジェクトのサービス側メタデータ(タグ・アセット名・説明)はリージョン障害時に復旧不可。また **Foundry プロジェクトは GRS/GZRS/RA-GRS による既定のストレージアカウントフェイルオーバーをサポートしない。**

### 2.3 モデルデプロイの冗長化パターン

**Standard デプロイ:**
1. データレジデンシが許すなら **Global Standard を第一候補**、次点 Data Zone。
2. 同一サブスクリプション内にプライマリ / セカンダリ 2 リージョンのリソースを配置。
3. 各リージョンで同一モデルのデプロイを作り、**利用可能クォータを全量 1 デプロイに割り当てる**(分割より高スループット)。
4. 前段に **APIM(ロードバランス + サーキットブレーカー)**。

**Provisioned — 「エンタープライズ PTU プール」パターン:**
- 単一の Data Zone PTU デプロイを全社共通プールとし、APIM でアプリ別のスループット制限・優先度・フェイルオーバーを制御。
- **エンタープライズ PTU プールは、プライマリの Standard デプロイとは別リージョンに配置**(同時被災回避)。
- **フェイルオーバーチェーン:** ワークロード専用 PTU → エンタープライズ PTU プール → Standard デプロイ。**PTU 間で溢れる限りレイテンシ SLA が維持される。**

### 2.4 APIM をゲートウェイに置く場合の設計ルール(公式)

- **`Retry-After` を必ず尊重する。**429 を返すエンドポイントを叩き続けず、そのモデルインスタンスのサーキットを開く。**ヘルスチェック専用エンドポイントは存在しない**ため、`429` / `500` / `503` を回路遮断シグナルとして扱う(合成トランザクションはモデル容量を消費してしまう)。
- **ラウンドロビン / フェイルオーバー先は必ず同一モデル・同一バージョン。**バージョン X と X+1 の間でロードバランスしてはならない(クライアント挙動が不定になる)。
- **全インスタンスでデプロイ名を統一**してルーティングロジックを単純化する。
- **ステートフル API はバックエンドをピン留めし、切替不能なら別インスタンスへ回さず 429 を返す**(履歴のないインスタンスへ隠蔽リダイレクトしない)。
- **データ主権:** 地政学的境界を独立したスタンプとして扱い、境界内でのみ active-active / active-passive を適用。**性能ベースルーティングはデータ主権要件と衝突する。**最も確実なのは地政学的リージョンごとに完全独立のゲートウェイを建てること。
- **ゲートウェイ冗長性:** APIM は 2 ユニット以上 × 2 ゾーン以上、カスタム実装なら最低 3 インスタンスを AZ 分散。

**APIM の主要ポリシー:** `llm-token-limit`(TPM 上限とトークンクォータ。`estimate-prompt-tokens` で**バックエンド到達前にプロンプトを弾ける**)/ `llm-emit-token-metric`(カスタムディメンション付きで App Insights へ)/ `llm-semantic-cache-store` `-lookup`(Azure Managed Redis 必須)/ `llm-content-safety` / backend pool(round-robin / weighted / **priority-based** / session-aware)/ circuit breaker(**バックエンドの `Retry-After` 値を動的トリップ期間として適用**)。

### 2.5 Agent 状態の DR(最重要のリスク開示)

> **Foundry Agent Service には組み込みの DR 機能がない。状態のレプリケーション、バックアップ、ポイントインタイム復元のいずれもできない。復旧は再構築で行う。インシデントによってエージェント・会話・ナレッジデータが恒久的に失われうる。**

**Standard セットアップが要求するリソース構成:**

| リソース | 格納内容 | 要件 |
|---|---|---|
| Cosmos DB for NoSQL | メッセージ・会話履歴・エージェントメタデータ(`enterprise_memory` DB) | **アカウント合計で最低 3,000 RU/s**。コンテナーは **3〜5 個 × 各 1,000 RU/s**(基本 3 個+Responses API 利用エージェントの初回起動で 2 個追加)。**Responses 利用時はプロジェクトあたり実質 5,000 RU/s。プロジェクト数だけ倍増が必要** |
| Azure Storage | アップロードファイル | Blob コンテナー 2 種(`azureml-blobstore` / `agents-blobstore`) |
| Azure AI Search | エージェントが作ったベクトルストア | Search Index Data Contributor + Search Service Contributor |

Cosmos DB の RU/s 不足は **capability host のプロビジョニング失敗の直接原因**になる。コンテナーは基本 3 個(`thread-message-store` 系)に加え、**Responses API を使うエージェントの初回起動で 2 個(`agent-definitions-v1` / `run-state-v1`)が追加される**(排他ではなく追加関係。 https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/use-your-own-resources )点にも注意。

**DR 補償策(公式リスト):**

1. **Cosmos DB: 継続バックアップ(7 日 or 30 日)を事前に有効化。インシデント発生後には有効化できない。**PITR 復元は同一アカウント・同一 DB へ。復元後は Foundry プロジェクトの Connected resources でエンドポイントを更新。**組織固有のユニークなアカウント名を使う**(PITR は元名の新アカウントを作るため名前衝突で復元失敗する)。
2. **AI Search: 組み込みのリストアがない。**データ損失時は Microsoft サポート依頼のみで **RTO に重大な影響。****AI Search を一次データストアとして扱わず、元データからの再構築パイプラインを常備する。**
3. **Storage: GZRS + customer-managed failover。**ZRS のみだとサポート依頼が必要で RTO が伸びる。
4. **スレッドに添付されたユーザーアップロードファイルは原則復旧不可。**「一時的(transient)なもの」であることをステークホルダーに合意させる。
5. **エージェント定義をコードとして管理する**(定義・接続・システムプロンプト・パラメータをソース管理へ。**ポータル経由の未追跡変更を避ける**)。
6. プロジェクトには**ユーザー割当マネージド ID** を使う(誤削除時に既存のロール割当を再利用できる)。
7. Foundry アカウント / Cosmos DB / AI Search / Storage に**削除ロック。**ただしコンテナー内データ・個別エージェント・スレッドは保護されない。
8. **単一責務原則:** Cosmos DB / AI Search / Storage はこのワークロード専用にする(爆発半径の限定)。

### 2.6 可用性ゾーンと SLA

- Microsoft 管理の Agent Service コンポーネントはゾーン冗長。**顧客管理の依存(Cosmos DB / AI Search / Storage)は自分でゾーン冗長設定が必要。**
- **Foundry ポータル・データプレーン API・Agent Service はゾーン冗長の直接制御を提供しない。**
- **Standard モデルデプロイは単一リージョンで AZ 非対応。**マルチデータセンター可用性を得るには Global または Data Zone デプロイが必須。
- **Foundry はモデルデプロイに対するラウンドロビンやサーキットブレーカーを提供しない。**リージョン内の粒度細かい冗長性が要るなら APIM 等の自前ゲートウェイが必要。
- AI Search は Standard ティア以上 + AZ 対応リージョン + レプリカ 3 以上でゾーン分散。
- SLA: Azure OpenAI は可用性 **99.9%**、Provisioned-Managed デプロイには**トークン生成の 99% レイテンシ SLA** が付く。
- **`learn.microsoft.com/azure/reliability/reliability-foundry` は存在しない**(404)。Foundry 専用の Azure Reliability ハブページは未整備。

### 2.7 早期検知の運用設定

1. 全 Foundry ワークロードの Azure サービスに **Service Health アラート**
2. Cosmos DB / Azure OpenAI / Storage に **Resource Health アラート**
3. App Insights の**可用性テスト**(複数地点からエージェントエンドポイントを常時プローブ)
4. アクショングループ(メール / SMS / インシデント管理)でフェイルオーバー判断を迅速化
5. **委任サブネットの IP 使用率は Azure portal に露出していない。**枯渇の先行指標は「data proxy の HTTP 5xx」「hosted agent のセッション作成・再開時の **HTTP 429 `subnet_exhausted`**」「新規プロジェクトのプロビジョニング失敗」で、**プラットフォームからの事前警告はない。**定期的にエージェントセッションを作る合成監視で補う。容量目安は既定 IP:セッション = 1:1 で /27 ≈ 20・/26 ≈ 50・/24 ≈ 250 セッション(サポート申請で 1:10 まで)、本番は /24 以上・使用率 80% 未満で設計([agents-networking-deep-dive](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agents-networking-deep-dive) ms.date 2026-09-07)。

---

## 3. 可観測性

### 3.1 トレーシング

- **ステータス:** prompt / hosted エージェントは **GA**、**workflow と外部エージェントはプレビュー。Tracing の VNet 対応もプレビュー。**
- **サーバーサイドトレースが出発点:** Foundry プロジェクトに Application Insights を接続するだけで**コード変更なしに**数分でトレースが出る。**ポータルでは直近 90 日分**を検索・フィルタできる。
- **キャプチャ内容:** ユーザー入力とエージェント出力、ツール呼び出しと結果、**トークン消費**、所要時間・レイテンシ、リトライ、コスト。
- **Conversation ビュー(トレースリプレイ相当):** Response ID / Trace ID から Conversation ID を辿り、会話履歴・順序付きアクション・ツール呼び出し・入出力を再生できる。
- **保存先は App Insights。**保持期間・サンプリング・課金は App Insights / Log Analytics の設定に従う(**Foundry 側の上乗せ課金はない**)。
- **必要ロール:** ログ参照に **Log Analytics Reader**。対象テーブルが Protected なら Privileged Monitoring Data Reader も必要。**公式では 2026-09-30 以降、会話の中身(`gen_ai.input.messages` 等の 7 属性)は専用テーブル `AppGenAIContent` に入る**(2026-10-06 の実測では従来テーブルとの二重書き)ので、中身を読ませる相手だけにこのロールを付ける設計ができる(§3.6 案 4)。**2026-10-14 追記:** Privileged Monitoring Data Reader は**接続先 App Insights リソースに付与すれば App Insights と Foundry の両方の画面で本文を読める**(Foundry は App Insights の API でクエリするため、リンク先 Log Analytics ワークスペースへの付与は不要。ワークスペース中心のクエリを直接打つ ID だけワークスペースにも付与 — traces-sensitive-content 2026-10-06 版)。トレース評価・トレース→データセット生成ではプロジェクトのマネージド ID にもロールが要る(§4.3)。
- **⚠ クライアント側(自前計装・コンテナ)のトレースは既定で間引かれる([実測] [maf-ports](../../../labs/maf-ports/README.md) Port 1・Port 4、2026-10-06):** `azure-monitor-opentelemetry` 1.8.x(1.8.9 / 1.8.10 で確認)の既定サンプラーは **rate-limited(5 spans/秒)**で、ワークフロー開始直後のスパンの山(`workflow.run` / executor / `invoke_agent`)が落ちてトレースが歯抜けになる(Port 4 のローカル再現では 87 本中 27 本しか残らず、親スパンが残っても子は独立に再サンプリングされる)。全件が要るなら `configure_azure_monitor(..., sampling_ratio=1.0)` か `OTEL_TRACES_SAMPLER=always_on`(`microsoft.rate_limited` 指定時は kwargs の `sampling_ratio` が勝つ)。**「トレースの配線は 2 行」にはサンプリングの 3 行目が要る。**取り込み量(= 課金)とのトレードオフなので、本番の比率は意図して決める
- **⚠ 照会側の既定にも注意:** `az monitor app-insights query` は既定で**直近 1 時間**しか見ない(`--offset` 既定 1h が KQL 内の期間指定より優先される)。過去分を数えるときは `--offset` を付けるか Log Analytics を直接引く(同実測。一時的に過少件数を返したこともある)
- **トレースは監査証跡の代わりにしない(本ドキュメントの判断、2026-10-06 の実測で理由が増えた):** ①既定サンプリングで間引かれる(上記)②会話の中身を含みうるので閲覧者を絞る必要があり(§3.6)、監査の閲覧者と要件が合わない ③ポータルの表示は 90 日・保持は App Insights の設定次第。承認・実行の記録は、サンプリングの影響を受けないアプリ側の監査ログ(追記専用ストア等)に持つ
- **取り込みの Entra 認証(プレビュー、2026-08 新設):** 接続済み App Insights への取り込みをキーから**プロジェクトのマネージド ID** に切り替えられる(App Insights 側でローカル認証を無効化して Entra のみに強制)。`disableLocalAuth` を全面適用する規制案件で効く([trace-ingestion-entra-authentication](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-ingestion-entra-authentication) ms.date 2026-08-06)。
- **セキュリティ:** トレースはプロンプト・出力・ツール引数などの機微情報を含みうる。**テレメトリ到達前にマスクする**のが公式ベストプラクティス。**ただし hosted agent のサーバーサイドトレースはアプリ側でマスクできない**(コンテナで内容記録をオフにしても、プラットフォーム側のスパンは会話の中身を記録する — §3.6)。マスクできない中身は「記録させない(接続しない)」か「読み手を絞る(`AppGenAIContent` の保護、または App Insights の分離)」で扱う。

### 3.2 OpenTelemetry GenAI セマンティック規約のステータス(設計に効く)

Foundry は OpenTelemetry のセマンティック規約に従ってトレースを保存するが、**規約側の成熟度は「Development(非安定)」**である。`gen_ai.provider.name` / `gen_ai.operation.name` / `gen_ai.usage.input_tokens` / `gen_ai.conversation.id` / `gen_ai.agent.name` などはすべて Development バッジで、**`gen_ai.system` は既に非推奨(`gen_ai.provider.name` に置換)。**2026 年に GenAI 規約は専用リポジトリへ分離され、コア規約とは別リリースサイクルになった。

> **設計上の含意:** KQL クエリ・Grafana ダッシュボード・アラートを `gen_ai.*` 属性名に直接ハードコードすると、SDK / 規約の更新で壊れる。**属性名を 1 箇所に抽象化する**か、Foundry ポータル側の抽象化に寄せる。

### 3.3 Azure Monitor メトリクス

**⚠ 最重要の落とし穴:** `Cognitive Services - HTTP Requests` カテゴリの**レガシー `Latency` / `BlockedCalls` / `TotalCalls` は Azure OpenAI 用に設計されておらず、使うと誤った診断になる**と明記されている。

**使うべきメトリクス:**

| 目的 | メトリクス |
|---|---|
| リクエスト数・エラー | `AzureOpenAIRequests`(ディメンション: `StatusCode`、**`IsSpillover`**、`ServiceTierRequest/Response`、`StreamType`) |
| 可用性 | `AzureOpenAIAvailabilityRate` |
| 総応答時間 | `AzureOpenAITTLTInMS` |
| 初回トークン応答性 | `AzureOpenAITimeToResponse` |
| トークン生成速度 | `AzureOpenAINormalizedTBTInMS` |
| **PTU 使用率** | **`AzureOpenAIProvisionedManagedUtilizationV2`**(V1 は非推奨) |
| キャッシュヒット率 | `AzureOpenAIContextTokensCacheMatchRate` |
| トークン数 | `ProcessedPromptTokens` / `GeneratedTokens` / `TokenTransaction` |
| ガードレール | `RAIHarmfulRequests`(`Category` / `Severity` で split)/ `RAIRejectedRequests` |

新しい `Models -*` カテゴリ(`ModelRequests` / `InputTokens` / `ProvisionedUtilization` 等)は Azure OpenAI 以外のモデルも含み、ポータルはこちらへの切替を推奨している。

**診断ログ:** `Audit Logs`(無料)/ `Request and Response Logs`(無料)/ `Trace Logs`(無料)/ `Azure OpenAI Request Usage`(課金)/ `Managed Network Events`(課金)。出力先は `AzureDiagnostics` テーブル。**Basic log plan と ingestion-time transformation はいずれも非対応。**Metrics Explorer では Resource types を「**Foundry Tools**」に設定する。

### 3.4 自前オーケストレーション時の可観測性ギャップ

> アプリケーション内でオーケストレーションするコードを App Service 上で動かす場合、**エージェントのメトリクスは Azure AI Foundry には表示されない。Foundry は完全マネージドの Foundry エージェントしか見えないからである。**

OpenTelemetry の GenAI セマンティック規約に沿って計装すれば、Application Insights 側と App Service の Agents タブでは集計される。**「Foundry のダッシュボードを見せる」ことが要件に入っていないかを事前に確認する。**

### 3.5 Agent Monitoring Dashboard(プレビュー)

Foundry ポータル → Build → エージェント → Monitor タブ。データソースは接続済み App Insights。

**公式が示す運用閾値:**
- **Latency: 10 秒超**ならモデルのスロットリング、複雑なツール呼び出し、ネットワーク問題の兆候
- **Run success rate: 95% 未満**なら失敗した run を調査すべき
- Token usage が多すぎる = 冗長なプロンプト / 応答の兆候

設定パネルの内訳(2026-09-26 確認、[how-to-monitor-agents-dashboard](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard) ms.date 2026-09-03): **Recurring evaluations(プレビュー)** / Red team scans(プレビュー)/ Alerts(プレビュー)の 3 項目に整理された(旧版の Continuous evaluation / Scheduled evaluations は **Recurring evaluations に統合**され、その中で「固定スケジュールの scheduled」と「ライブトラフィックをサンプリングする continuous」を選ぶ形。継続的評価のステータス不明瞭は解消しプレビュー確定)。ダッシュボード自体も View agent metrics (preview)。なお GA 一覧表では Red teaming 機能自体は GA だが、**Monitor 設定内の Red team scans(定期スキャン)はプレビュー表記**のまま。**継続的評価の `max_hourly_runs` 既定は 100/時**で、到達すると評価 run がスキップされる。**プロジェクトのマネージド ID に Foundry User ロールが必要**(未付与だとルール作成が失敗する)。**※2026-10-06 実測:** `sampling_rate` は百分率(1.0 = 1%)、継続評価が completed になるのはプロジェクトの Responses + `agent_reference` で呼んだ prompt agent の応答で、エージェントエンドポイント経由の応答は failed(§4.3)。

**Foundry 外のエージェントも監視できる:** Foundry Control Plane に AI Gateway 経由で登録し、同一 App Insights に OTel GenAI 規約準拠のテレメトリを送れば、継続的評価とエラーレート追跡が使える。

### 3.6 トレースに会話の中身を残すか(hosted agent の選定基準)

hosted agent で「会話の中身をどこに残し、誰が読めるか」は、App Insights の**接続**の仕方と、**中身が入るテーブルの保護**で決まる。委任アクセス(利用者ごとに見える文書を絞る構成)では特に効く。2026-09-30 に [Port 15](../../../labs/maf-ports/ports/delegated-access-hosted/README.md) のライブ検証で確認し、公式([trace-data](https://learn.microsoft.com/en-us/azure/foundry/observability/concepts/trace-data) ms.date 2026-06-02 / [deploy-hosted-agent](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent) ms.date 2026-08-17)と突き合わせた。**2026-10-06 注記:** 前回見落としていた公式 how-to [Restrict access to sensitive content in Microsoft Foundry traces (preview)](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/traces-sensitive-content)(ms.date 2026-07-21)を反映し、第 4 案(同じ App Insights のまま中身だけ保護テーブルに隔離)を追加した。

**仕組み — 「接続」1 つで 2 つが同時に起きる**

- 「接続」は、プロジェクトに App Insights を登録する**プロジェクト側の設定**(Foundry Owner / Foundry Account Owner が行う)。トレースは既定オフで、接続したときだけ有効になる。止める公式の手段は**接続の解除だけ**(プロジェクト内の全エージェントが対象)
- 接続すると:
  1. **プラットフォーム側(Agent Service)のサーバーサイドトレースが有効になる。**公式は記録内容を「利用者の入力・モデルの入出力・ツール呼び出し」と明記しており、**会話の中身が入る**(実測: `cloud_RoleName == "responsesapi"` のスパンの `gen_ai.input.messages` / `gen_ai.output.messages` にツール結果まで記録された)
  2. **同じ接続文字列が `APPLICATIONINSIGHTS_CONNECTION_STRING` としてコンテナに注入され**、ホスティングライブラリ(`azure-ai-agentserver-*`。Microsoft OpenTelemetry distro を組み込み済み)がコンテナのトレース・ログを**自動で送る**。既定の構成ではアプリ側に送信コードは要らない(自分で書くのは独自のスパン・ログだけ)
  - **⚠ 2026-10-14 追記 — 送出の既定が変わった:** `azure-ai-agentserver-responses` **2.3.0**(PyPI 2026-10-12)で `AGENTSERVER_FLUSH_MODE` の既定が `async` → **`background`** になり、Responses の要求完了がテレメトリ送出を待たなくなった(CHANGELOG は「要求の完了はテレメトリの到達を保証しない。background 送出にはサスペンド / 停止前のドレイン時間が要る」と明記)。idle で計算が止まるまでに送り切れないとスパンが欠ける。`agent-framework-foundry-hosting` 1.0.0b261008 の依存範囲(`>=2.2.0b1,<3`)では新規環境に 2.3.0 が入るので、**トレースの欠落を調べるときは既定サンプラー(§3.1)に加えてこの既定を疑い、要求ごとに送り切るなら `AGENTSERVER_FLUSH_MODE=async` を明示する**
- コンテナの `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false` が効くのは**コンテナ内の計装だけ**で、プラットフォーム側の記録は止まらない(実測)。サーバー側の中身だけを止める設定は公式に見当たらない(trace-data に「Configurable policies」とあるが具体的な手段の記載なし)
- **LangChain / LangGraph をコンテナで使う場合(2026-10-14 追記):** `langchain-azure-ai` の `AzureAIOpenTelemetryTracer` は**メッセージとツール呼び出しの内容の記録が既定で有効**(`enable_content_recording=False` で止める — langchain-traces)。案 4 の条件 (4)「`gen_ai.*` 以外に本文を書く計装を止める」や案 2・3 のコンテナ側の扱いでは、この既定を明示的に切る
- そのため §3.1 の「テレメトリ到達前にマスクする」は**コンテナ側にしか適用できない**。サーバー側に載るのは「モデルに渡したもの」なので、減らすにはモデルに渡す情報そのものを減らす(トークンが載らないのは、そもそもモデル入力に入れないから)
- 逆に、アプリが**自前の接続文字列で別の App Insights に送っても「接続」にはならない**(プラットフォーム側の記録は有効にならない)
- **会話履歴の保存とトレースは別物。**会話履歴(`store: true` の応答。`previous_response_id` で続けるため)の保存先を変えるのが Standard setup(BYO Cosmos DB 等)で、トレースに中身が入るかどうかは Basic / Standard どちらでも「接続したか」だけで決まる

**2026-09-30 から — 中身は専用テーブル `AppGenAIContent` に振り分けられる(公式では既定。2026-10-06 の実測ではまだ従来テーブルとの二重書き)**

> **⚠ 両論併記(2026-10-06 実測):** 公式は「移行日 2026-09-30 以降に取り込むデータは、既定で中身が `AppGenAIContent` だけに入る」と書く。一方、**2026-10-06 の japaneast 実測**(サブスクリプションの feature flag は `protectGenAISensitiveData` / `optOutProtectGenAISensitiveData` とも未登録、MAF 1.20 のクライアント側スパンで中身の記録を有効にして 1 往復)では、**会話本文は `AppDependencies.Properties` の `gen_ai.input.messages` / `gen_ai.output.messages` / `gen_ai.system_instructions` と `AppGenAIContent`(InputMessages / OutputMessages / SystemInstructions 列)の両方に二重書きされた**。`AppDependencies` 側の内部プロパティ `_MS.GenAIContentId` が `AppGenAIContent.Id` と一致して両者を対応づけ、`AppGenAIContent` への着信は約 5 分遅れた。`AppTraces` にもメッセージのログイベントが残った(これが振り分け対象かは未確認)。**つまりこのサブスクリプション・リージョンでは移行日以降の既定動作はまだ有効になっておらず、従来テーブルの本文は通常の Log Analytics Reader で読める。**早期有効化フラグを登録した後の挙動は未検証(サブスクリプション全体の設定変更になるため実施していない)。**[実測] [probe 11](../../../labs/foundry-probes/probes/11-trace-content-routing/NOTES.md)(2026-10-06、同条件)で発生源を 4 種に広げても結果は同じ** — 合成した `gen_ai.*` スパン、ログレコードの `gen_ai.*` 属性、prompt agent のプラットフォーム側スパン、MAF のクライアント側スパンの**すべてが二重書き**(`_MS.GenAIContentId` は `AppGenAIContent.Id` と 1 対 1)。**`gen_ai.*` 以外の属性名に入れた同じ本文と、MAF のメッセージイベント(`AppTraces` の Message 本体)は振り分け対象外**。`AppGenAIContent` の着信遅れは 0〜約 6 分で一定しない(直後に 0 件でも未振り分けと判断しない)。hosted agent のプラットフォーム側スパン(`responsesapi`)も Port 11 のライブで二重書きだった(本節末の表)。

- 対象は OpenTelemetry GenAI の**機微属性 7 種**: `gen_ai.input.messages` / `gen_ai.output.messages` / `gen_ai.system_instructions` / `gen_ai.tool.definitions` / `gen_ai.tool.call.arguments` / `gen_ai.tool.call.result` / `gen_ai.evaluation.explanation`。Application Insights がこれらの値を専用テーブル **`AppGenAIContent`** に入れる
- **移行日 2026-09-30 より前**は既存テーブル(`AppDependencies` / `AppTraces` / `AppEvents`)と `AppGenAIContent` の**両方**に入っていた。**公式の記述では、2026-09-30 以降に取り込むデータ**は、既存テーブル側の値が `AppGenAIContent` への短い参照に置き換わり(属性キーは残る)、値は `AppGenAIContent` にだけ入る。**移行日より前に取り込んだデータは既存テーブルに中身入りのまま残る**(保持期間が切れるまで)
- 移行日前の早期有効化はサブスクリプションの preview フラグ `protectGenAISensitiveData`(名前空間 `Microsoft.Insights`)。自作クエリの書き換えが間に合わない場合の**一時的な opt-out フラグ `optOutProtectGenAISensitiveData` は 2027-09-30 で廃止**され、以降はフラグに関係なく `AppGenAIContent` だけになる
- **振り分けだけでは読み手は絞られない。**`AppGenAIContent` を **Protected(既定拒否)**に設定すると、標準の閲覧ロール(Log Analytics Reader 等)とカスタムロールからの読み取りがその時点で止まり、**Privileged Monitoring Data Reader** を付けた ID だけが読める(PIM で期限付き・JIT にもできる。保護テーブル用の AzMon DataActions を含むカスタムロールも読める)。保護の設定には Log Analytics Contributor、フラグ登録にはサブスクリプションの Owner 相当が要る
- **閲覧制限が成立する条件(2026-10-06 実測を受けて 4 点):** (1) 早期フラグ `protectGenAISensitiveData` の登録か移行の完了により、**従来テーブルに本文が入らなくなっていること**、(2) `AppGenAIContent` を Protected にすること、(3) Privileged Monitoring Data Reader を限定して付けること、(4) **`gen_ai.*` 以外に本文を書く計装を止めること**(MAF のメッセージイベント〈`enable_instrumentation(enable_sensitive_data=True)` で出る `AppTraces` のログ〉・自前のログや独自属性) — の 4 点がそろって初めて成立する。二重書きのまま (2)(3) だけを行っても、従来テーブルの本文は Log Analytics Reader で読める。**採用前に KQL で従来テーブルを確認する**(`AppDependencies | where isnotempty(Properties['gen_ai.input.messages']) | count` が 0。`AppTraces` のメッセージイベントも同様)
- 確認方法(公式): Log Analytics Reader だけの利用者には**中身以外のトレースが見え、中身は見えない**こと、Privileged Monitoring Data Reader の利用者には中身が見えることを確かめる。ポータルのトレース画面(Trajectories)でも入出力が伏せて表示される(公式のスクリーンショット)。**⚠ 2026-10-14 注記: 公式の確認手順(en 2026-10-06 版・ja 10-12 版とも不変)は従来テーブルに本文が残っていないかを確認対象に含まない** — 二重書きの環境では公式手順に合格しても従来テーブルの本文は Log Analytics Reader で読めるので、上の KQL 確認を受入試験の別項目として残す([10 A17](./10-migration-antipatterns.md#a17-appgenaicontent-を-protected-にしただけで-トレースの本文は隠せた-と判断する))
- 組込みの App Insights / Foundry の画面は自動で追随する。**自作の KQL・アラート・ダッシュボード・ブック・レポートで既存テーブルからこれらの値を読んでいるものは書き換えが要る**(§3.2 の「属性名を 1 箇所に抽象化」と同じ論点)

**この振り分けで変わること・変わらないこと(Port 15 の実測との関係)**

- 変わるのは**中身の置き場所と読める人**だけで、**記録されるかどうかは変わらない。**プラットフォーム側のスパンは引き続き中身を記録し、コンテナの `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false` では止まらない(Port 15 の結論はそのまま)。**「中身を残さない」要件は依然として案 3 でしか満たせない**
- 振り分けの対象は**上の 7 属性だけ**。コンテナ側がログの本文・例外メッセージ・独自のスパン属性・別名の属性(旧い計装の属性名など)に書いた中身は既存テーブルに残る(**[実測] [probe 11](../../../labs/foundry-probes/probes/11-trace-content-routing/NOTES.md): 振り分けは取り込み側で属性名だけで決まり、同じ本文でも `gen_ai.*` 以外のキーや MAF のメッセージイベントは対象外**)。**§3.1 のコンテナ側マスクと、本文を書く計装の停止は案 4 でも必要**
- **プラットフォーム側スパンはオプトインなしで本文を記録する**(hosted agent: Port 15 / Port 11、prompt agent: probe 11。いずれも `gen_ai.input.messages` / `gen_ai.output.messages`。prompt agent では system instructions の属性は出ていなかった)
- Port 15 の測定(2026-09-30 = 移行日当日の取り込み)は、`responsesapi` スパンの `gen_ai.input.messages` / `gen_ai.output.messages` に中身があることを確認したが、どのテーブルで読んだか(既存テーブルに値が残っていたのか、`AppGenAIContent` を含めて読んだのか)は記録していない。移行前の挙動か展開途中かも判別できない。2026-10-06 のクライアント側計装の実測(上の両論併記)では本文が従来テーブルと `AppGenAIContent` に二重書きされており、**現時点では「移行日以降は従来テーブルに中身が残らない」とは言えない** → プラットフォーム側 `responsesapi` スパンも Port 11 のライブで再測定し、二重書きだった(本節末の「再測定」欄)

**Agent 365 への送出(hosted agent のもう 1 つの送り先)**

- [configure-agent-365-data-collection](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/configure-agent-365-data-collection)(ms.date 2026-09-29)は、**hosting ライブラリ(`azure-ai-agentserver-core` / `agent-framework-foundry-hosting`)で作った hosted agent は、Foundry リソースの `a365LoggingEnabled` が `true` なら Agent 365 へトレースを自動で送る**と改めた(旧版は「Agent 365 SDK を自分で組み込まない限りデータは流れない」)。`a365LoggingEnabled` は Agent 365 が有効なテナントでは**既定 `true`**(リソース単位。プロジェクト・エージェント単位の上書きなし)で、実際の取り込みには Agent 365 ライセンスとテナント同意も要る
- 送られたデータは **Entra テナントの所在地(ジオ)基準で保存**され、Foundry のリージョン基準とは別になる([agent-365-integration](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-365-integration) ms.date 2026-08-26)。止めるのは `a365LoggingEnabled=false`(変更後に開始したセッションから。Azure Policy で一括拒否も可)
- ⚠ **公式間で食い違う:** agent-365-integration(2026-08-26 版)は hosted agent の送出を「明示的な構成(Agent 365 SDK)が必要」のまま。また**送られるトレースに会話の中身が入るかは公式に記載がない(要確認)**。案 3 で「中身を残さない」とするなら、App Insights を接続しないだけでなく **Agent 365 のデータ収集も止めておく**(閉域の Firewall 側の扱いは [07 §2](./07-usecase-regulated-edge.md#firewall-nsg-udr))

**選択肢**

| 案 | 構成 | 向く要件 | 得るもの | 失うもの・要る作業 |
| --- | --- | --- | --- | --- |
| **1. 集約(既定)** | 接続した App Insights 1 つに、プラットフォーム側とコンテナ側の両方が入る | PoC。運用担当が会話の中身を読んでよいと合意できている | 設定不要。ポータルのトレース画面・Conversation ビュー・Monitor ダッシュボード・継続評価がそのまま使える | **運用担当も中身を読める**(`AppGenAIContent` を保護しない限り)。~~両方が同じテーブル(AppDependencies 等)に入るので、テーブル単位の保護(Protected)では分けられない~~ → **2026-10-06 訂正:** 2026-09-30 以降は中身が `AppGenAIContent` に分かれるので、テーブル単位の保護で分けられる(= 案 4) |
| **2. 分離** | #1 = 接続先(中身入り。分析・評価用に閲覧者を絞り、Protected・短期保持)/ #2 = 別の App Insights(コンテナのログ。運用・アラート用) | 品質改善に中身を使いたいが、運用担当には見せたくない。**かつ中身を別リソースに置きたい**(保持期間・アクセス管理・課金をリソースごと分けたい、preview の保護機能に依存したくない) | 運用担当は中身を見ずに障害対応・アラートができ、分析担当だけが中身を見る | コンテナの OpenTelemetry 設定を自分で書く。#2 の接続文字列は**別の名前の環境変数**で渡す(プロジェクト接続の参照 `${{connections.<名前>.credentials.key}}` が使える)。注入変数は #1 を指し、公式は注入変数を再宣言しないよう書いているので上書きしない。ライブラリの自動送信(#1 行き)を残すか止めるかも決める |
| **3. 接続しない** | プラットフォーム側のトレースなし。コンテナのログだけを自前の接続文字列で運用向け App Insights へ | 「会話の中身をログに残さない」が必須(規制・社内規程) | 中身が App Insights に残らない(コンテナ側の記録をオフにしている限り)。**Agent 365 のデータ収集が有効なテナントでは `a365LoggingEnabled=false` も併せて設定する**(上記) | ポータルのトレース画面・Conversation ビュー、トレースを使う Monitor ダッシュボード・継続評価が使えない。モデル呼び出しの監視は §3.3 の Azure Monitor メトリクス(中身を含まない)で代替する。自前の送信設定を忘れるとコンテナのログがどこにも届かない([casebook P-H02](../casebook/02-pitfalls-index.md)) |
| **4. 同じ App Insights のまま中身だけ保護(2026-10-06 追加)** | 接続した App Insights 1 つ。中身(7 属性)は `AppGenAIContent` に入る(公式では 2026-09-30 以降の既定)ので、そのテーブルを **Protected** にし、**Privileged Monitoring Data Reader** を分析担当(と評価に使うプロジェクト MI)にだけ付ける。運用担当は Log Analytics Reader のまま | 品質改善に中身を使いたいが運用担当には見せたくない、かつ App Insights を増やしたくない。**(1) 早期フラグ `protectGenAISensitiveData` の登録か移行の完了で従来テーブルに本文が入らなくなっていること、(2) `AppGenAIContent` を Protected にすること、(3) Privileged Monitoring Data Reader を限定して付けること、(4) `gen_ai.*` 以外に本文を書く計装(MAF のメッセージイベント・自前ログ)を止めること、の 4 点がそろって初めて成立する** | 運用担当は中身以外(スパン構造・所要時間・エラー・トークン数)で障害対応できる。ポータルのトレース画面・Monitor ダッシュボード・継続評価もそのまま使える(読めない人には中身が伏せて表示)。コンテナ側は (4) の計装停止のほかは追加設定不要 | **保護の手順は preview** で、振り分け(既定)と違い自分で設定する。保護されるのは 7 属性だけ — **コンテナ側のマスクは引き続き必要**。トレース評価・継続評価・トレース→データセットは**プロジェクト MI にも Privileged Monitoring Data Reader が要る**(評価経由で中身に触れる経路が増える。評価の説明文 `gen_ai.evaluation.explanation` も保護対象)。2026-09-30 より前の取り込み分は既存テーブルに中身入りで残る。**2026-10-06 の実測(フラグ未登録)は従来テーブルとの二重書きで、この状態で Protected にしても従来テーブルの本文は通常のリーダーで読める → 採用前に従来テーブルに本文が残っていないことを KQL で確認する(`AppDependencies` で `isnotempty(Properties['gen_ai.input.messages'])` の行数が 0。`AppTraces` のメッセージイベントも同様に確認。移行の進み具合はリージョン・サブスクリプション・時期で変わりうるので受入試験と定期点検に入れる)。**opt-out フラグを登録していないことの確認。自作クエリの書き換え。テーブル単位で保持期間を分けられるかは未確認 |

**選び方(ヒアリングで決める — [proposal 01 の 4-7](../proposal/01-hearing-sheet.md#phase-4-セキュリティ・規制-15分))**

1. 会話の中身(利用者の入力・回答・参照した社内文書)を運用ログに残してよいか → 不可なら**案 3**(Agent 365 のデータ収集も止める)
2. 残すなら、誰が読めるか。運用担当と分析担当は同じ人たちか → 同じなら**案 1**。分けたいなら**まず案 4**(App Insights 1 つのまま、ロールで分ける。ただし上の 4 点がそろい、従来テーブルに本文が残っていないことを KQL で確認できた場合だけ。確認できないうちは案 2)。中身を別リソースに置きたい・preview の保護手順に依存したくないなら**案 2**
3. 保持期間と利用者への告知。公式は、有効化した後の告知・アクセス制御・保持期間を**顧客の責任**としている
4. 継続評価やトレースを使う評価を使うか → 使うなら案 1・2・4(案 3 では使えない)。案 4 ではプロジェクト MI に Privileged Monitoring Data Reader を付ける(§4.3)
5. **2026-09-30 より前から接続している環境か** → 移行日前の中身は既存テーブルに残り、保持期間が切れるまで Log Analytics Reader で読める。案 4 に移るなら旧データの保持期間・削除と opt-out フラグの有無を確認する(本ドキュメントの判断)

**業界の標準との関係:** OpenTelemetry の生成 AI 規約は中身の記録を**オプトイン(既定では記録しない)**とし、Microsoft の手順書も「本番では中身の記録を無効にする」「個人データは記録前にマスク・最小化する」とする。Foundry では**接続そのものがオプトインに当たり、接続すれば中身が入る**設計。2026-09-30 からの専用テーブル化は「記録はするが、読める人をテーブル単位で絞れる」方向への変更で、記録がオプトインになったわけではない(振り分けは既定、閲覧制限は設定次第)。委任アクセスと組み合わせると、利用者ごとに絞った中身がトレースの閲覧者には全部見える点に注意する([casebook P-O12](../casebook/02-pitfalls-index.md))。

**未検証:** 案 2・案 3 は公式の記述から組み立てた構成で、実測していない(注入変数とは別の接続文字列での送信、ライブラリの自動送信の止め方、Agent 365 への送出の有無とその中身)。「接続なしでは接続文字列が注入されない」は probe 10 で確認済み。案 4 は振り分け(二重書き)までは実測済みで、**早期フラグ登録後の挙動と、Protected 化で中身だけが伏せられることは未検証**(サブスクリプション全体の設定変更になるため)。

**再測定(2026-10-06 実施。Port 15 構成でのライブ再実施は保留 — Entra 側の作成・権限付与を伴うため):** 移行日(2026-09-30)以降に取り込んだ `responsesapi` スパンについて次を確認した。**クライアント側スパンの結果(2026-10-06 確定、japaneast、MAF 1.20、feature flag 未登録):** 本文は `AppDependencies` と `AppGenAIContent` に二重書き(`_MS.GenAIContentId` で対応、専用テーブルは約 5 分遅れ)、`AppTraces` にもメッセージイベント。下表は hosted agent のプラットフォーム側スパンについての再測定([Port 11 hn-briefing-hosted のライブ](../../../labs/maf-ports/ports/hn-briefing-hosted/README.md)、2026-10-06、japaneast、共有基盤 `aif-mafp1006`・App Insights 接続あり・feature flag 未登録)。

| 確認項目 | 結果 |
| --- | --- |
| (a) 既存テーブル(`AppDependencies` 等)の `gen_ai.input.messages` / `gen_ai.output.messages` が `AppGenAIContent` への参照値に置き換わっているか | **置き換わっていない。**プラットフォーム側(`responsesapi`)44 本・コンテナ側 44 本の GenAI スパンすべてで本文が `AppDependencies.Properties` の `gen_ai.*` に残り、同じスパンに `_MS.GenAIContentId`(参照)も付いていた = 二重書き |
| (b) 値が `AppGenAIContent` に入っているか(ツール結果を含む) | **入っていた。**同じ ID の行が `AppGenAIContent` にあり、プラットフォーム側 44 本は本文の長さも一致、26 本の入力にツール結果(HN の digest)まで含まれていた。取り込みの遅れは最大 4 秒(クライアント側の予備測定は約 5 分 — 遅れは一定でない) |
| (c) `AppGenAIContent` を Protected にした後、Log Analytics Reader だけの ID から中身が読めず、ポータルのトレース画面でも伏せられるか | **未実施。**(a) のとおり従来テーブルに本文が残るため、専用テーブルの保護だけでは本文は伏せられない。早期フラグ登録後の挙動はサブスクリプション全体の設定変更になるため未検証 |
| (d) コンテナ側(`azure-ai-agentserver-*`)のログ・スパンに、7 属性以外の形で中身が残っていないか | **残っていた。**コンテナの `AppTraces` に MAF の GenAI ログイベント(instructions・入力・出力)が 74 件、`_MS.GenAIContentId` なしで入っていた = 振り分けの対象外。中身を残さない設計ならコンテナ側のログイベントも止める必要がある |

---

## 4. 評価と LLMOps

### 4.1 評価器の選び方(公式の組み合わせ推奨)

- **RAG アプリ:** Retrieval + Groundedness + Relevance + Content Safety
- **エージェントアプリ:** Tool Call Accuracy + Task Adherence + Intent Resolution + Rubric + Content Safety。**2026-10-06 注記:** built-in-evaluators の現行版は推奨を **Output Quality + Tool Use Quality + Rubric + Content Safety** に置き換えた(下の合成評価器)
- 全アプリ共通でリスク・安全性評価器(Hate / Sexual / Violence / Self-Harm)を追加

**合成(composite)評価器(preview、2026-10 追加):** 複数の品質評価器を **1 回の LLM ジャッジ呼び出しにまとめる**評価器。`builtin.output_quality`(Fluency / Coherence / Intent Resolution / Task Adherence / Groundedness / Task Completion)と `builtin.tool_use_quality`(Tool Call Accuracy / Tool Call Success / Tool Input Accuracy / Tool Output Utilization / Tool Selection)の 2 種で、ターン単位・会話単位(`messages` を渡す)の両方に対応する。主結果は「該当する全コンポーネントが合格なら 1、1 つでも不合格なら 0」の 2 値で、どのコンポーネントが落ちたかは `<composite>_reason` / `_properties` に入る。ジャッジは **GPT-5.6 系を推奨**(最安は `gpt-5.6-luna`)([agent-evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators) / [built-in-evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators)、2026-10-06 確認。Tech Community「Evaluate More, Spend Less」2026-10-02)。**設計への効き方:** 評価コストとレイテンシ(ジャッジ呼び出し回数)が下がるので継続評価の `max_hourly_runs`(§3.5)に余裕が出る。一方、主結果が 2 値なので**本番ゲートの閾値は個別コンポーネントの値で決める**(本ドキュメントの判断)。

**評価レベル:** `turn`(既定)と `conversation` がある。**レベルの異なる評価器を同一 run に混在させられない。****2026-10-14 更新(公式間で食い違い):** cloud-evaluation-conversations(2026-10-07 版)・built-in-evaluators(10-08 公開)は「`messages` 形式なら異なるレベルの評価器を同じ run に混在でき、conversation レベルでは turn 専用評価器を**スキップ**する(run は失敗しない)」に変わった一方、troubleshooting(09-28 版)は「turn 専用評価器を conversation レベルで使うと incompatible evaluation level エラー」のまま。**CI のゲートでは「スキップされた評価器」を失敗として検出する仕組みを入れる**(スキップだと結果が欠けたまま合格しうる)。会話レベル対応は Output Quality / Tool Use Quality / Deflection Rate / Customer Satisfaction / Task Completion / Coherence / Groundedness の 7 種(`builtin.deflection_rate` はリファレンスに記載がなく要確認)。

**RAG 評価器の精度側と再現側:** Groundedness は**精度**(応答がコンテキストに沿っているか)、Response Completeness は**再現**(正解データを網羅しているか)を測る。検索パラメータのスイープに使えるのは **Document Retrieval**(正解ラベル必要、LLM 不要で NDCG / XDCG / fidelity を数値計算)。

### 4.2 ⚠ ツールによって使えない評価器がある

公式に明記:

> `tool_call_accuracy`、`tool input accuracy`、`tool_output_utilization`、`tool_call_success`、`groundedness` の各評価器は、**エージェントの会話に Azure AI Search / Bing Grounding / Bing Custom Search / SharePoint Grounding / Code Interpreter / Fabric Data Agent / Web Search への呼び出しが含まれる場合は使うな。**

完全サポートは **File Search / Function Tool / MCP / Knowledge-based MCP。**

**※2026-10-06:** 合成評価器 `builtin.tool_use_quality` / `builtin.output_quality` は上の制限対象の評価器(Tool Call Accuracy / Groundedness 等)をコンポーネントに含むが、公式は合成評価器について同じ制限を明記していない。**構成要素が同じなので同じ制限を受けると見て、上記ツールを使う会話には使わない**(本ドキュメントの判断。要確認)。

> **設計への含意:** 「Foundry Agent + Azure AI Search ツール」構成は、**エージェント評価のストーリーが File Search / MCP(= Foundry IQ)構成より弱い。**評価自動化が要件に入っているなら、この非対称性が RAG 方式の選定に効いてくる。

### 4.3 クラウド評価の実行

- **`azure-ai-projects>=2.2.0` + OpenAI 互換 evals API**(`client.evals.create`、評価器は `builtin.*` 名で指定)。**Entra ID 認証必須(キー不可)。**ドキュメントの最低要件は 2.2.0 のままだが、PyPI 最新は **2.7.0**(2026-09-18。2026-10-14 時点の最新は次項の 2.8.0)。**評価・データ生成ジョブの作成は Python / JS 2.4.0 で long-running operation 化**しており、作成直後に結果を読むコードはポーリング待ちへの書き換えが必要。2.5.0 以降は **Python 3.10+ / `openai>=3.0.0`** が前提(7・8 月号ブログ 2026-09-09)。
- **`azure-ai-projects` 2.8.0(2026-10-02、PyPI 公開 10-05):** changelog は **Agent Optimization API・データ生成ジョブ API・評価器のライフサイクル / 生成ジョブ API を GA** とし、トレース評価サンプルを GA の `azure_ai_trace_data_source` に、会話シミュレーション(`azure_ai_user_conversation_simulation`)を GA 扱いにした(SFT / RFT 向けのデータ生成シナリオは `_PREVIEW` 付きに改名)。一方 **GA 一覧表(2026-10-06 時点で 09-29 以降の更新なし)は Agent optimizer を Limited preview**、cloud-evaluation は会話単位の評価・トレース起点の評価をプレビューと書いたまま → **SDK の「GA」と GA 一覧表が食い違う(両論併記)。SLA の根拠には GA 一覧表を使う。**なお MAF の `agent-framework-foundry` 1.14 は `azure-ai-projects<2.8.0` を要求するので、MAF と同居する評価コードは 2.8.0 に上げられない(2026-10-06 確認。**2026-10-14 の 1.14.1 でも同じ上限**)
- **2026-10-14 更新 — Learn の機能ページからプレビュー表記が外れ始めた(GA 一覧表は不変):** Rubric 評価器(rubric-evaluators)・traces→dataset・合成データセット生成・会話データセット評価・会話シミュレーション、Agent optimizer の概要の h1 から「(preview)」とプレビュー定型文が消えた(いずれも「generally available」の明記はない)。一方 **GA 一覧表は updated_at 2026-09-23 のまま**(Convert traces to evaluation datasets = Preview / Agent optimizer = Limited preview)、built-in-evaluators の見出しも「Rubric evaluators (preview)」のまま。→ **SDK 2.8.0 = GA / Learn の機能ページ = ラベルなし / GA 一覧表 = Preview の 3 者併記**で、本書は GA 一覧表に従い**プレビュー扱いを維持**する(SLA を論点にする提案では GA 一覧表の改訂を待つ)。**トレース評価(deployed-conversations / deployed-interactions)は Learn でも preview** で、deployed-conversations(2026-10-07 版)は preview のトレース評価ワークフローに **`azure-ai-projects==2.7.0`(`@azure/ai-projects@2.7.0`)を固定**し `azure_ai_trace_data_source_preview` を使う。SDK 2.8.0 のサンプルは GA の `azure_ai_trace_data_source` に移行済みなので、**同じプロジェクトで「2.8.0 の GA 型」と「2.7.0 固定の preview 手順」が混在しうる** → 評価パイプラインはワークフローごとに版を分けて固定するか、SDK リポジトリのサンプルを正とする。トレース評価の時間窓は 15 分以上(会話の両端に 5 分の非アクティブ緩衝)。合成シード(Simulation seed)は 2.8.0 では作れずポータル必須。Quality Grader は deprecated で評価に使えない(built-in-evaluators の一覧は「(preview)」のままでページ間不一致)
- **評価の権限(2026-09-29 新設の [evaluation-permissions](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluation-permissions)):** 基本は実行する ID(本人・CI のワークロード ID)に **Foundry User**。ただし**モデルを呼ぶ評価は Foundry User を Foundry アカウントのスコープで**付ける(プロジェクトだけの割り当てではモデル推論が認可されない)。継続・定期評価ルールはプロジェクト MI に Foundry User(§3.5)。**トレース評価・トレース→データセット生成はプロジェクト MI に接続先 App Insights の Reader**、Log Analytics ワークスペースが「Require workspace permissions」なら MI に Log Analytics Reader(DataActionsOnly モードなら Log Analytics Data Reader)、**保護テーブル(`AppGenAIContent` を Protected にした場合 — §3.6 案 4)を読むなら MI に Privileged Monitoring Data Reader も**。BYO ストレージを Entra 接続するなら MI に Storage Blob Data Contributor。**閉域・最小権限の案件では「人の閲覧権限」と別に「プロジェクト MI の読み取り権限」を設計項目に入れる**
- 上限: **1 行あたり最大 2MB / バッチ評価あたり最大 100,000 行。**評価 run 作成はテナント / サブスクリプション / プロジェクトの各レベルでレート制限され、超過時は `retry-after` 付きで返る(**指数バックオフ必須**)。
- シナリオは 2026-08〜09 に「評価単位(個別ターン / 会話全体)× 出発点」で再編された([cloud-evaluation](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/cloud-evaluation) 2026-09-07 更新): **個別ターン** = 既存データセット評価(GA)/ モデル・エージェントのターゲット評価(GA)/ デプロイ済みインタラクション評価(GA。ただしトレース起点の評価はプレビュー)/ 合成クエリ生成(プレビュー)、**会話全体** = 会話データセット評価(プレビュー)/ デプロイ済み会話評価(プレビュー)/ 会話シミュレーション(プレビュー)。**会話単位の評価はいまもすべてプレビュー**なので、マルチターン品質を本番ゲートにするなら SLA なしを前提にする(2026-10-14: 会話データセット評価・会話シミュレーションは Learn のページからプレビュー表記が外れたが、GA 一覧表は未改訂なので本書はプレビュー扱いのまま — 上の 3 者併記)。
- **`azure-ai-evaluation` はローカル評価専用。**クラウド / バッチ評価は `azure-ai-projects` を使う。
- **⚠ ルーブリック評価器(`score_model`)は `pass_threshold` が実質必須([実測] [Port 9 critique-loop](../../../labs/maf-ports/ports/critique-loop/README.md)、2026-10-06):** 省略するとサービスが 0.0 とみなし、`pass_threshold 0.0 must be within range [1.0, 5.0]` で **run 全体が失敗**する。SDK は省略を許し、提出時・`--dry-run` ではエラーにならず、run のエラーを読んで初めて分かる(3.0 を設定してルーブリック込みのクラウド評価が完走: 50 秒・ジャッジ 15 回・約 5.5 万トークン)。CI の評価ゲートでは評価器定義のスキーマ検証を自前で入れる。評価器カタログ(`project.evaluators`)は SDK 2.8.0 changelog が GA、Learn は preview で食い違う。**2026-10-14 注記:** ここでの「ルーブリック」は openai ネイティブの `score_model` グレーダーに自由記述のルーブリックを書いたもので、**Foundry の Rubric 評価器(生成型)とは別物**。Rubric 評価器は各次元 1〜5 の加重平均を **0〜1 に正規化**し、**合格閾値は 0.0〜1.0・既定 0.5**(rubric-evaluators 2026-09-30 版)で、`score_model` の [1.0, 5.0] とは尺度が違う。両方を CI ゲートに使うなら閾値の尺度を取り違えない。
- **継続評価(§3.5)が効く条件([実測] [probe 09](../../../labs/foundry-probes/probes/09-continuous-eval/NOTES.md)、2026-10-06):** ①**`sampling_rate` は百分率**で、`1.0` は 1%(全件なら 100)— 08-04 以来「自動ランが出ない」としていた真因はこの誤り ②**prompt agent をプロジェクトの Responses API + `agent_reference` で呼んだ応答**には 1 応答 = 1 ランが 16 秒以内に作られ completed になる ③**エージェントエンドポイント経由(公開エンドポイント)の応答は、ランは作られるが failed**(AOAI 404「Response … not found」)④結果は `evals.runs.list` / `output_items` で SDK から取れる。`builtin.violence` は japaneast で errored(原因未確認)。**本番の呼び出し経路がエージェントエンドポイント(Teams / M365・A2A・hosted の公開エンドポイント)なら、継続評価は現状そのままでは効かない前提で、トレース評価やバッチ評価で代替する**(本ドキュメントの判断)

### 4.4 リージョン制約(日本の案件で必ず効く)

| 機能 | 対応リージョン |
|---|---|
| バッチ評価 | 広範(**Japan East / Japan West を含む**) |
| **リスク・安全性評価器** | **22 リージョンに拡大**(米州 11: Brazil South / Canada Central / Canada East / Central US / East US / East US 2 / North Central US / South Central US / West Central US / West US / West US 3、欧州 10: France Central / Germany West Central / Italy North / Norway East / Poland Central / Spain Central / Sweden Central / Switzerland North / Switzerland West / West Europe、APAC は **Australia East のみ**)。**日本は依然非対応**(evaluation-regions-limits-virtual-network 2026-08-18 更新で確認。旧記載の 6 リージョンから拡大) |
| Groundedness Pro | East US 2 / Sweden Central のみ |
| Protected material | **East US 2 のみ** |
| **AI Red Teaming** | **公式2ページ間で記載が揺れる**(evaluation-regions-limits-virtual-network は East US 2 / North Central US の 2 リージョン、ai-red-teaming-agent は +France Central / Sweden Central / Switzerland West の 5 リージョン)。**いずれにせよ日本・APAC 非対応** |
| Agent playground 評価 | 米国 8 + 欧州 7 リージョン(**APAC なし**) |
| 合成データ生成 / トレース→データセット生成 | 広範(**Japan East・Japan West を含む**。2026-10-01 版で Japan West・Korea Central・Southeast Asia 等が追加 — 旧記載「Japan West は含まない」は更新) |

> **設計への含意:** 本番推論は Japan East、**安全性評価と Red Teaming は別リージョンの評価専用プロジェクト**という分離構成になる。**プロンプト・応答が評価のために国外に渡る**ため、法務確認が必須。評価だけなら Agent 用のフル構成(Cosmos DB / AI Search / capability host)は不要で、評価専用の Bicep テンプレートが用意されている。

### 4.5 AI Red Teaming Agent

PyRIT ベース。**Attack Success Rate = 成功攻撃数 ÷ 総攻撃数**を算出する。

- **エージェント固有リスク(クラウドのみ):** Prohibited actions(禁止 / 高リスク / 不可逆アクション)、Sensitive data leakage、Task adherence。
- **XPIA(間接プロンプトインジェクション):** メールや文書などツール経由の外部データに悪意ある指示を埋め込み、エージェントが不正実行するかを検証。攻撃戦略に `Indirect Jailbreak` がある。
- **サポート対象:** hosted prompt agent / hosted container agent は対応。**workflow エージェント・非 Foundry エージェント・Function tool 呼び出し・Browser automation・Connected Agent・Computer Use は非対応。**
- **既知の限界:** 合成データのため実データ分布を代表しない、**生成モデルで ASR を判定するため非決定的で偽陽性がありうる(対処前に必ずレビュー)。**
- **「purple environment」(本番相当リソースの非本番環境)での実行を推奨。**

---

## 5. コストアーキテクチャ

### 5.1 何に課金されるか

| 要素 | 課金 |
|---|---|
| モデルトークン | 入力 / 出力 / キャッシュ読取(**gpt-5.6 以降はキャッシュ書込も**) |
| **Foundry Agent Service 本体** | **プロンプトとワークフローを使う Foundry ネイティブエージェントの作成・実行に追加課金はない** |
| **Hosted agents** | **vCPU 時間 + メモリ GiB 時間** |
| File Search ストレージ | **ベクトルストレージ GB/日**(1 GB 無料) |
| Code Interpreter | **セッション単位** |
| Web Search / Custom Search | **1,000 トランザクション単位** |
| Logic Apps コネクタ / Fabric data agent / SharePoint / Bing grounding / Foundry IQ | いずれも別課金 |
| Cosmos DB / Storage / AI Search | 各サービスの通常課金 |
| Application Insights / Log Analytics | 取込データ量と保持設定。**Foundry 側の上乗せなし** |
| **Foundry Observability** | **課金対象は safety / red teaming / playground 評価のみ。**品質評価と継続的評価は自分のモデルデプロイのトークン課金のみ。**モニタリングとトレーシングは無料** |
| ファインチューニング | Training + **Hosting(デプロイ中は未使用でも時間課金)** + Inference |

**⚠ 見落としがちな課金:**
- **ファインチューニング済みモデルのホスティング料は未使用でも発生する。**
- **Agents playground の評価は全 Foundry プロジェクトで既定 ON。**停止するには playground の metrics から全評価器を選択解除する必要がある。
- **PTU は削除するまで課金が止まらない**(一時停止不可)。

**⚠ 実単価が公開されていない:** Foundry Agent Service / Foundry Observability の公開料金ページは**メーター名と単位のみで金額が `$-` プレースホルダ。**見積時は Azure 料金計算ツールにサインインするか営業経由で取得する必要がある。**Foundry は料金計算ツールに専用ページを持たない**(複数のオプションサービスの組合せのため)。

### 5.2 FinOps レバー

| レバー | 効果 |
|---|---|
| **Batch API** | Global Standard 比 **50% 割引** |
| **Prompt caching** | Provisioned は最大 100% 割引。**サイジング例で必要 PTU 110 → 80(-27%)**(GPT-6 系の normalized token モデルはキャッシュも PTU を消費するので効きが小さい — §1.3) |
| **Model router** | Balanced モードで品質 1〜2% 以内、Cost モードで 5〜6% 帯の最安モデルを選択(2026-10-14: 既定プールに Fireworks 3 モデル〈Microsoft 施設外・US のみ〉と Grok が入った。データ所在要件があるなら custom subset で絞る — [07](./07-usecase-regulated-edge.md)) |
| **Flex processing(preview、2026-10-14 追加)** | Global Standard への要求単位で `service_tier: "flex"` を指定すると Standard 比 **50% 割引**。専用デプロイ不要・同期応答。**latency / service SLA なし**、Global Standard のみ。対象は 2026-10-12 版で 7 モデル(GPT-6.1 Sol / GPT-6 Sol・Luna・Astra / GPT-5.6 Sol・Luna・Terra。旧: 5.6 Sol のみ)。Batch の 24 時間を待てない非対話処理の選択肢([08 E3](./08-usecase-specialized.md#e3-大量バッチ処理)) |
| **PTU Reservations** | 1 か月 / 1 年コミットで時間課金より割引(**割引率は公開ドキュメントに記載なし**) |
| **Spillover** | PTU 使用率を最大化(バースト分だけ Standard へ) |
| **小型モデル** | gpt-4.1-nano は PTU 効率が gpt-4.1 の約 20 倍 |
| **APIM セマンティックキャッシュ** | 近傍プロンプトの応答再利用で**バックエンド呼び出し自体を削減** |
| **APIM `llm-token-limit`** | `estimate-prompt-tokens=true` で**上限超過プロンプトをバックエンド到達前に遮断** |

### 5.3 ショーバック / チャージバック

- **プロジェクト単位の配賦(プレビュー):** 全 Foundry プロジェクトの使用量に**自動的に `project` タグが付く**(手動タグ付け不要)。Cost analysis で Tag フィルタを使う。**⚠ Models sold by Azure のみ対応で、Azure Marketplace 経由のモデルは未対応。**
- **メーターの見え方の罠:** Cost Analysis のサービスフィルタに「Azure OpenAI」は無い(Cognitive Services 分類の下の Service tier で絞る)。**パートナー / コミュニティモデルのメーターは Foundry リソースではなくリソースグループ配下に出る**ため、**Cost Analysis はリソースグループスコープにする。**
- **概算値と実請求はズレる:** ポータルの Estimated cost は**割引や契約価格を反映せず、Provisioned(PTU)も含まない。**課金イベントが Cost Analysis に現れるまで**取り込みタイミングにより遅延がある**(公式は具体的な時間を明示していない。分単位の比較ではなくトレンドで照合する)。財務照合には Cost Management と請求書を使う。**さらに prompt agent と非 Foundry エージェントのコストは Overview の概算に含まれない。**
- **⚠ ハードリミットが無い:** 「OpenAI にはハードリミットがあるが、**Azure OpenAI には現状その機能がない**」。予算超過での自動停止が要件なら、予算アラートのアクショングループから起動する**自動化を自作する必要がある。**
- **消費者別の粒度が要るなら APIM。**`llm-emit-token-metric` のディメンション(既定8種: API ID / Operation ID / Product ID / User ID / Subscription ID / Location / Gateway ID / Backend ID。テナント ID 等はカスタムディメンション〈最大5個〉で追加)を付ければ、Foundry が提供しない粒度でチャージバックできる。

### 5.4 PTU Reservations の注意点

- **デプロイ種別ごとに別購入**(Global / Data Zone / Regional は相互流用不可)。**Global 予約はリージョン非依存**で、複数リージョンの Global PTU デプロイを 1 つの予約でカバーできる。
- マッチング条件は「**デプロイ種別 × リージョン × スコープ**」の 3 つで、**モデルやデプロイ ID では一致させない**(モデル非依存なので新モデル追加時も自動的にカバーされる)。
- **予約はキャパシティを保証しない。必ずデプロイを先に作ってから予約を買う。**
- **余剰予約は失効し翌期に繰り越されない**(24×7 稼働前提の価格)。
- **デプロイを削除しても予約は自動解約されない。**
- **⚠ ドキュメント間の食い違い:** デプロイ種別間の交換について、Reservations 側は可能と読め、provisioned-throughput-billing 側は不可と明記している。**実行前にサポート確認を推奨。**

---

## 6. プラットフォーム自体の CI/CD

### 6.1 環境分離

**公式指針:** 「実験・テスト・本番の環境を計画するとき、**依存リソースを含めて Foundry リソースを明確に分離せよ。**」つまりプロジェクト分割ではなく**リソースごと分離**する。

**プロジェクトは共有 / 分離の単位:** 「同一プロジェクト内の全エージェントは同じファイルストレージ・スレッドストレージ・検索インデックスにアクセスする。データはプロジェクト間で分離される。**プロジェクトが現時点での共有と分離の単位である。**」

**⚠ プロジェクト RBAC の限界:** 「Foundry プロジェクトに **Foundry User** ロールを持つプリンシパルは、**そのプロジェクト内のすべてのエージェントと対話できる。**」どのユーザーがどのエージェント / 会話にアクセスできるかを制御するのは Foundry の RBAC ではなく**自社アプリの認証認可層。**

### 6.2 移植できるもの / できないもの

| 移植できる | 移植できない / 手動 |
|---|---|
| エージェント定義・接続・システムプロンプト・パラメータ(**as code で管理していれば**) | **capabilityHost(更新不可)** |
| モデルデプロイ(IaC で再作成) | Foundry プロジェクトのサービス側メタデータ(タグ・アセット名・説明) |
| Bicep 化した接続、共有 Key Vault | 会話スレッドと添付ファイル |
| geo-replication 済み ACR イメージ | AI Search インデックス(再構築のみ) |
| リージョンを跨いで参照可能な Storage 接続 | Application Insights(リージョンごとに作成) |

> **⚠ capabilityHost は作成後に更新できない**(`400 BadRequest`)。構成変更は **capability host の削除・再作成**で行う(プロジェクト削除は不要。同名+異構成での再作成は 400 になる。 https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/capability-hosts )。**IaC の冪等更新が効かない最大のポイント**で、パイプラインは「capability host の作り直し」を前提に設計する。
>
> **2026-09-26 追記:** 後継として **capability settings(プレビュー、API `2026-07-15-preview`)** が追加され、capability-hosts ページは「参考として保持」扱いになった(configure-capability-settings ms.date 2026-09-22)。アカウント / プロジェクトの `capabilitySettings`(`documentStore` / `vectorStore` / `blobStore`)で宣言し、プロジェクトはアカウント既定を継承・個別上書きする。**提供は UK South / Canada Central のみの段階展開**で日本リージョンは当面 capability host(後方互換フロー)。**capability settings も既存プロジェクトへの追加・更新は不可(プロジェクトの削除・再作成)**なので、「作り直し前提」の設計原則は変わらない。プロビジョニングは呼び出し元 ID(CI/CD の SP 等)で行われ、Storage Blob Data Contributor / Cosmos DB Operator が必要。
>
> **2026-10-14 更新:** (1) **要確認 — 設定ページ(configure-capability-settings)は 301 で agents/environment-setup に転送され、転送先に capability settings の記述がない**。capability-hosts・standard-agent-setup・virtual-networks は旧 URL を参照したまま capability settings を前提に書かれ、create-resource-terraform(10-09 版)の対応表は「Configure capability host for bring-your-own-resources」行を復活させた。取り下げか移設中かは判断できないので、パイプラインは capability host 前提のまま組む。(2) 上の「呼び出し元 ID がプロビジョニング」は **ARM REST / Bicep で capability settings を送る経路だけ**の話で、virtual-networks の現行版は「**ポータルと旧 capability host 経路は引き続きプロジェクト MI がプロビジョニング**」「実行時に BYO リソースへ届くのはどちらでもプロジェクト MI」と経路を区別した(旧記載は capability settings の設定ページだけに基づいており、経路の区別がなかった)→ CI/CD の SP に BYO リソースのデータロールを付けるかは、どの経路で作るかで決める

### 6.3 エージェントのバージョニングとリリース

- **Foundry はイミュータブルなエージェントバージョンをネイティブサポートする。**定義を変更するたびにバージョンスナップショットが作られ、監査証跡とロールバック先になる。hosted agent のロールバックは**エンドポイントのバージョンセレクタを過去バージョンに向け直すだけ**(リビルド不要)。
- **Structured inputs** でエージェント定義をパラメータ化でき、1 バージョンでユーザー別 / 文脈別の構成を再デプロイなしに提供できる。**⚠ ただし instruction テキストに限定すべき。**MCP サーバー URL などツールエンドポイントをテンプレート化すると、呼び出し側が実行時に任意の外部サービスへエージェントをリダイレクトでき、静的ガバナンスが崩れる。
- **⚠ カナリア / ブルーグリーンは組み込み機能がない:**
  > Foundry はエージェントの blue-green / canary デプロイの組み込みサポートを提供しない。これらのデプロイパターンや、ユーザーのエージェントバージョン間の制御された移行が必要なら、**エージェント API の前段に API ゲートウェイやカスタムルーターのようなルーティング層を実装せよ。**
  - **トラフィック分割は prompt agent を含め全エージェントで非対応。**`version_selector` の `FixedRatio` ルールは `traffic_percentage: 100` の 1 本だけを設定する仕様で、ルーティングは「Always use latest(既定)」か「特定バージョンに固定」の 2 択([configure-agent](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/configure-agent) ms.date 2026-09-11 の Limitations に「No traffic splitting」、[manage-hosted-agent](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/manage-hosted-agent) ms.date 2026-08-17 も同旨。旧記載「prompt agent は FixedRatio で % 指定可」は誤り)。**既定の Always use latest ではバージョン作成と同時に本番(Teams / M365 公開先を含む)に反映される**ので、本番はバージョン固定にしておく。
  - **2026-10-06 注記 — 公式間不整合(hosted agent のカナリア):** 新設の [deploy-hosted-agent-production](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent-production)(preview、ms.date 2026-09-21、2026-09-30 公開)は、`azure.yaml` の `agentEndpoint.versionSelector` に `FixedRatio` を 2 本(stable 90 / candidate 10 → 50/50 → candidate 100)書き、`azd ai agent endpoint update` で**同一エンドポイントのカナリア**を行う手順を載せた(失敗時は stable 100 に戻す。`--version` 指定の新しいセッションで候補を個別テスト)。同時期の manage-hosted-agent(ms.date 2026-09-16)は「Traffic splitting between agent versions isn't supported. Configure one `FixedRatio` rule … 100」、configure-agent の Limitations も「No traffic splitting」のまま。**未実測。提案では「分割不可」を前提に置き(必要ならルーティング層を前段に用意)、カナリアを使うなら検証用プロジェクトで 2 本の `FixedRatio` が受け付けられ実際に配分されることを実測してから採用する**(本ドキュメントの判断)。同ページは配分中に始まった会話がどちらの版に束縛されるかには触れていない
  - hosted agent には**ドラフトバージョン(プレビュー)**があり、`draft-{timestamp}` 版は latest 解決にもルーティング対象にもならないため、本番に影響させずに新イメージ・構成を直接呼び出して検証できる(昇格はドラフトを外して新バージョンを作成)。
- **公式の本番リリース手順(2026-10-06 追加 — [manage-hosted-agent「Release a version without changing production」](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/manage-hosted-agent#release-a-version-without-changing-production) ms.date 2026-09-16):** 既定のルーティングは latest 追従なので、**候補版を作る前に production を具体版へピン留めしないと、版の作成がそのまま本番の変更になる**。デプロイと昇格を分ける次の 6 段階が公式手順で、azd の CI/CD([set-up-ci-cd-cli](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/set-up-ci-cd-cli) ms.date 2026-09-23)と Terraform([deploy-hosted-agent-terraform](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent-terraform) ms.date 2026-09-23)の両方がここを参照する:
  1. **記録とピン留め:** 現在 production が出している版を記録し、その具体版に `FixedRatio` 1 本・100% で固定する。版 ID とコンテナイメージをロールバック用に保持する
  2. **候補の作成:** production のセレクタを変えずに新しいイメージ・構成をデプロイし、候補の具体的な版 ID を控える(テスト後や承認待ちの間に `latest` を引き直さない)。**azd は `azd deploy` 時に構成済みのエンドポイント設定とフックを適用するので、ピンを上書きしないか確認する。**Terraform の state lock は別の API クライアントによる版作成を止めないので、書き手を 1 つに揃える
  3. **準備完了と同一性の確認:** 候補の status が `active` になるのを待ち、イメージと構成が出そうとしている成果物と一致するか確かめる。失敗・タイムアウト・想定外の候補なら production を変えずに中止する
  4. **候補専用セッションでテスト:** `version_indicator`(`type: version_ref`、`agent_version` = 候補)で**新しいセッション**を作り、その ID で呼ぶ(Responses は本文の `agent_session_id`、Invocations はクエリの `agent_session_id`)。プロトコルの完了と期待した応答内容を確認し、「ログが出た」「接続できた」だけを合格にしない
  5. **承認と昇格:** 昇格直前に、候補がまだ `active` で production が記録した版のままかを再確認する(別のリリースが変えていたら止めて調整)。セレクタを候補 100% に更新し、プロトコル・認可の設定は保持する
  6. **本番の確認とロールバックの保持:** 版指定なしの新しいセッションで選んだ版が使われることを確認する。本番チェックで失敗したら直前の具体版に戻し、新しいセッションで再確認する
  - **実装例(2026-10-06):** maf-ports の Port 11 [hn-briefing-hosted](../../../labs/maf-ports/ports/hn-briefing-hosted/README.md) のデプロイスクリプトに `--candidate`(production が具体版に固定されていなければ現行版へピン留め → 候補作成 → `version_ref` の候補専用セッションで試験 → production のセレクタが動いていないことを確認)と `--promote <版>`(`active` の版にだけ切り替え。ロールバックも同じ操作)を実装した。ルーティング更新はプロトコル・認可の設定を保持してセレクタだけを差し替える(作り直すと他の設定が消える)
- **同節の明記事項:** 「**既存セッションは作成時の版に束縛され、エンドポイントのセレクタを変えても移行しない**」「セッションやロールバック要件が依存している間は旧版とイメージを残す」「**エージェントや版の削除はロールバック操作ではない**」と明記している(次項のとおり、実測では構成によって食い違った)。**2026-10-14 注記:** invoke-hosted-agent(ms.date 2026-10-13)も「sessions are bound to a version when they're created」を理由に `azd ai agent invoke` の `--version` と `--session-id` の併用を禁じており、公式側の記述は一貫して「束縛」。休止明けの挙動に触れたページはなく、両論は解消していない。手順全体に `[TO VERIFY]`(公開前に全ツールで通しの検証をする旨の執筆者コメント)が残っており、手順自体もまだ固まりきっていない
- **hosted agent の版を更新しても、会話は続けられる。ただし「既存の会話にどの版が答えるか」は 2026-10-06 の実測で構成によって割れた([probe 10](../../../labs/foundry-probes/probes/10-hosted-version-continuity/NOTES.md) 2026-09-30・2026-10-06 / [Port 11](../../../labs/maf-ports/ports/hn-briefing-hosted/README.md) 2026-10-06)。**会話履歴はエージェント+利用者の単位で保存され、どの版からも読める(両方の実測で一致)。
  - **起動中**のセッション(最後のアクセスから idle_timeout 以内。既定 15 分)は、ルーティングを新版に切り替えても**作成時の版のまま**応答する — 公式・probe 10・Port 11 の 3 者で一致。ロールバックも起動中の会話には効かない
  - **新しい会話**は切り替えた時点の版で始まる(3 者で一致。公式の本番リリース手順は新しい会話にはそのまま効く)
  - **休止(idle_timeout の経過、または `stop_session`)の後の次のターン**が割れた(下表)

| 構成 | `stop_session` 後 | idle 明け | `version_ref` で旧版に固定したセッションの休止明け | 休止中にロールバックした後 |
| --- | --- | --- | --- | --- |
| **公式**(manage-hosted-agent 2026-09-16「既存セッションは作成時の版に束縛され、セレクタを変えても移行しない」/ manage-hosted-sessions 2026-08-21「版を固定すると新しい版を公開してもその版を使い続ける」) | 作成時の版 | 作成時の版 | 固定した版 | (記載なし) |
| **[実測] Port 11**(MAF `agent-framework-foundry-hosting` 1.0.0b261002 の `ResponsesHostServer`、2026-10-06) | **作成時の版(v1)** | **作成時の版(v1、約 15 分明け)** | — | — |
| **[実測] probe 10**(Agent Server SDK 2.2.0 だけの最小エージェント、コードデプロイ、2026-09-30・2026-10-06 の計 3 回) | **現行セレクタの版(v2)** | **現行セレクタの版(idle_timeout 120 秒・900 秒とも)** | **現行セレクタの版**(固定が効かない) | **戻した版(v1)** |

- **割れた原因の切り分け(2026-10-06):** 同じ日・同じリージョン(japaneast)・同じ SDK(`azure-ai-projects` 2.8.0)で、クライアント SDK の版(2.7 / 2.8 で要求の形が同じ)と切り替え API の形(セレクタだけ差し替える方式でも probe 10 は同じ結果)は原因から外れた。**残る差はコンテナの実装**(ホスティングライブラリ。b261002 は永続・サンドボックス分離セッションを導入した版)とリソースサイズ・基盤で、**未切り分け**。どの構成でも、同じセッション ID のまま履歴と `$HOME` は引き継がれた
- **版の判定と周辺の実測(2026-10-06):**
  - **応答の `agent_reference.version` は「答えた版」ではなく「その時点のセレクタの版」**(Port 11: v1 のコンテナが答えた応答にも `"2"`)→ 版の判定はセッションの `version_indicator`(`get_session`)か、コンテナ側スパンの `gen_ai.agent.version` / `AppRoleInstance` で行う
  - **`get_session` の `status` は休止を即時に反映しない**(idle 経過の 180 秒後も `active` のまま次のターンでコンテナが起動し直した — probe 10)→ 休止の判定に `status` を使わない
  - **同じ zip・定義を再デプロイしても新しい版は作られず、既存の版が返る**(`create_version_from_code` — Port 11)→ パイプラインは「候補の版 = 本番の版」なら止める判定を入れる(公式 6 段階の 3 段目「想定外の候補」に当たる)
  - **エンドポイント設定にはサーバー側で `authorization_schemes: [{type: Entra}]` が入る**ので、セレクタの更新は他の設定を保ってセレクタだけを差し替える(作り直すと消える — Port 11)
  - 所要の目安(Port 11): 新しい会話 12.7〜13.8 秒 / 起動中セッションの短い続き 4.2〜4.4 秒 / `stop_session` 後の再開 11.1 秒 / 版のプロビジョニング 1〜2 分
  - **旧版の削除は、結び付いたセッションが残っていると 409**(休止中もセッションの有効期限 30 日まで)。`force=true` で削除すると、次のターンで同じセッション ID のまま現行版に作り直され、履歴も `$HOME` も残った(probe 10、2026-09-30。公式は「版の削除はロールバック操作ではない」とする)
  - 新版に明示固定したセッション(`create_session(version_indicator=...)`)の ID を渡せば、起動中の会話もすぐ新版へ移せる(履歴は引き継ぎ、`$HOME` は引き継がない — probe 10、2026-09-30)
  - 一方、**別の agent の response ID は 404**(利用者の分離は公式の仕様、agent 単位の分離は [Port 15](../../../labs/maf-ports/ports/delegated-access-hosted/README.md) の実測)。前段のルーターで**別の agent に切り替える blue-green は、会話を引き継げない**前提で設計する
- **リリース手順の型(hosted agent。2026-10-06 改訂):** **基本は上の公式 6 段階**(ピン留め → 候補を版固定セッションで検証 → 昇格 → 新しいセッションで確認)。新しい会話は昇格の時点から新版になる。**既存の会話が休止後にどの版で再開するかは構成で割れる**ので、公式の記述を前提にせず、どちらでも困らないように組む:
  - **受入試験に「`stop_session` 後」「idle 明け」「休止中のロールバック後」に既存の会話がどの版で答えるかを入れ、自分の構成(ホスティングライブラリ・デプロイ方式)で確かめる。**判定は `version_indicator` かコンテナ側スパン(`agent_reference.version` は使わない)。公式の記述が直される・挙動が変わる可能性もあるので、版更新のたびに確認する
  - **通常の改修:** 既存の会話が旧版のまま続いても、休止明けに新版へ移っても困らない改修なら、昇格だけでよい
  - **旧版で会話を最後まで続けさせたい場合**(新版が旧版の会話履歴・`$HOME` の形式と互換がない等): セレクタの切り替えでは保証できない(probe 10 の構成では休止すると新版で再開する)→ **エージェント名を分ける**(新しい会話は新しいエージェントで始め、旧エージェントは既存の会話が終わるまで残す。会話は agent をまたいで引き継げない)
  - **すべての会話をすぐ新版へ移したい修正**(権限・業務ルールの不具合など)と**問題の版からの緊急退避:** 第一手は**中間層で新版に固定した新しいセッションを作って渡す**(`version_ref` でのセッション作成は公式手順の部品)。`stop_session` は probe 10 の構成では次のターンで現行の版に作り直させたが、**Port 11(MAF ホスティング)では `stop_session` 後も旧版のままだった** → 移行手段に使うなら自分の構成で効くことを先に確かめる。旧版の `force=true` 削除は、公式がロールバック手段と位置づけていない最後の手段(旧記載「緊急退避は `force=true` で削除」を第一手から格下げ)
  - 新版は旧版が書いた履歴と `$HOME` を読むので、ツール呼び出しの形式やファイル形式を変える版は後方互換を持たせる。受入試験に「更新前に始めた会話の続き」「ロールバック後の続き」「(使うなら)旧版削除後の続き」も入れる
  - **用語の注意:** Foundry の「セッション」はサンドボックス(コンテナ+`$HOME`)で、会話(履歴)とは別物。休止しても**別のセッションにはならず**、同じセッション ID(最長 30 日)のままコンテナだけが止まる。次の発言で起動し直すときの版が、probe 10 の構成では現行の版、Port 11・公式では作成時の版だった(Copilot Studio・AgentCore の「セッションが終わり、新しいセッションから新版」とはどちらも違う)
  - **切り替わる時点の例(probe 10 の構成のように休止明けに移る場合。idle_timeout 15 分):** 10:10 に修正版へ切り替えたとき、10:00 から 5 分おきに話し続けている利用者は**旧版のまま**(15 分以上の間が空いた後の発言から新版)、9:50 以来 30 分ぶりに戻った利用者と新しく始めた利用者は新版。**Port 11・公式のように束縛される場合は、既存の会話はセッションの有効期限(最長 30 日)まで旧版**で、新版になるのは新しく始めた会話だけ
  - **コードを直しても、会話履歴に残った誤りは消えない。**旧版が出した誤った回答・ツール結果は履歴に残り、新版はそれを文脈として読む。影響の大きいバグでは、対象の利用者に新しい会話を始めてもらうか、新版側で旧版の出力を含む会話を検知して注意を促す
- **他製品の例(2026-09-30 確認):** Copilot Studio は「進行中の会話を妨げないよう、公開した内容は新しいセッションから有効」(多くのチャネルは 30 分無操作でセッション終了、Teams は `start over` か公開から最大 1 時間)([publish channels](https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-fundamentals-publish-channels) ms.date 2026-09-16)。AWS AgentCore Runtime は既存セッションが旧版のスナップショットで終了まで続く(15 分無操作・最長 8 時間)([runtime how it works](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html))。LangGraph は再デプロイした最新の graph を既存スレッドにもすぐ適用し、状態スキーマの後方互換を利用者側に求める([backward compatibility](https://docs.langchain.com/oss/python/langgraph/backward-compatibility))。Foundry hosted agent は、**probe 10 の構成では「休止の切れ目で新版」、Port 11・公式では「セッション(最長 30 日)が続く限り旧版」**で、どちらでも**履歴と `$HOME` が切れ目を越えて残る**点が他製品と違う
- **モデルデプロイの version upgrade を自動アップグレードにしない**(テストスイート検証前に応答が変わるのを防ぐ)。
- **非決定性への対処:** 「Foundry Agent Service で定義したエージェントは非決定的に振る舞うため、望ましい品質水準をどう測り維持するかを決めなければならない。**現実的なユーザーの質問とシナリオに対する理想的な応答をチェックするテストスイートを作って実行せよ。**」→ §4 のクラウド評価を CI のゲートに組み込む形になる。

### 6.4 IaC

- **Bicep テンプレート集:** `microsoft-foundry/foundry-samples` の `infrastructure/infrastructure-setup-bicep/` に番号付きシナリオ(private network basic / standard agent setup / APIM 併用 / managed VNet / 評価専用など)。既存リソースの ARM Resource ID を渡して再利用できる。
- 主要リソース種別: `Microsoft.CognitiveServices/accounts`(kind `AIServices`)/ `accounts/projects` / `accounts/deployments`(`sku.name` でデプロイ種別、`properties.spilloverDeploymentName` で spillover)/ `capabilityHosts`(アカウントスコープとプロジェクトスコープの 2 階層。後継の `properties.capabilitySettings` はプレビュー・一部リージョンのみ → §6.2。2026-10-14: 設定ページが 301 で消え、取り下げか移設中か要確認)。
- **推奨プラクティス:** ARM/Bicep で両リージョンへ同一デプロイし、**CI/CD パイプラインを両リージョンにデプロイしてドリフトを防ぐ。**ロール割当・VNet / Private Endpoint / DNS も両方に用意する。
- **閉域環境では公開端末から `azd up` / `azd deploy` ができない。**VNet 内のセルフホスト GitHub Actions runner / Azure DevOps agent が公式の推奨パターンで、**CI/CD 基盤の追加コストとして見積もりに入れる。**
- **hosted agent の Terraform(2026-10-06 追加):** 経路が 2 つあり、**どちらが「エージェントの版」を持つかが違う**([cli-infrastructure](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/cli-infrastructure) ms.date 2026-09-16 / [set-up-ci-cd-cli](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/set-up-ci-cd-cli) 2026-09-23 / [deploy-hosted-agent-terraform](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent-terraform) 2026-09-23。Tech Community「Deploying hosted agents in Foundry Agent Service via Terraform」2026-10-01)

  | 経路 | Terraform が持つもの | エージェントの版 | 注意 |
  | --- | --- | --- | --- |
  | **azd + Terraform 基盤**(`azd ai agent init --infra=terraform`。`--deploy-mode container` と独立に選べる) | Foundry アカウント・プロジェクト・モデルデプロイ・ACR 等(`infra/main.tf` / `provider.tf` / `variables.tf` / `outputs.tf` / `main.tfvars.json`。既存基盤があれば `infra/foundry/` に別レイヤー) | **`azd deploy` が作る**(Terraform state には入らない) | 生成物はリモート state を作らない → Azure Storage の `azurerm` バックエンド・環境別キー・`use_azuread_auth` を自分で設定。`main.tfvars.json` は azd 前提で、素の `terraform apply` でそのまま動く前提にしない。**ejection はサービスの `network:` 構成に非対応**(閉域構成は Bicep 側に残るか手で書く)。Terraform の ARM 認証(`ARM_*` OIDC)と azd の認証は別 |
  | **Terraform 単独**(azd 不要) | 基盤は別構成(プラットフォームチーム)、エージェント定義は AzAPI の `azapi_data_plane_resource`(type `Microsoft.Foundry/agents@v1`、`parent_id` は ARM ID ではなく**プロジェクトのデータプレーン エンドポイント**) | **名前付きエージェントを管理**し、定義が変われば Foundry が新しい版を作る(版ごとの Terraform リソースは作らない。変更のない apply は新しいリリース ID にならない) | AzAPI 2.9.0+ / Terraform 1.4+。イメージは**ダイジェスト固定**、`rai_policy_name` には**ポリシーの ARM ID 全体**を渡す(無効な参照でも `active` になりうる → 遮断テスト必須)。apply 成功 ≠ 版が `active` → readiness ゲート(`terraform_data` + スクリプト)を挟む。**state に設定値が残るので環境変数に秘密を入れない**(プロジェクト接続の参照を使う)。**state lock は他の書き手(ポータル・SDK・別パイプライン)を止めない** → 名前付きエージェントの書き手を 1 つにし、エンドポイントの昇格(セレクタ)は Terraform 構成と所有者を分ける |

  どちらの経路でも、本番は §6.3 の公式手順(ピン留め → 候補検証 → 昇格)と組み合わせる。公式のサンプル(community-maintained の `simple-hosted-agent-deploy-azapi`)はローカル state 既定なので、共有環境ではリモート state とリリース統制を足す。手順ページ自体に `[TO VERIFY]`(公開前の通し検証)の執筆者コメントが残っている
- **ツールチェーンの版固定:** 7・8 月号ブログ(2026-09-09)のセットアップ基準は azd 1.32.0 以降 + `azure.ai.agents` 拡張 1.0.0-beta.13(プレビュー)以降。az / azd / 拡張 / Foundry Skill を一括導入する **Foundry DevPack**(0.1.3 はプレビュー。winget / brew / curl)は開発端末向けで、CI ランナーでは版を明示してインストールする。`azd ai agent` 系はまだ beta 拡張である点を CI 設計に織り込む。**2026-10-14 追記 — 拡張の版上げで CI が壊れる実例が続いた:** `azure.ai.agents` 1.0.0-beta.18(2026-09-30)はエージェント定義を azure.yaml(または明示のルート `$ref`)に必須化し、`AGENT_DEFINITION_PATH`・入れ子の `config:`・旧 AgentManifest を**拒否**する破壊的変更、beta.19(10-08)は prompt-memory / GitHub Copilot ツールセットのプロパティ名を **camelCase に変更(snake_case は拒否)**、`azd ai agent init` の `--manifest` / `-m` を非推奨の別名にした(`--template` / `-t` が正式。クイックスタートの例は `-m` のまま)。同時期の `azure.ai.toolboxes` beta.10・`azure.ai.routines` beta.9 も camelCase 化を含む。azd 本体は 1.35.1。→ **CI ランナーでは azd 本体と各拡張の版を固定し、版上げは検証環境で azure.yaml の受理と `azd deploy` の通しを確認してから**行う

---

## 7. 運用設計チェックリスト

**キャパシティ**
- [ ] データレジデンシ要件を確認(「日本国内処理」なら APAC Data Zone は不可)
- [ ] Quota Tier を確認し、自動昇格をオプトアウトするか判断
- [ ] PTU サイジングを式で算出し、**キャッシュ率を織り込む**
- [ ] PTU 購入前に**必ずデプロイを先に作成**してキャパシティ確認 → その後 Reservation 購入
- [ ] Batch に回せる処理を切り分けた(50% 割引)

**信頼性**
- [ ] PTU デプロイ全てに **spillover を有効化**
- [ ] APIM: backend pool(priority-based)+ circuit breaker(`Retry-After` 尊重)、2 ユニット × 2 AZ 以上
- [ ] **Cosmos DB の継続バックアップをインシデント前に有効化**、ゾーン冗長、ユニークなアカウント名
- [ ] Cosmos DB RU/s = 1,000 × コンテナー数 × プロジェクト数(最低 3,000 RU/s)
- [ ] Storage は GZRS、AI Search は Standard 以上 + レプリカ 3
- [ ] Foundry アカウント / Cosmos DB / AI Search / Storage に削除ロック
- [ ] **スレッド添付ファイルは復旧不可**であることをステークホルダーと合意

**可観測性**
- [ ] App Insights を接続、Log Analytics Reader を配布
- [ ] **レガシー `Latency` を使わず** `AzureOpenAITimeToResponse` / `TTLTInMS` / `NormalizedTBTInMS` を使用
- [ ] PTU は `ProvisionedManagedUtilizationV2`(V1 は非推奨)
- [ ] **spillover は 429 として計上されない**点をダッシュボードに明記
- [ ] トレースの PII / シークレット redaction をテレメトリ到達前に実装(**コンテナ側のみ有効。hosted agent のサーバーサイドトレースはマスクできない**)
- [ ] 会話の中身をトレースに残すか・誰が読めるかを決め、§3.6 の案 1〜4(集約 / 分離 / 接続しない / 同じ App Insights で中身だけ保護)を選んだ
- [ ] 案 4 なら `AppGenAIContent` を Protected にし、Privileged Monitoring Data Reader の付与先(分析担当・評価に使うプロジェクト MI)を限定した。MAF のメッセージイベント・自前ログなど `gen_ai.*` 以外に本文を書く計装を止めた。従来テーブルに本文が残っていないことを KQL で確認した(`AppDependencies | where isnotempty(Properties['gen_ai.input.messages']) | count` が 0。2026-10-06 の実測〈フラグ未登録〉は二重書きで残っていた)。早期フラグ `protectGenAISensitiveData` の登録要否を判断した。opt-out フラグ(`optOutProtectGenAISensitiveData`、2027-09-30 廃止)を登録していない
- [ ] 自作の KQL・アラート・ブックが `AppDependencies` 等から `gen_ai.*` の値を読んでいないか棚卸しした(2026-09-30 以降は `AppGenAIContent` 側を読む)
- [ ] Agent 365 のデータ収集(`a365LoggingEnabled`、Agent 365 有効テナントでは既定 true)を案件の方針に合わせた(中身を残さない要件・データ所在要件なら false)
- [ ] `gen_ai.*` 属性名への直接依存を 1 箇所に抽象化
- [ ] hosted agent のコンテナが `azure-ai-agentserver-responses` 2.3.0 以降なら、テレメトリ送出の既定(`AGENTSERVER_FLUSH_MODE=background`)で欠落が許容できるか判断し、必要なら `async` を明示した。LangChain の tracer を使うなら内容記録の既定(有効)を意図して設定した(2026-10-14 追加)
- [ ] 委任サブネットの IP 枯渇に対する合成監視

**評価**
- [ ] 評価器の組み合わせを決定(RAG / エージェントで別)
- [ ] **使用ツールが評価器の限定サポートリストに入っていないか確認**
- [ ] **安全性評価と Red Teaming 用に別リージョンのプロジェクトを設計**し、越境の法務確認
- [ ] 継続的評価の `max_hourly_runs` をトラフィックに合わせて調整(`sampling_rate` は百分率。エージェントエンドポイント経由の応答では継続評価のランが failed になる実測あり)
- [ ] ルーブリック評価器に `pass_threshold`(1.0〜5.0)を設定した(省略すると run 全体が失敗)。これは `score_model` グレーダーの尺度で、Foundry の Rubric 評価器は 0〜1・既定 0.5(2026-10-14 追記)
- [ ] 評価パイプラインの `azure-ai-projects` の版をワークフローごとに固定した(トレース評価の Learn 手順は 2.7.0 固定、GA 型は 2.8.0、MAF 同居は 2.8.0 不可)。conversation レベルで turn 専用評価器がスキップされたことを検出できる(2026-10-14 追加)
- [ ] 評価の権限を設計した(モデルを呼ぶ評価は Foundry User をアカウントスコープ、トレース評価はプロジェクト MI に App Insights の Reader、保護テーブルなら Privileged Monitoring Data Reader)
- [ ] `azure-ai-projects` 2.8.0 の「GA」と GA 一覧表の Preview / Limited preview 表記の食い違いを、SLA の説明で区別した(MAF 同居なら 2.8.0 は不可)
- [ ] Agents playground の既定 ON 評価をコスト観点で棚卸し

**コスト**
- [ ] `project` タグでプロジェクト別チャージバック(**Marketplace モデルは対象外**)
- [ ] Cost Analysis は**リソースグループスコープ**
- [ ] FT モデルのホスティング料、PTU の削除忘れ、playground 評価を定期棚卸し
- [ ] 予算アラート + 自動化(**ハードリミットは存在しない**)

**CI/CD**
- [ ] dev/stg/prod は **Foundry リソースごと分離**
- [ ] **capabilityHost 更新不可**を前提にパイプライン設計(capability host の削除・再作成前提。プロジェクト削除は不要)
- [ ] エージェント定義を as-code 化(ポータルでの未追跡変更を禁止)
- [ ] モデルデプロイの自動アップグレードを OFF
- [ ] カナリア / ブルーグリーンが要るなら**ルーティング層を自前で用意**(トラフィック分割は prompt / hosted とも非対応が既定の前提。hosted agent の本番昇格ページ〈preview〉は 90/10 のカナリアを示すが他ページと食い違い未実測)
- [ ] エージェントのルーティングを「Always use latest」のままにせず、本番はバージョン固定
- [ ] 本番リリースは公式 6 段階(ピン留め → 候補作成 → `active` と同一性の確認 → `version_ref` の候補専用セッションでテスト → 再確認して昇格 → 版指定なしの新しいセッションで確認)。`azd deploy` のエンドポイント設定・フックがピンを上書きしないことを確認した
- [ ] Terraform を使うなら、どの経路(azd + Terraform 基盤 / Terraform 単独で AzAPI)が版を持つかを決め、リモート state・書き手の一本化・環境変数に秘密を置かないことを決めた(ejection は `network:` 非対応)
- [ ] 版更新・ロールバックのときに既存の会話をどう扱うか決めた(休止明けの版は構成で割れる — 公式・Port 11 は作成時の版、probe 10 は現行セレクタの版。受入試験で `stop_session` 後・idle 明け・休止中ロールバック後の版を `version_indicator` で確認。旧版で続けさせるならエージェント名を分ける。すぐ移すなら版固定の新しいセッションを中間層で渡し、`force=true` 削除は最後の手段。別 agent への切り替えは会話を引き継げない。§6.3)
- [ ] デプロイが新しい版を作ったことを確認する判定を入れた(同じ zip・定義の再デプロイは既存の版を返す)。版の判定に応答の `agent_reference.version` を使っていない
