# 権限の境界(ユーザー割り当て MI × ロール × スコープ)— 実測メモ(2026-11-22)

環境: probe 12 と同じ RG `rg-ignite26-verify`(**実測後に削除済み**)。B1〜B5 は閉域のプロジェクト(`aif-…/proj`)、B2 の反映時間と B6 は `infra.bicep` のパブリックの basic 構成(`aif-…p/pub`、Memory は閉域で非対応のため)。呼び出しは VM 内から IMDS(`client_id` 指定)で取った MI のトークン。ロールはすべて GUID で付与。生ログは `logs/`(`vmfull-*.log` が全文、`roles.log` が割り当ての記録)。

ID(Entra のユーザー・アプリは作らず、RG 内の UAMI 5 つ。B3 の 2 人目と B5 の割り当て主は既存の ID にロールを足して兼用):

| ID | 付けたロール(スコープ) |
| --- | --- |
| id-ops | Foundry User(閉域アカウント・公開アカウント) |
| id-fu | Foundry User(閉域プロジェクト)→ B5 で Foundry Project Manager(閉域アカウント)を追加 |
| id-rt | Foundry Project Runtime User `142bfaed…`(閉域プロジェクト)→ B5 で Foundry Account Owner(閉域アカウント)を追加 |
| id-ac1 | Foundry Agent Consumer(エージェント a13-target・a13-share、公開の a13-mem) |
| id-rd | Reader(閉域アカウント)+Foundry Agent Consumer(a13-share・公開の a13-mem)= B3 の 2 人目 |

## B1 推論の経路 × ロール(閉域プロジェクト、対象 a13-target。HTTP ステータス)

| ID | (a) プロジェクトの Responses(エージェントなし) | (b) エージェントのエンドポイント | (c) プロジェクトの Responses+`agent_reference` | (d) アカウントの `/openai/v1/responses` | (e) エージェント一覧 | (f) `create_version` |
| --- | --- | --- | --- | --- | --- | --- |
| ops(Foundry User @アカウント) | 200 | 200 | 200 | 200 | 200 | 200 |
| fu(Foundry User @プロジェクト) | **200** | 200 | 200 | **401** | 200 | 200 |
| rt(Project Runtime User @プロジェクト) | **403(本文なし)** | 403 | 403 | 401 | 403 | 403 |
| ac1(Agent Consumer @エージェント) | 403 | **200** | 403 | 401 | 403 | 403 |
| rd(Reader @アカウント) | 403 | 403 | 403 | 401 | 403 | 403 |

- (d) の拒否は **401** `PermissionDenied`「lacks the required data action `Microsoft.CognitiveServices/accounts/OpenAI/responses/write`」(403 ではない)。(a)〜(c)・(e)・(f) の拒否は 403 `UserError`「does not have permissions for …/AIServices/agents/write(または read)actions」。
- `https://ai.azure.com` のトークンでもアカウントの `/openai/v1` は通る(ops で 200。probe 08 D と同じ)。
- rt は割り当てから 28〜45 分後に 3 回(14:34 / 14:44 / 14:51)試してすべて 403(`roles.log` で割り当ての存在を確認済み)。

| 公式の記述 | 実測 | 判定 |
| --- | --- | --- |
| rbac-foundry:「`agents/write` を持つ主体はプロジェクトの Responses でモデルを直接呼べる」 | Foundry User @プロジェクトで (a) 200 | **一致** |
| evaluation-permissions:「プロジェクトだけの割り当てでは推論が認可されない(アカウントスコープの Foundry User が要る)」 | プロジェクトの経路は通り、**アカウントの `/openai/v1` だけが 401** | **一部一致**(アカウントの経路に限れば正しい。プロジェクトの経路には当てはまらない) |
| ロール定義: Foundry Project Runtime User の dataActions は `AIServices/responses/*` のみ(調査メモの推論:「エージェントなし推論専用ロール」) | **どの経路も 403** | **推論と不一致**(このロールだけでは Responses を呼べない。用途は不明のまま) |
| agent-endpoint-authorization:「エンドポイントの最小ロールは Foundry Agent Consumer」 | (b) だけ 200、プロジェクトの経路は 403 | **一致** |

