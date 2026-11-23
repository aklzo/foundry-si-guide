# エージェントの外向き通信の経路と NSG / UDR(閉域プロジェクト)— 実測メモ(2026-11-22)

> **進行状況**: 17:34 開始 / 17:36〜17:51 環境作成 / 18:08〜18:53 P0〜P4 / 18:53〜19:36 撤去(**完了**: `az group exists` = false・論理削除のアカウントなし)。全体 122 分(時間の上限 120 分を撤去の待ちで 2 分超過)

環境: 12 と同じ構成を `../12-closed-network/deploy.sh up && caphost && vmconfig` で作り直した(japaneast・RG `rg-ignite26-verify`・PNA Disabled・BYO Cosmos DB Serverless / Storage / AI Search Basic・gpt-5.4-mini 2026-03-17 GlobalStandard)。`snet-agent` 10.40.0.0/24 は `Microsoft.App/environments` に委任・**defaultOutboundAccess=false・NAT なし**、VM は `snet-vm` 10.40.2.10(B1s・パブリック IP なし・既定の送信あり)。13 の公開プロジェクトは `SKIP_PUBLIC=1` で省いた。テストは VM から `az vm run-command invoke`(`run15.sh` → `vm/egressprobe.py`)、ID は `id-ops`(Foundry User @アカウント)。生ログは `logs/`(`vm-all.log` などが run-command の要約、`vmfull-p15-bundle.log` が VM 内の全文、`net.log` が NSG / ルートテーブルの操作。サブスクリプション ID・公開 IP などは伏せ字)。

テスト(閉域プロジェクト): T1 Copilot harness の shell(IP エコー 2 つ・VM の `/whoami`・`hostname -I`・TCP 22)/ T2 OpenAPI ツール(匿名。サーバーは公開の `https://api.ipify.org` と `https://ifconfig.me/all.json` の 2 本)/ T3 MCP ツール(`https://learn.microsoft.com/api/mcp`、接続なし・`require_approval: never`)/ T4 Code Interpreter(python で ipify と VM)/ T5 Web search / 素の prompt agent(ツールなし)/ T6 VM 自身の送信。

フェーズ(すべて `snet-agent` に対して。関連付けから 2 分待って実行):

| フェーズ | 内容 | 関連付け → 実行(JST) |
| --- | --- | --- |
| P0 | NSG・ルートテーブルなし | — → 18:08 |
| P1 | NSG `deny-echo`(priority 100・Outbound・Deny・宛先 = ipify の 3 IP と ifconfig.me の 1 IP の /32。ほかは既定の規則のまま) | 18:31:34 → 18:33:54 |
| P2 | NSG を外して削除 → ルートテーブル(同じ 4 IP の /32 → 次ホップ None) | 18:37:43 → 18:40:02 |
| P3 | ルートを 0.0.0.0/0 → None の 1 本に置き換え | 18:43:22 → 18:45:41 |
| P4 | ルートテーブルを外して削除(回復の確認。T2・T3 だけ) | 18:50:31 → 18:52 |

## 結果(フェーズ × テスト)

| テスト | P0 なし | P1 NSG(エコー先 4 IP) | P2 UDR /32 → None | P3 UDR 0.0.0.0/0 → None | P4 外した後 |
| --- | --- | --- | --- | --- | --- |
| T1 harness の shell | **未取得**(エージェントのエンドポイントが 403。下の E8) | 未取得(同) | 未取得(同) | 未取得(同) | — |
| T2 OpenAPI → ipify / ifconfig.me | **200**(6.7 秒)。ifconfig.me から見た送信元 `<public-ip-1>`、`forwarded: <public-ip-2>,<public-ip-3>,<public-ip-1>,…`。ipify の値は 100.100.209.x(X-Forwarded-For の先頭) | **400 `tool_user_error`**(16.9 秒) | **400 `tool_user_error`**(16.9 秒) | **400 `invalid_configuration`「Storage operation exceeded its 45-second deadline.」**(45.1 秒) | **200**(5.7 秒)。送信元 `<public-ip-4>`、forwarded の手前は 100.100.209.x・100.64.17.x |
| T3 MCP → Learn | 200(6.7 秒。1 回目は 429 → 容量を 10 → 50) | 200(6.4 秒) | 200(3.9 秒) | **400 `tool_user_error`**(63.0 秒) | 200(4.6 秒) |
| T4 Code Interpreter | 200。ipify は名前解決失敗(`Errno -3`)、VM はタイムアウト | 同じ | 同じ | 同じ | — |
| T5 Web search | 200(4.7 秒)・`web_search_call` 完了 | 200(7.3 秒) | 200(5.9 秒) | **200**(4.6 秒) | — |
| 素の prompt agent | 200 `PONG`(3.3 秒) | 200(2.6 秒) | 200(2.4 秒) | **200**(4.4 秒) | — |
| T6 VM の送信 | 200 `<public-ip-5>`(0.2 秒) | 同じ | 同じ | 同じ | — |

