# 閉域(PNA Disabled + BYO VNet 注入 + standard setup)— 実測メモ(2026-11-22)

環境: japaneast・RG `rg-ignite26-verify`(**実測後に削除済み**)・`infra.bicep`(自前。公式テンプレート 15 は foundry-samples が 404)・ARM API `2026-11-01`(Network は `2026-05-01`)・データプレーン `api-version=v1`・gpt-5.4-mini 2026-03-17(GlobalStandard 10)。テストは VNet 内の Linux VM(B1s・パブリック IP なし)から `az vm run-command invoke` で実行し、ID はユーザー割り当て MI(`id-ops` = Foundry User @アカウント)。生ログは `logs/`(`vm-<cmd>.log` は run-command の要約、`vmfull-<cmd>.log` は VM 内の全文。サブスクリプション ID・テナント ID は伏せ字)。

構成: VNet 10.40.0.0/16 — `snet-agent` 10.40.0.0/24(`Microsoft.App/environments` に委任・**defaultOutboundAccess=false・NAT なし**)/ `snet-pe` 10.40.1.0/24(PE 4 本: Foundry `account`・Blob・Cosmos `Sql`・Search)/ `snet-vm` 10.40.2.0/24(VM。ARM と公開側のアカウントを呼ぶため defaultOutboundAccess=true)。Private DNS ゾーン 6 つを VNet にリンク。BYO は Storage(共有キー無効)・**Cosmos DB for NoSQL Serverless**(ローカル認証無効)・AI Search **Basic**(bypass None)で、3 つとも publicNetworkAccess=Disabled。

## 結果(公式の記述 / 実測 / 一致・不一致)