## B2 API キー

| 公式の記述 | 実測 | 判定 |
| --- | --- | --- |
| authentication-authorization-foundry の対応表「Agents service: API キー不可」/ agent-endpoint-authorization「API キーはエージェントのエンドポイントに使えない」 | 閉域・公開とも、`api-key` ヘッダーで **アカウントの `/openai/v1/responses` 200・プロジェクトの `/openai/v1/responses` 200・`agent_reference` 200・エージェントのエンドポイント 200・プロジェクトのファイル一覧 200(他人のファイルも見える)・memory store 一覧 200・最適化ジョブ一覧 200**。拒否されたのはエージェント一覧(管理操作)だけ: 403 `unsupported_authentication_type`「Agents service rejected management operation 'GET /agents/v2.0/…'」 | **不一致**(実行系はキーで通る。キーを持つ人はエージェントスコープの制限を迂回できる) |
| ロール定義: `listKeys` はアカウントスコープ | Foundry User @アカウント(ops)200 / Foundry User @プロジェクト・Runtime User・Reader 403 `AuthorizationFailed` | **一致** |
| disable-local-auth:「反映は通常数分、最大数時間。旧キーで **401** `Access denied due to invalid subscription key…` を確認するまで無効化済みとみなさない」 | PATCH(202)14:18:26 → 14:18:27 は旧キーで 200 → **14:19:29 に 403 `AuthenticationTypeDisabled`「Key based authentication is disabled for this resource.」**、以後 3 回連続。Entra の経路は 200 のまま。無効化後はプロジェクト・エージェント・Memory など全経路が同じ 403 | 反映時間は**一致**(約 1 分)/ ステータスと文言は**不一致**(401 ではなく 403) |

## B3 同じエージェントの Agent Consumer 2 人(ac1 と rd、a13-share)

| 観点 | 公式の記述 | 実測 | 判定 |
| --- | --- | --- | --- |
| ファイル | rbac-foundry: ファイルはプロジェクト単位で分離されない。「prompt agent を呼べる主体はプロジェクト内の任意の file ID を `input_file` で参照できる」 | Agent Consumer はファイルの登録・一覧とも 403(`agents/write` が要る)。`input_file` は閉域では誰が送っても 400 `Error while downloading file.`(12 の A4-6)。公開側で ac1・rd が実行者のファイル ID を `input_file` に入れると **200 で受理**されたが、使ったエージェント(a13-mem)の指示が「記憶にないことは UNKNOWN」だったため回答は UNKNOWN で、中身を読めたかは判定できなかった(`vm-sharepub.log`。中立な指示のエージェントでの再測定は時間の都合で未実施)。ファイルのメタデータの GET は 403 | 判定不能(受理はされる。内容が渡るかは未確認) |
| 会話 | 記載なし(hosted は Entra 単位で分離と明記) | ac1 がエージェントのエンドポイントで作った会話 C1 は、rd から items の一覧で 404「Conversation … not found in Endpoint <エージェントの ID> **isolationKey** <…>」、続きの質問も 400 | 記載なし(**呼び出し元ごとに分離されている**) |
| 応答の GET | 記載なし | ac1 本人は 200、rd は 404、Foundry User(ops)もプロジェクトの経路で 404 | 記載なし(分離されている) |
| `previous_response_id` | 記載なし | **rd・fu・ops が ac1 の応答 ID を `previous_response_id` に入れると続きが生成され、ac1 が覚えさせた値(31337、ultramarine-77)を答えた**(2 回再現)。プロジェクトの Responses+`agent_reference` でも同じ | 記載なし(**分離の穴**: GET は 404 なのに続きは読める) |
| 権限のないエージェント | — | ac1 が a12-basic(ロールなし)を呼ぶと 403 | 一致 |