- T2〜T5 と素の prompt agent は、エージェントのエンドポイントの 403 のため**プロジェクトの Responses+`agent_reference`** で呼んだ(全フェーズ同じ経路。文書ではツールの外向き通信は Tools Service → データプロキシなので、入口の違いは結論に影響しないとみている)。
- P1〜P3 の T2 の 400 は、P0 で 2 回・P4 で 1 回とも 200 なので、NSG / UDR による失敗とみなした。T3 の宛先(learn.microsoft.com、CDN で IP が変わる)は P1・P2 の拒否対象に入れていない(対照)。
- VM のアクセスログ(`server.log`)には VM 自身の `/health` しかない(今回は VM 宛てのツール呼び出しなし・harness 不通)。

## 送信元 IP とサービスタグ(`az network list-service-tags --location japaneast`、changeNumber 246 を Python `ipaddress` で照合。`tagip.py`)

| 観測 | IP | 含むタグ(狭い順) |
| --- | --- | --- |
| T6 VM(`snet-vm` の既定の送信) | `<public-ip-5>` | AzureCloud.japaneast(/19)・AzureCloud |
| T2 OpenAPI(P0) | `<public-ip-1>` | AzureCloud.japaneast(/17)・AzureCloud |
| T2 OpenAPI(P4) | `<public-ip-4>` | AzureCloud.japaneast(/16)・AzureCloud |
| T2 の X-Forwarded-For の手前の 2 段 | 100.100.209.x・100.64.17.x | どのタグにもない(100.64/10 の CGNAT 範囲。100.100/17 は virtual-networks が予約済みとして挙げる範囲) |

- どの公開 IP も **Azure の公開 IP(AzureCloud.japaneast)で、サービス別のタグ(AzureCognitiveServices など)には入っていない**。OpenAPI の送信元は呼び出しごとに変わり(P0 と P4 で別)、VM の既定の送信 IP とも別。
- 12 で harness が出た送信元(12 のログでは伏せ字。この表の番号とは別物)と同じ範囲かは、今回 harness を呼べなかったので比べていない。

## 公式の記述 / 実測 / 一致・不一致

| # | 項目 | 公式の記述 | 実測 | 判定 |
| --- | --- | --- | --- | --- |
| E1 | prompt agent のツールの外向き通信はどこを通るか | agents-networking-deep-dive:「Prompt agents use the single-tenant data proxy for all outbound connectivity」「All tool calls route through the data proxy」「All agent infrastructure (data proxies and Micro VMs) deploys into this subnet」 | OpenAPI(公開 URL)と MCP(Learn)の通信は、委任サブネットの NSG / UDR で止まった(E2・E3)→ **顧客サブネットを通る**。12 の VM 宛て(送信元 10.40.0.x)と同じ経路 | **一致** |
| E1' | 公開側への送信 | virtual-networks:「No public egress: Foundational infrastructure provides the right authentication and security …」 | NAT・FW なし、defaultOutboundAccess=false でも、**OpenAPI と MCP は公開側の宛先に届いた**。宛先から見た送信元は Microsoft 管理の Azure 公開 IP(上表)、その手前に 100.100.209.x → 100.64.17.x の内部アドレス | 「公開側へは出ない」と読むなら**不一致**(基盤の通信の説明と読むなら記載なし) |
| E2 | 委任サブネットの NSG | virtual-networks:「NSG を委任サブネットに当てるなら、AzureActiveDirectory タグなど必要な依存先への送信許可を入れる。塞ぐと provisioning と runtime が失敗しうる」 | 宛先 IP だけを拒否する NSG で **OpenAPI が 400(16.9 秒)**。ほか(MCP・Web search・素の prompt agent)は変化なし | **一致**(NSG が効く) |
| E3 | 委任サブネットの UDR | virtual-networks の FAQ:「ルートテーブルは不要。付けるなら(FW に送るなど)PE へのピアリング経路を上書きしない」 | /32 → None で OpenAPI が 400。0.0.0.0/0 → None で OpenAPI(45 秒の Storage 期限切れ)と MCP(63 秒)が失敗。外すと両方 200 に戻った | **一致**(UDR が効く) |
| E4 | Web search | copilot harness:「Declared Foundry tools such as Code Interpreter and web search run behind their own service boundaries」/ 調査メモ: Microsoft 管理の公開エンドポイント | 0.0.0.0/0 → None でも 200(4.6 秒) | **一致**(顧客サブネットを通らない) |
| E5 | Code Interpreter | code-interpreter:「サンドボックスはサブネットを引き継がず外向き通信不可」 | 全フェーズで公開側は名前解決失敗、VM はタイムアウト(12 と同じ) | **一致** |
| E6 | エージェントの実行基盤そのものがサブネットの外向き通信に頼るか | virtual-networks:「FW の許可リストに `control-{region}.identity.azure.net`・`{region}.login.microsoft.com`・`login.microsoftonline.com`。塞ぐと provisioning と runtime が失敗しうる」 | 0.0.0.0/0 → None でも**ツールなしの prompt agent は 200**。ツールの呼び出し(OpenAPI)は「Storage operation exceeded its 45-second deadline.」で失敗(何の Storage かは不明) | ツールなしの応答は**失敗しなかった**。ツールありは失敗(原因の切り分けは未実施) |
| E7 | Copilot harness の外向き通信 | copilot harness:「Network egress controls (preview) govern direct outbound requests from the Foundry-managed harness execution environment」「Shell commands can … access network resources that the environment permits」。経路(サブネットを通るか)は記載なし | この run では未取得(E8 の 403)。**追試(別名のアカウント・下の節)で取得**: shell の `curl` で公開側へ出る通信は、委任サブネットの NSG(宛先 /32 の拒否)・UDR(/32 → None、0.0.0.0/0 → None)で**タイムアウトになり、外すと戻った**。VNet 内の VM には 10.40.0.x から届いた。RAI ポリシーの egress controls(`ifconfig.me` を Deny)では **HTTP 403**、規則にない ipify は 200 | 経路は記載なし(**新しい知見**: 顧客サブネットを通り NSG / UDR で止まる)。egress controls は**一致** |
| E8 | 作成直後のエージェントのエンドポイント(付随) | 記載なし | Foundry の PE を 17:39 に作ってから 18:53 まで、エージェントのエンドポイント(`…/agents/{name}/endpoint/protocols/openai/…`)だけが **403「Traffic is not from an approved private endpoint.」**(成功は 18:03〜18:04 に 1 回だけ)。同じ VM・同じ PE(10.40.1.9)からプロジェクトの Responses・エージェントの作成と一覧・アカウントの Responses は 200。アカウントへのタグ付け(18:29)でも変わらず。12 の記録にはない。今回は 12 で purge した同じ名前(RG 名から決まる `baseName`)で作り直した。**追試で RG 名を変えて `baseName` を変えたら再現しなかった**(PE 作成 19:46 の 14 分後の 1 回目 20:00 から harness・OpenAPI ともエージェントのエンドポイントで 200) | 記載なし(新しい知見。**名前を変えたら直った**。ただし同じ名前・別の名前で 1 回ずつの比較なので、原因が名前の再利用とは断定しない) |
| E9 | IP エコーの読み方(付随) | — | ipify は X-Forwarded-For の先頭(内部の 100.100.209.x)を返し、TCP の送信元を返さない。ifconfig.me/all.json は送信元と forwarded を分けて返す | プロキシを挟む経路の送信元確認に ipify は使えない |

