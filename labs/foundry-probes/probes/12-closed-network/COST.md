# 12〜14 の費用見積もりと実績見込み(2026-11-22)

対象: probe 12(閉域)・13(権限)・14(Agent Optimizer)。3 本とも RG `rg-ignite26-verify`(japaneast)の中だけに作る。上限は利用者の許可額 **5,000 円**、各項目の中止ラインは**見込み 4,000 円**。

## 単価(Azure Retail Prices API、JPY、`type=Consumption`、2026-11-22 13:5x JST 取得)

| 項目 | 単価 | meter(API の表記) |
| --- | --- | --- |
| AI Search Basic | ¥21.0446 / 時 | Azure AI Search / Basic Unit |
| プライベートエンドポイント | ¥1.5823 / 時 / 本(+処理量 ¥1.5823 / GB) | Virtual Network Private Link / Standard Private Endpoint |
| Private DNS ゾーン | ¥79.115 / ゾーン / 月(最初の 25 ゾーン) | Azure DNS / Private Zone |
| VM B2ats v2(Linux) | ¥1.9462 / 時 | Virtual Machines Basv2 Series / B2ats v2 |
| OS ディスク Standard HDD S4(32 GiB) | ¥243.0413 / 月(= ¥0.333 / 時) | Standard HDD Managed Disks / S4 LRS Disk |
| Cosmos DB Serverless | ¥45.0956 / 100 万 RU(+保存 ¥44.7 / GB 月) | Azure Cosmos DB serverless / 1M RUs |
| Blob(Hot LRS) | ¥3.1646 / GB 月、書き込み ¥7.9115 / 1 万回 | Blob Storage / Hot LRS |
| gpt-5.4-mini Global | 入力 ¥118.6725 / 100 万、出力 ¥712.035 / 100 万トークン | Azure OpenAI GPT5 / 5.4 mini Inp・Opt Gl |
| gpt-5.4 Global(Optimizer の最適化モデル) | 入力 ¥395.575 / 100 万、出力 ¥2,373.45 / 100 万トークン | Azure OpenAI GPT5 / 5.4 inp・opt Gl |
| text-embedding-3-small | ¥0.0038 / 1,000 トークン(DZ の単価。Global は API に出ない) | Azure OpenAI Embedding |
| Code Interpreter | ¥4.7469 / セッション | Azure OpenAI / Code-Interpreter-global Session |
| File Search のベクトル保存 | ¥15.823 / GB 日 | Assistants-File Search-glbl |
| Memory | 短期イベント ¥43.5133 / 1,000、長期 ¥43.5133 / 1,000 件月、検索 ¥87.0265 / 1,000 | Foundry Agents |
| (作らない)Azure Firewall | Standard ¥197.787 / 時、Basic ¥62.501 / 時 | 調査メモの取得値 |
| (作らない)Bastion Basic | ¥30.064 / 時 | 同上 |
| (作らない)hosted agent | vCPU ¥17.3009 / 時、メモリ ¥2.0538 / GiB 時 | Foundry Agents / Hosted |

- Web search(Grounding with Bing)は Retail Prices API に meter が見つからなかった(`contains(serviceName,'Bing')` が 0 件)。1 回あたり数円とみて、見積もりでは 1 回 ¥5 の上限で置く(**単価未確認**)。
- Private DNS ゾーンを月の途中で消したときに日割りになるかは確認できなかった。**見積もりは 1 か月分を満額で計上**する(安全側)。
- Copilot harness の実行は 2026-12-01 まで無料(既存調査)。トークン代はモデルの行に含める。

## 構成ごとの見積もり

### 閉域の環境(probe 12・13 の A / B1〜B5。1 本の Bicep)

| リソース | 数量 | 時間あたり | 想定 6 時間 |
| --- | --- | --- | --- |
| AI Search Basic | 1 | ¥21.04 | ¥126.3 |
| プライベートエンドポイント(Foundry / Blob / Cosmos / Search) | 4 | ¥6.33 | ¥38.0 |
| VM B2ats v2+S4 ディスク(パブリック IP なし) | 1 | ¥2.28 | ¥13.7 |
| **時間課金の小計** | | **¥29.65 / 時** | **¥177.9** |
| Private DNS ゾーン(cognitiveservices / openai / services.ai / search / documents / blob) | 6 | — | ¥474.7(満額) |
| Cosmos DB Serverless(エージェントの会話・定義の保存) | 〜100 万 RU | — | 〜¥45.1 |
| Storage(Blob) | 少量 | — | 〜¥1 |
| VNet・サブネット・UAMI・プロジェクト・アカウント | — | 無料 | ¥0 |

### パブリックの basic 環境(13 の B2・B6、14)

| リソース | 想定 | 見積もり |
| --- | --- | --- |
| Foundry アカウント+プロジェクト(固定費なし) | — | ¥0 |
| Memory(短期 50 件・長期 20 件・検索 50 回) | — | 〜¥8 |
| Agent Optimizer(最小ジョブ 1 本: 3 行・候補 1・評価器 1。下の式) | — | 〜¥50(上限 ¥300 で管理。estimate の Maximum が ¥1,000 を超えたら開始しない) |

Optimizer の式(agent-optimizer-costs の静的仮定: agent 2,000 / 400、judge 3,000 / 120、reflection 6,000 / 2,000 トークン / 呼び出し): agent 6 回 × ¥0.52 + judge 6 回 × ¥0.44 + reflection 〜6 回 × ¥7.12 ≈ ¥48。