## B4 接続と仕様にない名前

| 公式の記述 | 実測 | 判定 |
| --- | --- | --- |
| connections-add(11-18)「Foundry User・Foundry Owner・Azure Contributor が接続を追加できる」/ ロール定義: Foundry User に `projects/connections/write` はない | Foundry User @プロジェクト・Foundry User @アカウント・Reader の ARM `PUT …/connections/…` はすべて 403 `AuthorizationFailed`(`connections/write`)。Foundry User @プロジェクトの `listsecrets` は 200 | connections-add と**不一致**・定義と**一致** |
| REST 仕様 2026-11-01 の `ConnectionAuthType` に `AgentOnBehalfOfUser` はない(`AgentUserImpersonation` はある) | 操作者で `AgentOnBehalfOfUser` / `AgentUserImpersonation` / `UserEntraToken` の接続を PUT → **3 つとも 200**、GET もそのまま返る。存在しない値は 400 で、エラーが列挙する対応値に **`AgentOnBehalfOfUser`・`UserTokenAndProjectManagedIdentity`・`DeveloperConnection`・`RegistryIdentity`・`Basic`**(公開仕様にないもの)が含まれる | 仕様と**不一致**(サービスは受理する) |
| REST 仕様・SDK 2.11.0 のエンドポイント認可は `Entra` / `BotService*` のみ。Learn は `AzureRbac`・`AgentBlueprint` | 既定値は `[{"type":"Entra","isolation_key_source":{"kind":"Entra"}}]`。データプレーンの PATCH `agent_endpoint.authorization_schemes` は `AzureRbac`・`AzureRbac+AgentBlueprint`・**存在しない `NoSuchScheme`** のどれも 200 で、GET にそのまま残る(`isolation_key_source` は消える)。`NoSuchScheme` のままでも Agent Consumer の呼び出しは 200 | 記載なし(**値の検証がなく、入れた値が実際に効いているかも外から分からない**)。検証後に既定へ戻した |

## B5 ロール割り当ての条件と metrics read(ARM、閉域アカウント)

| 公式の記述 | 実測 | 判定 |
| --- | --- | --- |
| rbac-foundry / hosted-agent-permissions「Project Manager が付けられるのは Foundry User のみ」/ ロール定義の条件: Agent Consumer と Foundry User | fu(+Project Manager @アカウント)が id-ac1 に: Foundry User @アカウント 201・@エージェント 201、**Agent Consumer @アカウント 201**、Reader・Log Analytics Reader・Monitoring Reader は 403「has an authorization with **ABAC condition that is not fulfilled**」 | Learn と**不一致**・定義と**一致**(Agent Consumer も付けられる) |
| ロール定義: Account Owner の条件は Agent Consumer・Foundry User・ACR 2 種・Log Analytics Reader | rt(+Account Owner @アカウント): **Log Analytics Reader 201**、Reader・Monitoring Reader 403(ABAC)、Foundry User / Agent Consumer は直前に fu が付けたため 409 `RoleAssignmentExists`(403 ではない = 条件は通過) | 定義と**一致** |
| cost-management-permissions「すべての Foundry ロールで利用量が見える」/ 定義: Project Manager に `Microsoft.Insights/metrics/read` はない | `GET …/providers/Microsoft.Insights/metrics`: Foundry User @アカウント・Account Owner・Reader は 200(値あり)、**Project Manager は 200 だが `{"value":[]}`**(エラーにならず空) | cost-management-permissions と**不一致**(PM には見えない。しかも空で返るので気づきにくい) |

※ B5 で id-ac1 に Foundry User @アカウントが付いたため、B5 以降の ac1 の結果(metrics の 200 など)は B1・B3 の条件と異なる。付与したものは RG ごと削除済み。