## 発見(読み手の問い「Web search も Global Standard も外に出る。harness は何が違うのか」に効くもの)

1. **prompt agent の OpenAPI / MCP ツールが公開側の URL を呼ぶ通信は、顧客の委任サブネットを通り、そのサブネットの NSG / UDR で止められる。** NAT も FW もなく defaultOutboundAccess=false でも公開側に届く(送信元は Microsoft 管理の Azure 公開 IP で、呼び出しごとに変わる)。「NAT を置かない = 外に出ない」ではない。止めるなら NSG / UDR(または 0.0.0.0/0 を FW に向ける)を明示的に当てる。宛先を決めるのは**エージェント定義に書いた URL**。
2. **Web search は顧客サブネットを通らない**(0.0.0.0/0 → None でも動く)。宛先は固定のサービスで、止める手段はサブネットではなく、ツールを付けないことと管理者の設定。Code Interpreter はそもそも外に出ない。
3. **harness は今回測れなかった。** 12 の実測(NAT なしで公開側に出て、VM 内の宛先にはサブネット経由で届く)に対して、NSG / UDR で公開側への通信が止まるかは**まだ言えない**。比べる軸は次のとおり(→ **追試で測った**。harness の行は追試の結果に直した。詳細は末尾の「追試」の節)。

   | 経路 | 宛先を誰が決めるか | 通る場所(実測) | 止める手段(実測 / 文書) |
   | --- | --- | --- | --- |
   | OpenAPI / MCP | 定義に書いた URL | 顧客サブネット → Microsoft 管理の公開 IP | NSG / UDR で止まった(実測) |
   | Web search | 固定のサービス(Bing) | 顧客サブネットを通らない | サブネットでは止まらない(実測)。ツールの有無・管理者設定 |
   | Code Interpreter | 実行時のコード | 外に出ない | —(実測) |
   | harness の shell / Web | **実行時にモデルが決める任意の宛先・任意のコマンド**(12 では `curl` で任意の公開サイト) | VNet 内の宛先も公開側も顧客サブネット経由(12・追試の shell)→ Microsoft 管理の Azure 公開 IP(OpenAPI と同じ AzureCloud.japaneast・別のプレフィックス。X-Forwarded-For に内部の段なし) | **NSG / UDR で止まった**(追試・shell の実測)。**RAI ポリシーの egress controls でもホスト名で止まった**(追試・HTTP 403)。付けると VNet 内の 8080 番・公開の 22 番への直接接続も拒否された。Web ツールは未測定 |

   違いとして今言えるのは「宛先がエージェント定義に固定されず、実行時に決まる」点と、「文書が示す制御がサブネットではなく RAI ポリシー」の点まで。