### 呼び出し代(両環境の合計)

| 項目 | 想定 | 見積もり |
| --- | --- | --- |
| gpt-5.4-mini(エージェント・ツール・権限テスト・harness) | 入力 100 万・出力 10 万トークン以内 | ≤ ¥190 |
| Code Interpreter | 5 セッション | ¥24 |
| Web search | 5 回 | ≤ ¥25(単価未確認) |
| File Search の保存 | 1 MB 未満 × 1 日 | ¥0.02 |

### 合計

| | 見積もり |
| --- | --- |
| 閉域の時間課金(6 時間) | ¥178 |
| DNS ゾーン(満額) | ¥475 |
| Cosmos・Storage | ¥46 |
| 呼び出し代 | ¥239 |
| Memory・Optimizer | ¥58(Optimizer を上限 ¥300 で見ると ¥308) |
| **計** | **約 ¥1,000(安全側 ¥1,250)** |

**消し忘れたときの 1 日の費用**: 時間課金 ¥29.65 × 24 = **¥711.6 / 日**(DNS ゾーンは満額計上済みなので追加なし。Cosmos Serverless・アカウントは使わなければ 0)。5 日放置で予算を超える。

### 実施しないもの(費用見込み超過または費用事故のリスク)

| 項目 | 見積もり | 扱い |
| --- | --- | --- |
| Managed VNet(Approved Outbound に FQDN 規則を足すと Azure Firewall を自動作成) | Standard ¥197.8 / 時 → 1 日 ¥4,747、SKU は後から変えられない | **作らない**(費用見込み超過のため除外。1 日放置で 4,000 円を超える) |
| Bastion | ¥30.06 / 時 | 作らない(テストは `az vm run-command invoke`) |
| NAT Gateway | 単価は API で取れず(公開価格からの換算で約 ¥7 / 時) | 作らない。エージェントサブネットは既定のプライベートのまま |
| hosted agent を使う項目 | vCPU ¥17.30 / 時+メモリ ¥2.05 / GiB 時(0.5 vCPU / 1 GiB で約 ¥10.7 / 時) | 費用ではなく構築時間の理由で除外(NOTES) |

## 実績見込み(作成・削除の時刻から更新する)

| 時刻(JST) | 出来事 | 時間課金の稼働 | 累計見込み |
| --- | --- | --- | --- |
| 2026-11-22 13:57 | 見積もり作成(リソース未作成) | — | ¥0 |
| 14:01 | RG 作成。1 回目のデプロイはプリフライトで失敗(Basv2 のクォータ 0。リソースは作られていない)→ VM を B1s(¥2.1519 / 時)に変更 | — | ¥0 |
| **14:03(05:03 UTC)** | 閉域の環境の作成開始(AI Search・Cosmos・PE・VM はこの時刻から課金)。14:13 完了 | 開始 | — |
| 14:09〜14:10 | 公開の basic 構成(固定費なし) | — | — |
| 14:17〜14:20 | プロジェクトの capability host | — | — |
| 14:57 | 閉域アカウントに gpt-5.4 を追加(固定費なし) | — | — |
| **15:25(06:25 UTC)** | `deploy.sh down` の RG 削除を開始。VM・AI Search・PE・DNS ゾーンは 15:30〜15:44 に削除済み | 約 1.4〜1.7 時間 | — |
| 15:25〜15:59 | 1 回目の RG 削除は `ResourceGroupDeletionBlocked`(VNet が委任サブネットの legionservicelink で残った。残りは無料の VNet だけ)。両アカウントの purge(閉域側は 22 分)完了後に 2 回目 | — | — |
| **16:01(07:01 UTC)** | `az group exists -n rg-ignite26-verify` → **false**。論理削除のアカウントも 0 件 | 終了 | 下表 |

### 実績見込み(2026-11-22 16:01 の削除確認時点で計算。請求の確定値ではない)

| 項目 | 計算 | 見込み |
| --- | --- | --- |
| 時間課金(AI Search Basic・PE 4 本・VM B1s+S4) | (¥21.04+¥6.33+¥2.15+¥0.33)× 1.7 時間(05:03〜06:44 UTC で安全側) | ¥51 |
| Private DNS ゾーン 6 つ | 満額計上(日割りの有無は未確認) | ¥475 |
| Cosmos DB Serverless・Storage・File Search の保存 | 少量 | ≤ ¥10 |
| モデル呼び出し(gpt-5.4-mini 約 150 回、gpt-5.4 は Optimizer のみ) | Optimizer の実測トークンは公開 ¥2.9・閉域 ¥7。他は短い入出力 | ≤ ¥40 |
| Code Interpreter | 3 セッション × ¥4.75 | ¥14 |
| Web search | 1 回(クエリ 2 本。単価未確認) | ≤ ¥10 |
| Memory | 書き込み数回・検索十数回 | ≤ ¥5 |
| **合計** | | **約 ¥610(DNS ゾーンが日割りなら約 ¥135)** |

予算 5,000 円・中止ライン 4,000 円のいずれにも届かず、「費用見込み超過のため除外」にしたのは Managed VNet だけ(見積もり ¥4,747 / 日)。

消し忘れた場合の 1 日の費用(実際の構成で再計算): 時間課金 (¥21.04+¥6.33+¥2.15+¥0.33)× 24 = **¥716 / 日**(B2ats v2 のつもりの見積もり ¥711.6 から VM の差分だけ増える)。
