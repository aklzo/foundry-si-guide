# probe 15 の費用見積もりと実績見込み(2026-11-22)

対象: probe 15(エージェントの外向き通信の経路と NSG / UDR)。12 の閉域環境を `deploy.sh` で作り直し(13 の公開プロジェクトは `SKIP_PUBLIC=1` で省略)、RG `rg-ignite26-verify`(japaneast)の中だけに作る。
上限: 検証全体 **5,000 円**(既使用 約 610 円)、この run は**見込み 1,500 円未満**。時間の上限 120 分(17:34 開始 → 19:34 までに撤去完了、19:14 でテスト追加をやめる)。

## 単価(Azure Retail Prices API、JPY、`type=Consumption`)

2026-11-22 17:39 JST に再取得したもの(AI Search Basic・B1s・S4・Private DNS ゾーン)と、同日 13:5x に 12 で取得したもの(PE・モデル・Code Interpreter)。

| 項目 | 単価 | 取得 |
| --- | --- | --- |
| AI Search Basic | ¥21.0446 / 時 | 17:39 |
| VM B1s(Linux) | ¥2.1519 / 時 | 17:39 |
| OS ディスク Standard HDD S4 | ¥243.0413 / 月(= ¥0.333 / 時) | 17:39 |
| Private DNS ゾーン | ¥79.115 / ゾーン / 月(最初の 25 ゾーン) | 17:39 |
| プライベートエンドポイント | ¥1.5823 / 時 / 本 | 12(13:5x) |
| gpt-5.4-mini Global | 入力 ¥118.6725 / 100 万、出力 ¥712.035 / 100 万トークン | 12 |
| Code Interpreter | ¥4.7469 / セッション | 12 |
| NSG・ルートテーブル | 課金なし(meter なし) | — |
| Web search(Grounding with Bing) | meter が API に見つからない。1 回 ¥5 の上限で置く(**単価未確認**) | 12 |
| (作らない)NAT Gateway・Azure Firewall・Bastion・Managed VNet | 12 の COST.md のとおり | — |

## 見積もり(この run)

| 項目 | 計算 | 見積もり |
| --- | --- | --- |
| 時間課金(AI Search Basic・PE 4 本・VM B1s+S4) | ¥29.85 / 時 × 2.5 時間(作成 17:36 〜 撤去の完了待ちまで安全側) | ¥75 |
| Private DNS ゾーン 6 つ | 満額計上(日割りの有無は未確認) | ¥475 |
| Cosmos DB Serverless・Storage | 少量 | ≤ ¥10 |
| gpt-5.4-mini | 4 フェーズ × 7 呼び出し+作成。harness は 1 回の入力が大きい想定で 入力 100 万・出力 10 万トークン以内 | ≤ ¥190 |
| Code Interpreter | 5 セッション | ¥24 |
| Web search | 5 回(単価未確認) | ≤ ¥25 |
| NSG・ルートテーブル | — | ¥0 |
| **計** | | **約 ¥800(上限 1,500 円の内側)** |

消し忘れたときの 1 日の費用: ¥29.85 × 24 = **約 ¥716 / 日**。

任意項目の hosted agent(最小 0.5 vCPU / 1 GiB)は ¥10.7 / 時+イメージ置き場(ACR)。閉域ではプライベートの ACR と委任サブネットからのビルド経路が要り、時間の上限から実施するかは phase 3 の終了時刻で決める。

## 実績見込み(作成・削除の時刻から更新する)

| 時刻(JST) | 出来事 | 時間課金 | 累計見込み |
| --- | --- | --- | --- |
| 17:34 | 開始。既存の RG なし(`az group exists` = false)・論理削除のアカウントなし | — | ¥0 |
| 17:36 | RG 作成 → `p12-infra` デプロイ開始(AI Search・Cosmos・PE・VM はこの時刻から課金とみなす) | 開始 | — |
| 17:46 | `p12-infra` 完了(10 分)。アカウントの capability host は 12 と同じく 409(自動作成済み) | 稼働中 | — |
| 17:47 | プロジェクトの capability host PUT 201 → 作成中 | 稼働中 | — |
| 17:51 | プロジェクトの capability host Succeeded・`vmconfig` 完了 | 稼働中 | — |
| 17:54〜17:56 | テスト用エージェント 6 本を作成(固定費なし) | 稼働中 | — |
| 17:57 | 任意 (a) の準備: RAI ポリシー `rai-p15-egress`(egress のみ)を作成(固定費なし) | 稼働中 | — |
| 18:06 | gpt-5.4-mini の容量 10 → 50(容量は無料。従量のトークン代だけ) | 稼働中 | — |
| 18:31 | P1: NSG nsg-p15-agent を作成し snet-agent に関連付け(課金なし) | 稼働中 | — |
| 18:37 | P1 の NSG を外して削除 → P2: ルートテーブル rt-p15-agent(/32 × 4 → None)を関連付け(課金なし) | 稼働中 | — |
| 18:43 | P3: rt-p15-agent のルートを 0.0.0.0/0 → None の 1 本に置き換え | 稼働中 | — |
| 18:50 | P3 のルートテーブルを外して削除(回復の確認へ) | 稼働中 | — |
| 18:53 | 回復の確認(P4)の後、`deploy.sh down` を開始(capability host → プロジェクト → アカウント削除 → purge → RG 削除) | 撤去中 | — |
| 18:57〜19:20 | アカウント削除 → purge(約 24 分) | 撤去中 | — |
| 19:14 | purge 待ちのあいだに VM と AI Search を先に削除 | VM・AI Search 終了 | — |
| 19:18 | PE 4 本の削除を要求 | PE 終了(〜19:20) | — |
| 19:20〜19:36 | RG 削除(最後まで残ったのは Cosmos DB)。`ResourceGroupDeletionBlocked` は起きず | — | — |
| **19:36** | `az group exists -n rg-ignite26-verify` → **false**、`az cognitiveservices account list-deleted` → **[]** | 終了 | 下表 |