| # | 項目 | 公式の記述 | 実測 | 判定 |
| --- | --- | --- | --- | --- |
| A1-1 | Cosmos DB Serverless で standard setup | standard-agent-setup「Provisioned Throughput と Serverless の両方に対応」(必要量は 3,000 RU/s と 5×1,000 RU/s の 2 通りの記述) | プロジェクトの capability host(`threadStorageConnections`=Cosmos Serverless、`vectorStoreConnections`=Search、`storageConnections`=Blob)が **PUT 201 → 約 3 分で Succeeded**。会話・エージェント・ファイル・ベクトルストアまで動いた | **一致**(RU/s の最低量は Serverless では無関係) |
| A1-2 | capability host の作成順 | capability-hosts / 調査メモ: アカウント → プロジェクトの順に作る | `networkInjections` 付きでアカウントを作った時点で、**アカウントの capability host `<account>@aml_aiagentservice` が自動作成**されていた(`customerSubnet` = 注入したサブネット、05:03 作成)。明示の PUT は `customerSubnet` なしで **400**「The customerSubnet property must match the subnet recorded on the CapabilityHost parent resource.」、付けると **409**「There is an existing Capability Host with name: …@aml_aiagentservice … cannot create a new Capability Host with name: caphost-acct for the same ClientId.」 | **不一致**(注入ありのアカウントでは作るのはプロジェクトの capability host だけ。IaC にアカウント側を書くと失敗する) |
| A1-3 | リソースプロバイダー | virtual-networks「`Microsoft.App` と `Microsoft.ContainerService` を登録。未登録だとエラー」 | `Microsoft.ContainerService` は **NotRegistered のまま**で、アカウント(注入あり)・capability host・prompt agent・全ツールが動いた | **不一致**(prompt agent の範囲では不要。hosted agent は未検証) |
| A1-4 | 既定でプライベートなサブネット(候補 3) | default-outbound-access「2026-03-31 より後の Network API で作る VNet はサブネットが既定でプライベート」。Foundry の文書は記載なし | Network API `2026-05-01` で作成し GET で `defaultOutboundAccess=false` を確認。NAT Gateway・Firewall なしで A2〜A5 の全項目が成立。委任直後から `serviceAssociationLinks: legionservicelink` が付く | **一致**(prompt agent は NAT なしで動く。hosted agent の起動・イメージ取得は対象外) |
| A1-5 | 構築時間 | — | `infra.bicep` 11 分(AI Search Basic が最長)+ capability host 3 分 | — |
| A2 | 外から拒否 / 中から通る | configure-private-link: PNA Disabled ならプライベートエンドポイント経由のみ | WSL(実行者に Foundry User を付与済み)からは名前が `*.privatelink.*` の CNAME を経て公開 IP に解決され、プロジェクト(エージェント一覧・Responses)・`openai.azure.com`・`cognitiveservices.azure.com` の 4 つとも **HTTP 403 `{"code":"403","message":"Public access is disabled. Please configure private endpoint."}`**。VM からは 3 つの FQDN が 10.40.1.7〜.9 に解決され、すべて 200 | **一致** |
| A3 | prompt agent | 対応(networking-options・deep-dive) | 作成 200、エージェントのエンドポイントで応答 200(初回 34 秒)、プロジェクトの Responses+`agent_reference` も 200 | **一致** |
| A3' | 会話の作り先(付随) | 記載なし | **会話は作った経路のものしか使えない**: `{project}/openai/v1/conversations` の ID はエージェントのエンドポイントで 400 `conversation_not_found`、エージェントのエンドポイントの `…/protocols/openai/conversations` の ID はプロジェクトの Responses で 400。公開側のプロジェクトでも同じ(閉域とは無関係) | 記載なし(新しい知見) |
| A4-1 | File Search | configure-private-link / toolbox-network-isolation: 対応 | ファイル登録 200 → ベクトルストア作成 → `completed`(チャンク 800 / 400)→ 検索 API 200 → `file_search` 付きエージェントが「あおいろペンギン 4096」と回答 | **一致** |
| A4-2 | Code Interpreter のファイル入出力(候補 5) | configure-private-link: 対応 / virtual-networks:「BYO の private 構成では**ファイルのアップロード・ダウンロードを伴わない場合のみ**動く。回避策は SDK でコンテナーを作り `container_id` を渡す」/ code-interpreter:「サンドボックスはサブネットを引き継がず外向き通信不可」 | `container: {type: auto, file_ids: [CSV]}` で平均 85.0 を計算し、`/mnt/data/result.txt` を `containers/{id}/files/{id}/content` から **200 で取得**。`container_id` を渡す回避策も同じく成功。サンドボックスからは VM(10.40.2.10)がタイムアウト、公開サイトは名前解決失敗 | virtual-networks の制限は**不一致**(入出力とも動いた)/ 外向き不可は**一致** |
| A4-3 | Web search | 公開経路で対応(Microsoft 管理の公開エンドポイント) | NAT なしの閉域プロジェクトで 200、`web_search_call.action.queries` に実クエリ、出典 URL 付きで回答 | **一致** |
| A4-4 | OpenAPI ツールで VM の API | VNet サブネット経由で対応 | 匿名認証・`http://10.40.2.10:8080`(TLS なし)で 200。VM のアクセスログの要求元は **10.40.0.84(エージェントサブネット)**、UA `azure-agents`。モデルが知りえない値 4217 を返した | **一致**(http も通る) |
| A4-5 | MCP ツールで VM の MCP サーバー | VNet サブネット経由で対応。mcp-authentication は private MCP を**専用の MCP サブネット**(Container Apps の内部 ingress)に置く構成を案内 | 接続なし・`require_approval: never`・`http://10.40.2.10:8081/mcp` で `mcp_list_tools` → `mcp_call` が成功(値 7391)。要求元 10.40.0.84 / 10.40.0.142、UA `AzureAIFoundryAgentRuntime/244898599`。要求は `server/discover` → `initialize` → `GET /mcp`(SSE 試行)→ `tools/list` → `tools/call` → `DELETE` | **一致**(専用サブネットでなく普通のサブネットの VM でも届く) |
| A4-6 | `input_file`(付随) | 記載なし | 閉域プロジェクトでは `.txt` の `input_file` が **誰でも 400 `Error while downloading file.`**(ops / fu / ac1、エージェントのエンドポイントとプロジェクトの Responses の両方)。**公開側のプロジェクトでは同じ内容で 200**(`logs/../../13-rbac-boundaries/logs/input-file-control.log`) | 記載なし(閉域だけの失敗) |
| A5 | Copilot harness(候補 7) | limits-quotas-regions: Japan East 可・「ネットワークの対応は prompt agent 一般より狭いことがある」/ copilot harness: egress controls はハーネス環境からの直接通信に効く。閉域での送信経路は記載なし | 注入済みの japaneast プロジェクトで `harness: {type: microsoft_copilot_preview}`(`Foundry-Features: MicrosoftCopilot=V1Preview`)の作成 200(57 秒)。shell で `curl http://10.40.2.10:8080/whoami` → 要求元 **10.40.0.124(エージェントサブネット)**、`curl https://api.ipify.org` → **`{"ip":"<public-ip-1>"}`(公開インターネットに出られた)**。サンドボックスの IP は 169.254.0.2、Foundry の FQDN は PE(10.40.1.9)に解決 | 記載なし(新しい知見): **VNet 内の宛先にはサブネット経由で届き、顧客サブネットに送信経路がないのに公開側へも出る** |