4. **0.0.0.0/0 → None でもツールなしの prompt agent は答える。** 実行基盤そのものはサブネット経由のインターネット送信に頼っていない(この構成・この時点)。ただしツールの呼び出しは「Storage operation exceeded its 45-second deadline.」で失敗したので、0.0.0.0/0 を FW に向ける設計では、文書の許可リスト(Entra など)を入れたうえでツールの動作を確かめる。
5. **purge 後に同じ名前でアカウントを作り直すと、エージェントのエンドポイントだけが 70 分以上 403 になることがある**(原因は未確定)。prompt agent はプロジェクトの Responses+`agent_reference` で代わりに呼べるが、harness はエージェントのエンドポイント必須なので呼べない。検証環境を作り直すときは名前を変える(`baseName` を変える)。

## 対象外にしたもの(理由と概算)

| 項目 | 理由 | 概算(実施した場合) |
| --- | --- | --- |
| T1 harness の全項目(IP エコー・VM `/whoami`・`hostname -I`・TCP 22)と、そのフェーズ比較 | エージェントのエンドポイントの 403(E8)。P0 で計 4 分、P1〜P3 で各 5 回(約 40 秒)再試行したが通らず | トークン代のみ(harness は 2026-12-01 まで無料)・各フェーズ ≤ ¥5 |
| 任意 (a) harness の egress controls | RAI ポリシー `rai-p15-egress`(`egressPolicy`: `api.ipify.org` を Deny・既定 Allow・Enforced、API `2026-05-15-preview`)の PUT は閉域の Japan East アカウントで **201**(`logs/rai-egress.log`)。harness を呼べないため、エージェントへの付与と T1 の再実行は未実施。P0〜P3 の終了も 18:50(開始から 76 分)で、条件の 75 分を超えた | ポリシーは無料・トークン代 ≤ ¥10 |
| 任意 (b) 送信元 IP を返す最小の hosted agent | P0〜P3 が 75 分以内に終わらなかった。閉域ではプライベート ACR と委任サブネットからのビルド経路も要る | 0.5 vCPU / 1 GiB で約 ¥10.7 / 時+ACR Standard ¥105.5 / 日(12 の COST.md の単価) |
| NSG に AzureActiveDirectory などの許可を入れた 0.0.0.0/0 拒否、FW へ 0.0.0.0/0 を向ける構成 | 時間の上限(撤去に約 35 分かかるため 18:53 に撤去開始) | NSG は無料。FW は Standard ¥197.8 / 時(**費用見込み超過のため除外**の扱いは 12 と同じ) |
| NAT Gateway を足した比較 | 指示どおり作らない(NAT なしで公開側に出ることは P0 で確認済み) | 約 ¥7 / 時 |

## 撤去

- 18:53 `deploy.sh down` 開始(`LOGDIR` で `logs/deploy.log` に記録)→ capability host・プロジェクト削除 → 18:57 アカウント削除 → purge(**約 24 分**。12 の 22 分とほぼ同じ)。
- purge を待つあいだに、時間課金の VM・AI Search(19:14)と PE 4 本(19:18)を先に消した。
- 19:20 RG 削除 → 19:36 `az group exists -n rg-ignite26-verify` = **false**、`az cognitiveservices account list-deleted` = **[]**。purge を先に済ませたので `ResourceGroupDeletionBlocked` は起きなかった。最後まで残ったのは Cosmos DB(RG 削除の約 15 分の大半)。

## 再実行