### 実績見込み(19:36 の削除確認時点で計算。請求の確定値ではない)

| 項目 | 計算 | 見込み |
| --- | --- | --- |
| 時間課金(AI Search Basic・PE 4 本・VM B1s+S4) | AI Search+VM(¥23.52 / 時)× 1.65 時間(17:36〜19:14)+PE(¥6.33 / 時)× 1.75 時間(17:36〜19:20) | ¥50 |
| Private DNS ゾーン 6 つ | 満額計上(日割りの有無は未確認) | ¥475 |
| Cosmos DB Serverless・Storage | 少量 | ≤ ¥10 |
| gpt-5.4-mini | 応答 約 30 回(harness は 403 で 0 回)。MCP の検索結果を含め入力 20 万・出力 3 万トークン以内とみる | ≤ ¥45 |
| Code Interpreter | 5 セッション(P0 × 2・P1・P2・P3)× ¥4.75 | ¥24 |
| Web search | 5 回(単価未確認、1 回 ¥5 の上限) | ≤ ¥25 |
| NSG・ルートテーブル・RAI ポリシー・容量の変更 | 課金なし | ¥0 |
| **合計(この run)** | | **約 ¥630(DNS ゾーンが日割りなら約 ¥160)** |
| 検証全体の累計 | 12〜14 の ¥610 + この run | **約 ¥1,240 / 5,000 円** |

この run の上限 1,500 円・検証全体の 5,000 円のどちらにも届かない。

## 追試(harness)

対象: 同じ日の夜の追試(Copilot harness の shell だけを P0〜P5 で測る)。RG `rg-ignite26-verify2`(japaneast)を新しく作り、その中だけに作る(RG 名が変わるので `baseName` も変わる)。作り方は上と同じ(`../12-closed-network/deploy.sh up && caphost && vmconfig`、`SKIP_PUBLIC=1`)。
上限: この run **1,000 円以内**、検証全体 **5,000 円**(前回までの累計 約 1,240 円)。時間の上限 120 分(19:41 開始 → 20:56 でテスト追加をやめて撤去開始 → 21:41 までに撤去完了)。

### 単価(2026-11-22 19:41 JST に Azure Retail Prices API で再取得。JPY・`type=Consumption`)

| 項目 | 単価 | 取得 |
| --- | --- | --- |
| AI Search Basic | ¥21.0446 / 時 | 19:41(前回と同じ) |
| プライベートエンドポイント(Standard Private Endpoint) | ¥1.5823 / 時 / 本 | 19:41(同じ) |
| VM B1s(Linux) | ¥2.1519 / 時 | 19:41(同じ) |
| OS ディスク Standard HDD S4 | ¥243.0413 / 月(= ¥0.333 / 時) | 19:41(同じ) |
| Private DNS ゾーン | ¥79.115 / ゾーン / 月(最初の 25 ゾーン) | 19:41(同じ) |
| gpt-5.4-mini Global・Cosmos DB Serverless・Storage・NSG・ルートテーブル・RAI ポリシー | 上の表のとおり(再取得しない) | 前回 |
| Copilot harness | トークン代のみ(上の表と同じ扱い。harness 自体は 2026-12-01 まで無料) | 前回 |

### 見積もり(この run、開始前)

| 項目 | 計算 | 見積もり |
| --- | --- | --- |
| 時間課金(AI Search Basic・PE 4 本・VM B1s+S4) | ¥29.85 / 時 × 2.0 時間(19:45 作成 〜 21:40 撤去完了の安全側) | ¥60 |
| Private DNS ゾーン 6 つ | 満額計上(日割りの有無は未確認) | ¥475 |
| Cosmos DB Serverless・Storage | 少量 | ≤ ¥10 |
| gpt-5.4-mini | T1(harness)6 フェーズ × 最大 2 回+T2 6 回+作成。harness は 1 回あたり入力 15 万トークン程度とみて、入力 150 万・出力 10 万トークン以内 | ≤ ¥250 |
| Code Interpreter・Web search | 今回は呼ばない | ¥0 |
| NSG・ルートテーブル・RAI ポリシー | 課金なし | ¥0 |
| **計** | | **約 ¥795(上限 1,000 円の内側。DNS ゾーンが日割りなら約 ¥330)** |