## 発見(SI 判断に効くもの)

1. **注入ありのアカウントではアカウントの capability host を IaC に書かない。** 自動作成され、追加は 400 / 409。作るのはプロジェクトの capability host だけ(`threadStorageConnections` / `vectorStoreConnections` / `storageConnections` の接続名)。
2. **Cosmos DB は Serverless で足りる**(検証・小規模環境の常時課金を消せる)。`Microsoft.ContainerService` の登録も prompt agent では不要だった。
3. **エージェントサブネットに NAT がなくても prompt agent とツール(File Search / Code Interpreter / Web search / OpenAPI / MCP)は動く。** Web search と Code Interpreter は Microsoft 側の経路、OpenAPI と MCP は 10.40.0.0/24 から VNet 内に届く。
4. **Copilot harness は閉域でも公開インターネットに出る。** エージェントサブネットに NAT も既定の送信もないのに出られ、出口の IP は VM サブネットの既定の送信とも違った。この実測では NSG・UDR を当てていない。probe 15 で当てると止まった(NAT なしで公開側に出るのは OpenAPI・MCP も同じ)。VNet 内の宛先には届くので、社内 API を shell から叩ける点も含めて設計する。
5. **virtual-networks の「Code Interpreter はファイル入出力なしのときだけ」は 2026-11-22 時点では当たらない**(入力・出力とも動いた)。一方で **`input_file` は閉域だけ失敗**するので、ファイルを渡すなら Code Interpreter か File Search を使う。
6. 会話 ID は作成経路に縛られる(プロジェクト / エージェントのエンドポイント)。アプリは会話の作成と応答を同じ経路に揃える。

## 撤去で詰まったところ(2026-11-22 の実測)

- プロジェクトが残っているとアカウントの削除は `CannotDeleteResource`「Cannot delete resource while nested resources exist」。
- RG 削除だけに任せると、アカウントは論理削除のまま委任サブネットの `legionservicelink` を握り続け、VNet が消えずに **`ResourceGroupDeletionBlocked`**(6 リソース)。`az cognitiveservices account purge` の完了後(閉域側は **22 分**、公開側は約 3 分)にリンクが消え、2 回目の RG 削除で `az group exists` = false になった。`deploy.sh down` はプロジェクト削除 → アカウント削除 → purge → RG 削除の順に直してある。

## 対象外にしたもの(理由と概算)

| 項目 | 理由 | 概算(実施した場合) |
| --- | --- | --- |
| hosted agent を使う項目(閉域ビルド・プライベート ACR・PNA 無効時のエンドポイント到達・セッション分離・UserIdentityImpersonation) | 構築(イメージ・ACR・委任サブネットからのビルド経路)に時間がかかるため | vCPU ¥17.30 / 時+メモリ ¥2.05 / GiB 時(0.5 vCPU / 1 GiB で約 ¥10.7 / 時)+ACR Standard ¥105.5 / 日 |
| Managed VNet(Japan West 含む) | Approved Outbound に FQDN 規則を足すと Azure Firewall が自動作成され、SKU を後から変えられない | **費用見込み超過のため除外**(Standard ¥197.8 / 時 = ¥4,747 / 日) |
| Bastion | 不要(run-command で代替) | ¥30.06 / 時 |
| NAT Gateway を足した比較(候補 3 の後半) | NAT なしで全項目が成立したため比較の必要がなくなった | 約 ¥7 / 時(単価は API で取れず) |

## 再実行

```bash
cd labs/foundry-probes/probes/12-closed-network
./deploy.sh up && ./deploy.sh caphost && ./deploy.sh vmconfig   # 約 15 分
./vmrun.sh push                                                 # VM に vm/*.py と config を置き、検証用サーバーを起動
./probe.sh outside && ./probe.sh inside && ./probe.sh harness   # A2〜A5
./vmrun.sh fetch <command>                                      # VM 内の全文ログを取得
./deploy.sh down                                                # 必ず実行(時間課金 約 ¥29.65 / 時)
```

`deploy.sh caphost` のアカウント側の PUT は上の A1-2 のとおり 409 になる(記録のために残してある)。費用は `COST.md`。