```bash
cd labs/foundry-probes/probes/12-closed-network
export SCRATCH=<鍵と vm-config.json の置き場> LOGDIR=$PWD/../15-egress-paths/logs OUTS_FILE=$PWD/../15-egress-paths/infra.outputs.json SKIP_PUBLIC=1
./deploy.sh up && ./deploy.sh caphost && ./deploy.sh vmconfig    # 約 15 分(アカウントの capability host は 409 のまま)
./vmrun.sh push                                                  # vmprobe.py / api_server.py / config.json
# 今回は SKIP_PUBLIC で config.json の publicProjectEndpoint が null になり vmprobe.py の short() が落ちたので VM 上で "#" に置き換えた(deploy.sh vmconfig は撤去中に `// "#"` を足して直した)
cd ../15-egress-paths
./run15.sh push && ./run15.sh run setup P0 && ./run15.sh run setup2 P0
./run15.sh run all P0
./run15.sh nsg <ipify の IP>/32 … <ifconfig.me の IP>/32 ; ./run15.sh run all P1   # 関連付けから 2 分待つ
./run15.sh nsg-off ; ./run15.sh rt <同じ /32 …> ; ./run15.sh run all P2
./run15.sh rt 0.0.0.0/0 ; ./run15.sh run all P3
./run15.sh rt-off ; ./run15.sh run t2 P4 ; ./run15.sh run t3 P4
python3 -I tagip.py <service tags の JSON> <IP> …
cd ../12-closed-network && ./deploy.sh down                     # 必ず実行(時間課金 約 ¥29.85 / 時)
```

費用は `COST.md`。

## 追試: Copilot harness(2026-11-22 夜・別名のアカウント)

> **進行状況**: 19:41 開始 / 19:42〜19:57 環境作成 / 20:00〜20:28 P0〜P5 / 20:29〜21:10 撤去(**完了**: `az group exists` = false・論理削除のアカウントなし)。全体 90 分(時間の上限 120 分の内側。テストの追加は開始 47 分で終了)

上の run で測れなかった T1(harness の shell)だけを測り直した。目的は 3 点: (1) harness の shell から公開側への通信が `snet-agent` の NSG / UDR で止まるか、(2) RAI ポリシーの egress controls(preview)で止まるか、(3) 送信元 IP が OpenAPI ツールの送信元と同じ範囲か。

環境: 上と同じ構成を **RG `rg-ignite26-verify2`**(japaneast)に作り直した。RG 名が変わったので `baseName`(`uniqueString(resourceGroup().id)` から決まる)も変わり、アカウント名は 12・上の run と別(伏せ字ではどちらも `aif-<sfx>`)。`../12-closed-network/deploy.sh up && caphost && vmconfig`(`SKIP_PUBLIC=1`)、ID は `id-ops`(Foundry User @アカウント)、gpt-5.4-mini の容量は最初から 50(上の run の 429 を避けるため。無料)。生ログは **`logs/harness/`**(`vm-t1.log`・`vm-t2.log` が run-command の要約、`vmfull-p15h-bundle.log` が VM 内の全文、`net.log` が NSG / ルートテーブルの操作、`rai-egress.log` が RAI ポリシーの PUT、`tagip.log` がサービスタグの照合、`vm-dns.log` が VM からの名前解決、`vm-tcp22.log` が TCP 22 の対照)。上の run の `logs/` 直下と 12〜14 のログは書き換えていない(開始前と終了後の sha256 が一致)。

T1 の呼び方: エージェントのエンドポイント(`…/agents/{name}/endpoint/protocols/openai/conversations` で会話を作り、同じ会話で `…/responses`)。shell に 1 本のコマンドを渡す(`vm/egressprobe.py` の `SHELL_CMD`: `curl` で `https://api.ipify.org?format=json`・`https://ifconfig.me/ip`・VM の `http://10.40.2.10:8080/whoami`、`hostname -I`、`getent`、`/dev/tcp/github.com/22`(8 秒)、`curl https://ifconfig.me/all.json`、`env | grep _proxy`)。ifconfig.me/all.json は TCP の送信元(`ip_addr`)と X-Forwarded-For(`forwarded`)を分けて返すので主に使い、ipify(X-Forwarded-For の先頭を返す)は補助。各フェーズの最後に対照として T2(OpenAPI → ipify・ifconfig.me/all.json)を 1 回流した。

| フェーズ | 内容(すべて `snet-agent` に対して) | 関連付け → T1 実行(JST) |
| --- | --- | --- |
| P0 | NSG・ルートテーブルなし | — → 20:00:07 |
| P1 | NSG `deny-echo`(priority 100・Outbound・Deny・宛先 = ipify の 3 IP と ifconfig.me の 1 IP の /32。19:54 の VM と 20:00 の harness の名前解決で同じ値: <public-ip-15>・<public-ip-16>・<public-ip-17>・<public-ip-18>) | 20:03:33 → 20:05:56 |
| P2 | NSG を外して削除 → ルートテーブル(同じ 4 IP の /32 → 次ホップ None) | 20:09:39 → 20:11:50 |
| P3 | ルートを 0.0.0.0/0 → None の 1 本に置き換え | 20:15:16 → 20:17:37 |
| P4 | ルートテーブルを外して削除(回復の確認) | 20:21:34 → 20:23:51 |
| P5 | NSG・ルートテーブルなしのまま、RAI ポリシー `rai-p15h-egress`(`egressPolicy`: `mode` Enforced・`defaultAction` Allow・規則 `deny-ifconfig` = `ruleType` Fqdn・`match.host` `ifconfig.me`・`actionType` Deny。`contentFilters: []`、API `2026-05-15-preview`、PUT 201)を `rai_config.rai_policy_name`(ARM の完全な ID)に入れた**新しいエージェント** `a15-harness-eg` | ポリシー 20:04:15・エージェント作成 20:05 → 20:26:08 |

付け方は Learn の use-tools-skills-copilot-harness(ms.date 2026-11-04)の「Control network egress」と「Create an egress-only policy with REST」、REST 仕様(azure-rest-api-specs の `cognitiveservices/…/preview/2026-05-15-preview/cognitiveservices.json` の `RaiEgressPolicyConfig` / `RaiEgressRule`)で確かめた。文書は「ポリシーを付ける・参照を変えるときは新しいエージェントのバージョンを作る」「実行中の harness 環境はポリシーの変更を読み直さないので新しい会話で試す」とするので、P5 は別エージェント・新しい会話で流した(作成時に返った定義に `rai_config.rai_policy_name` = ポリシーの ARM ID が入っていることを確認)。