## B6 Memory の `x-memory-user-id`(公開プロジェクト、memory store `ms13`、`memory_search_preview` の scope=`{{$userId}}`)

| 公式の記述 | 実測 | 判定 |
| --- | --- | --- |
| memory-usage:「`x-memory-user-id` があればその値を user ID に使い、なければ呼び出し元の TID / OID」(送るための権限要件の記載なし) | **プロジェクトの Responses+`agent_reference`(Foundry User)ではヘッダーが効く**: ops が `user-bob` で書いた記憶は scope `user-bob` に入り(low-level の `items:list` で確認)、**別の ID(実行者、Foundry User @アカウント)が同じヘッダーを付けると「エメラルドグリーンです」と他人の記憶が返った**。ヘッダーなしは UNKNOWN | 記載どおり(**権限要件がないことがそのまま穴になる**: プロジェクトの経路を呼べる人は、他人の scope 名を知れば記憶を読める) |
| 同上 | **エージェントのエンドポイント(Agent Consumer)ではヘッダーが無視される**: ac1 が `user-alice` を付けて書いた記憶は `user-alice` に入らず(`items:list` も検索も空)、ac1 はヘッダーの有無にかかわらず自分の記憶を読めた。rd が `user-alice` を付けても UNKNOWN。実行者がエンドポイントに `user-bob` を付けても UNKNOWN | 記載なし(エンドポイント経由は TID / OID で固定) |
| — | low-level API(`search_memories` / `items:list`): Agent Consumer は 403(`agents/read` が要る)、Foundry User は任意の scope を読める。TID / OID 由来の scope 文字列の形式は 7 通り試して特定できず(`:` と `/` などは 400) | — |

## つまりどころ・SI 判断メモ

- **Project Runtime User 単体では推論できない。** 実行専用の ID にはエンドポイントを呼ぶなら Agent Consumer(エージェントスコープ)、エージェントなしでモデルを呼ぶなら Foundry User @プロジェクト(= エージェントの作成もできてしまう)。最小権限の「モデルだけ呼べる」ロールは組み込みにない。
- **API キーが残っている限りエージェントスコープの設計は迂回できる**(エージェントのエンドポイントもファイルもキーで通る)。`disableLocalAuth=true` は約 1 分で効いたが、拒否は 403 `AuthenticationTypeDisabled` なので監視の条件を 401 で書かない。
- **`previous_response_id` は呼び出し元で分離されない。** 応答 ID をクライアントに返す設計(ブラウザーに保持させる等)では、ID が漏れると他人の続きが読める。応答 ID はサーバー側で利用者に紐付けて検証する。
- **Memory の `{{$userId}}` は、プロジェクトの経路ではヘッダーで任意の scope に切り替えられる。** 利用者が直接プロジェクトの Responses を呼べる構成(Foundry User を配る構成)では記憶の分離が成り立たない。利用者には Agent Consumer だけを付け、エンドポイント経由にする(エンドポイントではヘッダーが無視された)。
- 接続の作成は Project Manager 以上に寄せる(Foundry User では作れない。connections-add の記述は誤り)。Project Manager は利用量メトリクスを見られない(空で返る)ので、コスト確認役には別途 Monitoring Reader 等が要る(PM 自身はこれを付与できない)。

## 再実行

```bash
cd labs/foundry-probes/probes/13-rbac-boundaries   # 前提: 12 の deploy.sh up / caphost / vmconfig、vmrun.sh push
./probe.sh roles-agent      # エージェントの作成とエージェントスコープの割り当て(伝播待ち 5〜15 分)
./probe.sh b1; ./probe.sh b2; ./probe.sh b3; ./probe.sh b4
./probe.sh roles-b5; ./probe.sh b5; ./probe.sh b6
./keys_timing.sh disable 150   # 公開アカウントの disableLocalAuth の反映時間
```