消し忘れたときの 1 日の費用: 前回と同じ **約 ¥716 / 日**。

### 実績見込み(追試。作成・削除の時刻から更新する)

| 時刻(JST) | 出来事 | 時間課金 | 累計見込み |
| --- | --- | --- | --- |
| 19:41 | 開始。`az group exists -n rg-ignite26-verify2` = false・論理削除のアカウントなし | — | ¥0 |
| 19:42 | RG 作成 → `p12-infra` デプロイ開始(`baseName` = 新しい値。AI Search・Cosmos・PE・VM はこの時刻から課金とみなす) | 開始 | — |
| 19:46 | Foundry の PE(`pe-<sfx>-aif`)作成完了(30 分ルールの起点) | 稼働中 | — |
| 19:52 | `p12-infra` 完了(10 分) | 稼働中 | — |
| 19:53〜19:57 | プロジェクトの capability host Succeeded(アカウント側は前回と同じく 409)・`vmconfig` | 稼働中 | — |
| 19:57 | gpt-5.4-mini の容量 10 → 50(無料)・テスト用エージェント作成(固定費なし) | 稼働中 | — |
| 20:03 | P1: NSG を作って snet-agent に関連付け(課金なし) | 稼働中 | — |
| 20:04 | P5 の準備: RAI ポリシー `rai-p15h-egress` 作成・`a15-harness-eg` 作成(固定費なし) | 稼働中 | — |
| 20:09 | P2: NSG を外して削除 → ルートテーブル(/32 × 4 → None)を関連付け(課金なし) | 稼働中 | — |
| 20:15 | P3: ルートを 0.0.0.0/0 → None の 1 本に置き換え | 稼働中 | — |
| 20:21 | P3 のルートテーブルを外して削除(P4 回復の確認へ) | 稼働中 | — |
| 20:26 | P5: egress controls を付けた `a15-harness-eg` で T1(NSG・ルートテーブルなし) | 稼働中 | — |
| 20:29 | VM のログを取得してから `deploy.sh down` を開始(capability host → プロジェクト → アカウント削除 → purge → RG 削除) | 撤去中 | — |
| 20:32 | アカウント削除 → purge 開始 | 撤去中 | — |
| 20:34 | purge 待ちのあいだに VM と AI Search を先に削除(VM は 1 回目の引数誤りでやり直し、20:34:12 に削除) | VM・AI Search 終了 | — |
| 20:34〜20:36 | PE 4 本を削除 | PE 終了 | — |
| 20:32〜20:55 | アカウント削除 → purge(約 23 分。上の run の 24 分とほぼ同じ) | 撤去中 | — |
| 20:55 | RG 削除開始(`az cognitiveservices account list-deleted` は 20:55 の時点で `[]`) | — | — |
| 21:10 | `az group exists -n rg-ignite26-verify2` → **false**、`az cognitiveservices account list-deleted` → **[]** | 終了 | 下表 |

### 実績見込み(追試。21:10 の削除確認時点で計算。請求の確定値ではない)

| 項目 | 計算 | 見込み |
| --- | --- | --- |
| 時間課金(AI Search Basic・PE 4 本・VM B1s+S4) | AI Search+VM(¥23.53 / 時)× 0.87 時間(19:42〜20:34)+PE(¥6.33 / 時)× 0.9 時間(19:42〜20:36) | ¥26 |
| Private DNS ゾーン 6 つ | 満額計上(日割りの有無は未確認) | ¥475 |
| Cosmos DB Serverless・Storage | 少量 | ≤ ¥10 |
| gpt-5.4-mini | T1(harness)6 回は応答の `usage` で入力 149,922・出力 5,906 トークン(キャッシュ分を含む)。T2 6 回は `usage` を記録していないので入力 5 万・出力 1 万トークン以内とみる。計 入力 20 万・出力 1.6 万トークン以内 | ≤ ¥35 |
| Code Interpreter・Web search | 呼んでいない | ¥0 |
| NSG・ルートテーブル・RAI ポリシー・容量の変更 | 課金なし | ¥0 |
| **合計(この run)** | | **約 ¥546(DNS ゾーンが日割りなら約 ¥72)** |
| 検証全体の累計 | 前回までの約 ¥1,240 + この run | **約 ¥1,786 / 5,000 円** |

この run の上限 1,000 円・検証全体の 5,000 円のどちらにも届かない。費用見込み超過のため除外した項目はない。