### 結果(フェーズ × テスト)

| T1 の項目 | P0 なし | P1 NSG(/32) | P2 UDR /32 → None | P3 UDR 0.0.0.0/0 → None | P4 外した後 | P5 egress controls(ifconfig.me を Deny) |
| --- | --- | --- | --- | --- | --- | --- |
| 応答(エージェントのエンドポイント) | 200(19.7 秒) | 200(53.7 秒) | 200(48.6 秒) | 200(53.5 秒。`shell_call_output` は `incomplete`〈30 秒を超えた〉で、途中までの出力を応答本文に貼った) | 200(20.0 秒) | 200(10.7 秒) |
| ifconfig.me/all.json | **200**。`ip_addr` = <public-ip-19>、`forwarded` = `<public-ip-19>,<public-ip-18>`(後ろは ifconfig.me 側の Google LB) | **タイムアウト**(curl 28・10 秒) | **タイムアウト** | 結果なし(手前の項目のタイムアウトの累計で shell が 30 秒を超え、ここで出力が切れた) | **200**。P0 と同じ `ip_addr` | 本文なし(この行は HTTP コードを出していない。同じホストの ifconfig.me/ip は 403) |
| ifconfig.me/ip | 200 `<public-ip-19>`(0.31 秒) | タイムアウト(10 秒) | タイムアウト | タイムアウト | 200 同じ IP | **HTTP 403(0.07 秒)**。接続先 IP は ifconfig.me のまま・証明書エラーなし |
| ipify(補助) | 200 `{"ip":"<public-ip-19>"}`(0.30 秒) | タイムアウト | タイムアウト | タイムアウト | 200 同じ IP | **200 同じ IP**(0.35 秒) |
| VM の `/whoami`(VNet 内) | 200・送信元 **10.40.0.115** | 200・10.40.0.115 | 200・10.40.0.115 | 200・**10.40.0.108** | 200・10.40.0.108 | **接続拒否**(curl 7「Couldn't connect」0 ms)・VM のアクセスログに記録なし |
| `hostname -I` | 169.254.0.2 | 同じ | 同じ | 同じ | 同じ | 同じ |
| 名前解決(`getent`) | 引ける | 引ける | 引ける | 引ける | 引ける | 引ける |
| TCP 22(github.com) | タイムアウト(rc=124) | 同じ | 同じ | 同じ | 同じ | **Connection refused**(rc=1・即時) |
| `*_proxy` 環境変数 | なし | なし | なし | なし | なし | なし |
| 対照 T2 OpenAPI | 200(10.5 秒)。`ip_addr` <public-ip-20>・`forwarded` の手前は 100.100.209.x → 100.64.17.x | **400 `tool_user_error`**(17.2 秒) | **400 `tool_user_error`**(16.9 秒) | **400 `tool_user_error`**(17.1 秒) | 200。`ip_addr` <public-ip-20> | 200。`ip_addr` <public-ip-21>(このエージェントにはポリシーなし) |

- エージェントのエンドポイントは **PE 作成(19:46)の 14 分後の 1 回目(20:00)から 200**。403「Traffic is not from an approved private endpoint.」は一度も出なかった(T2 もエージェントのエンドポイントで 200。上の run の E8 は再現せず)。
- P1〜P3 の失敗は公開側の 4 IP 宛て(または全宛先)だけで、同じ呼び出しの中で VM(VNet 内)には届き、P4 で元に戻った。harness の応答そのもの(モデル呼び出し・名前解決)は 0.0.0.0/0 → None でも 200 だった。
- サンドボックスの送信元は P0〜P2 が 10.40.0.115、P3 から 10.40.0.108 に変わった(サンドボックスの入れ替え。毎回新しい会話)。公開側の送信元は P0・P4・P5 とも同じ 1 つ。
- P5 の `a15-harness-eg` は `a15-harness` と同じモデル・指示・harness で、定義の違いは `rai_config` だけ(P5 の時点で `snet-agent` に NSG・ルートテーブルなし。P4 の直後)。
- TCP 22 は VM(`snet-vm`・既定の送信)からの対照(20:27)も **rc=124 のタイムアウト**だったので、P0〜P4 の結果は harness の制限とは読まない(宛先・経路側の要因を切り分けていない)。P5 だけ即時の拒否に変わった点は harness 側の変化。

### 送信元 IP とサービスタグ(`az network list-service-tags --location japaneast`、changeNumber 246。`tagip.py`、`logs/harness/tagip.log`)

| 観測 | IP | 含むタグ(狭い順) |
| --- | --- | --- |
| T1 harness の shell(P0・P4・P5 で同じ) | <public-ip-19> | AzureCloud.japaneast(/15)・AzureCloud |
| T2 OpenAPI(P0・P4) | <public-ip-20> | AzureCloud.japaneast(/17)・AzureCloud |
| T2 OpenAPI(P5) | <public-ip-21> | AzureCloud.japaneast(/16)・AzureCloud |
| T6 VM(`snet-vm` の既定の送信) | <public-ip-22> | AzureCloud.japaneast(/20)・AzureCloud |
| T2 の X-Forwarded-For の手前の 2 段 | 100.100.209.x・100.64.17.x | どのタグにもない |

- 公開 IP は伏せ字にした。番号は上の run の表の続きで、上の run と同じ値かどうかは比べていない(同じ番号どうしは同じ値)。

- **harness も OpenAPI も、タグで言えば同じ AzureCloud.japaneast だけに入り、サービス別のタグ(AzureCognitiveServices など)には入らない。** ただしプレフィックスは別(harness は /15 の 1 つ、OpenAPI は /17 と /16 の 2 つ。どれも互いに重ならない)。VM の既定の送信とも別。
- 経路の形も違う。OpenAPI は X-Forwarded-For に内部アドレス 2 段(100.100.209.x → 100.64.17.x)が載り、User-Agent は `azure-agents`。harness は X-Forwarded-For に自分の公開 IP と宛先側の LB しかなく(`curl/7.88.1`)、OpenAPI と同じプロキシの段は見えない。
- 送信元で許可リストを作る用途には、どちらもサービスタグでは AzureCloud.japaneast(リージョンの Azure 全体)までしか絞れない。

### 公式の記述 / 実測 / 判定

| # | 項目 | 公式の記述 | 実測 | 判定 |
| --- | --- | --- | --- | --- |
| H1 | harness の shell の公開側への通信は `snet-agent` を通るか | use-tools-skills-copilot-harness:「Shell commands can read or write files and access network resources that the environment permits」。経路(サブネットを通るか)は記載なし | 宛先 /32 の NSG 拒否(P1)・/32 → None(P2)・0.0.0.0/0 → None(P3)で、ifconfig.me・ipify への `curl` がタイムアウト。同じ呼び出しで VM(VNet 内)には 10.40.0.x から届き、外すと(P4)戻った | 記載なし(**新しい知見**: 顧客サブネットを通り、そのサブネットの NSG / UDR で止まる) |
| H2 | RAI ポリシーの egress controls | 同:「govern direct outbound requests from the Foundry-managed harness execution environment」「including shell commands and the harness Web tool」「first matching host rule wins」「In Enforce mode, denied requests return HTTP 403 to the harness environment」 | `defaultAction` Allow+`ifconfig.me` Deny で、shell の `curl https://ifconfig.me/ip` が **HTTP 403(0.07 秒)**、`https://api.ipify.org` は 200(送信元は P0 と同じ) | **一致** |
| H3 | egress controls を付けたときの、規則に当たらない直接通信(付随) | 同:「Foundry preserves the required platform connectivity」。HTTP 以外・VNet 内の宛先の扱いは記載なし | `defaultAction` Allow なのに、VM の `http://10.40.2.10:8080`(VNet 内・8080 番)と `github.com:22` が**即時の接続拒否**(P0〜P4 は前者が 200、後者がタイムアウト)。名前解決は引けた | 記載なし(**新しい知見**。ポート番号と宛先の種類のどちらで拒否されたかは切り分けていない) |
| H4 | harness の送信元 IP | 記載なし | AzureCloud.japaneast(/15)の 1 つの IP。OpenAPI(/17・/16)と同じタグ・別のプレフィックス。X-Forwarded-For に内部の段なし | 記載なし |
| E8' | 名前を変えたときのエージェントのエンドポイント | 記載なし | PE 作成の 14 分後の 1 回目から 200(上の run は同じ名前の作り直しで 70 分以上 403) | 名前を変えた今回は再現しなかった(1 回ずつの比較なので、原因が名前の再利用とは断定しない) |

### 発見

1. **harness の shell から公開側への通信は顧客の委任サブネット(`snet-agent`)を通り、その NSG / UDR で止まる。** 宛先 IP の /32 を NSG で拒否しても、UDR で None に向けても `curl` はタイムアウトし、外すと戻った。12 の「NAT なしでも公開側に出る」は、サブネットに送信制御がないときの挙動で、NSG / UDR を当てれば止められる。prompt agent の OpenAPI / MCP と同じく、**止めるならサブネットに明示的に当てる**(0.0.0.0/0 → None でも harness の応答そのものは返る)。
2. **RAI ポリシーの egress controls は、文書どおりホスト名で止まる。** `ifconfig.me` を Deny にすると shell の HTTPS 要求に 403 が返り、規則にない ipify は通った。ただし付けると、規則に当たらない **VNet 内の 8080 番と公開の 22 番への直接接続も拒否された**(`defaultAction` Allow でも)。VNet 内の社内 API を harness から呼ぶ設計で egress controls を付けるなら、付けた状態で VNet 内の宛先に届くかを確かめる(今回の宛先は 8080 番の HTTP。443 番で届くかは未確認)。
3. **送信元 IP は OpenAPI と同じ AzureCloud.japaneast だが、プレフィックスも経路の段も別。** サービスタグで harness だけ、または Foundry のツールだけを許可する、という絞り方はできない。宛先側で送信元を絞るより、NSG / UDR(サブネット)か egress controls(ホスト名)で出口側を絞るほうが実際的。
4. **アカウント名を変えたら、エージェントのエンドポイントの 403(上の run の E8)は出なかった。** 検証環境を作り直すときは `baseName` を変える(RG 名を変える)、という上の発見 5 の対処で T1 を測れた。

### 対象外にしたもの

| 項目 | 理由 | 概算(実施した場合) |
| --- | --- | --- |
| egress controls を付けた状態で NSG / UDR も当てる(ポリシーを付けた通信がサブネットを通るか) | 目的の 3 点の外。P5 は NSG・UDR なしで測った | NSG・ポリシーは無料・トークン代 ≤ ¥5 |
| P5 の VNet 内 8080 番・TCP 22 の拒否の切り分け(VNet 内の 443 番・公開の 8080 番など) | 目的の 3 点の外(付随の観測) | トークン代 ≤ ¥5 |
| `defaultAction` Deny(許可リスト)・Audit モード | 指示のフェーズは Deny 規則 1 本のみ | 無料・トークン代 ≤ ¥5 |
| harness の Web ツール(URL の取得)・ほかのツール(MCP・Code Interpreter・Web search・素の prompt agent) | Web ツールは目的外。ほかは上の run で測定済み | トークン代 ≤ ¥10 |
| TCP 22 の別の宛先での再試行 | VM からの対照も github.com:22 がタイムアウトしたが、宛先を変えるのは新しいテストになるため | トークン代 ≤ ¥5 |
| hosted agent・NAT Gateway・Azure Firewall・Bastion・Managed VNet | 指示どおり作らない | 上の run の表と 12 の COST.md のとおり |

### 撤去の記録

- 20:28 VM 内の詳細ログを `logs/harness/vmfull-p15h-bundle.log`・`vmfull-server.log` に取得 → 20:29 `deploy.sh down` 開始(`RG=rg-ignite26-verify2`・`LOGDIR=logs/harness`): プロジェクトの capability host 削除(202)→ アカウントの capability host 削除(204)→ プロジェクト削除(202)→ 20:32 アカウント削除 → purge(**約 23 分**。上の run の 24 分・12 の 22 分とほぼ同じ)。
- purge を待つあいだに、時間課金の VM・AI Search(20:34。VM は 1 回目が `az vm delete` の引数誤りで失敗し、20:34:12 にやり直して削除。`deploy.log` に訂正を記録)と PE 4 本(20:34〜20:36)を先に消した。
- 20:55 purge 完了 → RG 削除 → 21:10:41 `az group exists -n rg-ignite26-verify2` = **false**。21:10:54 に `az cognitiveservices account list-deleted` = **[]** を確認。`ResourceGroupDeletionBlocked` は起きず、最後まで残ったのは Cosmos DB(RG 削除の約 15 分の大半)。ほかの RG(rg-decision-models・NetworkWatcherRG)には触れていない。

### 追試の再実行

```bash
cd labs/foundry-probes/probes/12-closed-network
export RG=<新しい RG 名> SCRATCH=<鍵と vm-config.json の置き場> LOGDIR=$PWD/../15-egress-paths/logs/harness OUTS_FILE=$LOGDIR/infra.outputs.json SKIP_PUBLIC=1
./deploy.sh up && ./deploy.sh caphost && ./deploy.sh vmconfig && ./vmrun.sh push
cd ../15-egress-paths
./run15.sh push && ./run15.sh run setup P0 && ./run15.sh run setup2 P0
./run15.sh run t1 P0 ; ./run15.sh run t2 P0
./run15.sh nsg <ipify の IP>/32 … <ifconfig.me の IP>/32 ; ./run15.sh run t1 P1 ; ./run15.sh run t2 P1   # 関連付けから 2 分待つ
./run15.sh nsg-off ; ./run15.sh rt <同じ /32 …> ; ./run15.sh run t1 P2 ; ./run15.sh run t2 P2
./run15.sh rt 0.0.0.0/0 ; ./run15.sh run t1 P3 ; ./run15.sh run t2 P3
./run15.sh rt-off ; ./run15.sh run t1 P4 ; ./run15.sh run t2 P4
# P5: RAI ポリシー(logs/harness/rai-egress.log の PUT)→ 付けたエージェントを作って T1
./run15.sh run setup_eg P5prep <ポリシーの ARM ID> ; ./run15.sh run t1 P5 a15-harness-eg ; ./run15.sh run t2 P5
cd ../12-closed-network
./vmrun.sh sh 'cd /opt/probe/logs && for f in p15-*.log; do echo "######## $f"; cat "$f"; done > p15h-bundle.log'
./vmrun.sh fetch p15h-bundle && ./vmrun.sh fetch server && ./deploy.sh down   # 必ず実行
```
