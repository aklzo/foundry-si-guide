# 技術選定ガイド(実装検証ベース)

> **最終更新:** 2026-07-31 / **版:** 第3版(Wave 1+2+3 反映)/ 2026-09-26 注記追加(実測内容は書き換えず、公式側の変化で前提が崩れた箇所に「※2026-09-26」を付記: 罠 10)/ 2026-09-29 全ラボを agent-framework 1.19 / openai 3.20 でオフライン再検証 / 2026-09-30 §5 委任アクセス(Port 15)を追加し同日ライブ検証の結果を反映(版の変化で前提が変わった箇所に「※2026-09-29」を付記: 罠 3・4・10)/ **2026-10-06 全ラボを agent-framework 1.20 / openai 3.24 で再検証しライブも再実施(Port 15 を除く)→ §6 を追加**、版の変化で前提が変わった箇所に「※2026-10-06」を付記(§1-1・罠 3・12・13、§5-2・9・10) / 2026-10-14 注記追加(ラボは再実行していない。公式・パッケージ側の変化で前提が変わった箇所に「※2026-10-14」を付記: §5-1・5-10・§6-1・6-2・6-3、**§6-5 を新設**)
> **出典の分離:** 本ドキュメントは **labs/ での実装検証から得たナレッジのみ**を集約する。公式ドキュメント調査由来の知見は [docs/survey/](./survey/README.md)(features / architecture / proposal)にあり、混在させない。各主張には検証元(どのラボ/ポートで実証したか)を付す。
> **検証環境:** agent-framework 1.10〜1.13 / azure-ai-projects 2.4 / Microsoft Foundry(Japan East、gpt-5.4-mini)/ 2026-07 時点。**再検証:** 2026-10-06 に agent-framework-core 1.20 / openai 3.24 / azure-ai-projects 2.8.0(MAF の Foundry 連携を使うポートは 2.7.0)で全ラボを再検証し、Port 15 以外はライブも再実施(Japan East、gpt-5.4-mini)。フレームワークの進化が速いため、**版が変われば結論も変わりうる**。

## 1. 選定の実証済み判断基準

[learning-plan](./learning-plan.md) の問い「ポータルで足りるか / MAF が必要か / 他 FW を選ぶべきか」に対する、実装で裏が取れた範囲の回答。

### 1-1. マルチエージェント協調の分水嶺(Port 3・7・13 で実証 — 2軸3値)

協調の選び方は「**制御を誰が決めるか(コード/LLM)**」×「**制御が戻るか(戻る/移る)**」の2軸で整理できる:

| 型 | 制御 | 応答 | MAF での器 | 例 |
| --- | --- | --- | --- | --- |
| **グラフ** | コード(仕様で決まる) | — | Workflow(core のみ) | 直列・並列・分岐・ループ(Port 1-4, 7) |
| **相談型(agent-as-tool)** | LLM が選ぶ | **呼び出し元に戻る** | Agent+動的ツール生成(core のみ) | 通信グラフ制約下の協調(Port 13) |
| **担当交代(handoff)** | LLM が選ぶ | **制御ごと移る** | HandoffBuilder(別パッケージ・会話型) | サポートのエスカレーション等 |

- MAF core に first-class handoff は**ない**。`HandoffBuilder` は別パッケージ(agent-framework-orchestrations)で、全結線メッシュ+human-in-loop 既定の**会話型**設計。one-shot パイプラインに使うと「グラフなら決定的に保証される性質(順序・終了)が全部確率的になる」(Port 7 で比較実装して実証)。※2026-10-06: orchestrations 1.3.0 の `enable_return_to_previous(False)`(人のターンの後に開始エージェントへ戻す)と生成 handoff の `call_id` 照合は、利用者のターンがない one-shot には効かず、3 制約(参加者は実 `Agent` 限定・persistence フラグ必須・autonomous mode と終了条件)も不変 — 1.2.0 / 1.3.0 で同じモックに流して挙動が同一(Port 7)。`enable_return_to_previous(False)` は「トリアージをハブにした会話型」を書くときの部品(Port 3)
- 移植して分かった副次的事実: **元アプリの「handoff」の多くは LLM が委譲先を選んでいない固定シーケンス**(AG2 Swarm の AfterWork リング等)。この場合グラフ化で失うものはなく、得るもの(型付き state、テスト可能性、スパン可視化)だけがある
- 逆に「ユーザーとの会話中に、次に誰が話すかを LLM が決める」型(サポートのエスカレーション等)は OpenAI Agents SDK / AG2 / MAF orchestrations が本質的に楽
- 公式・業界のフレームワーク(AAC 5 パターン、CAF 単一 vs マルチ判断、LangChain 4 型)との対照は [survey/architecture/11 §6](./survey/architecture/11-decision-frameworks.md) 参照(2 軸 3 値と AAC の Routing 軸は同型)

### 1-2. グラフ化の対価は観測性(Port 1・4・7)

手続き的な直列呼び出しを MAF Workflow に「昇格」させるコストはほぼゼロ(Executor+エッジの定型)。見返りは:
- ノード単位のスパン(`executor.process`)、エージェント単位(`invoke_agent`)、ツール単位(`execute_tool`)が**自動で** App Insights に出る
- **ループの発火回数がスパン数でそのまま見える**(Port 7 のリング×2周、Port 4 の文書別採点×6)
- 進捗イベント(intermediate output)が UI/CLI の構造化された進捗表示になる

トレース配線は `configure_azure_monitor(connection_string=...)` の実質2行(Port 1)。**「Foundry に載せる動機は観測性が最初」**という survey 側の仮説は実装でも成立した。

### 1-3. フレームワーク書き換えコストの実測感(全ポート)

| 元 → MAF | 書き換えの実態 | 検証元 |
| --- | --- | --- |
| Agno(手続き直列) | 直訳。Executor 化のみ | Port 1 |
| 素 SDK(gather 並列) | `add_fan_out_edges` / `add_fan_in_edges` が first-class。むしろ堅くなる | Port 2 |
| OpenAI Agents SDK(handoff) | 構造化出力+switch-case で明示化。1行→数十行だがテスト可能に | Port 3 |
| LangGraph(StateGraph) | ノード→Executor、条件エッジ→switch-case、**無型共有 dict→型付きメッセージ**。規律が強制される | Port 4 |
| mem0(記憶) | ストア API の置換は素直。**同期 add→LRO+debounce の意味論差**が本丸 | Port 5 |
| AG2 旧 Swarm | UPDATE_SYSTEM_MESSAGE 等の「長寿命エージェントの必要悪」がステートレス Agent.run では純関数に縮退 | Port 7 |
| DuckDB ローカル分析 | Code Interpreter 置換は「データの行き先と課金対象」の置換。ツールは素の dict がパススルー | Port 8 |
| LangChain ルーター(3DB 振り分け) | 三段カスケード約150行が Foundry IQ の宣言+プロンプトに消滅。ただし可観測性・単体テスト可能性を失う | Port 10 |
| ADK + FastAPI(常時稼働) | hosted agent 化で変わるのは周辺3点(資格情報/観測/HTTP 面)。Routines で cron 配管が不要に | Port 11 |
| Google ADK + Gemini Live | Voice Live は Realtime API 互換+additive 拡張。音声非依存コアの分離が移植とテストの両方に効く | Port 12 |
| Agency Swarm(通信グラフ) | 1行の魔法が20行×3に分解される代わりにテスト可能性を獲得。「戻るか戻らないか」が Workflow に載るかの試金石 | Port 13 |
| ガバナンス層(素SDK 2本) | MAF middleware 3種で再現。short-circuit 2方式(見せて続行/全停止)の選択がガバナンス設計そのもの | Port 14 |

共通パターン: **書き換えで元コードの欠陥が見つかる**(質問本文がアグリゲータに未達 / dead code の context_variables / 「補正ループ」が実は単発 DAG)。型付きグラフへの移植自体がコードレビューとして機能する。

## 2. 実装ナレッジ集(ハマりどころ)

運が悪いと半日〜1日溶ける系。すべて実測。

1. **Bicep 作成の Foundry プロジェクトは MI にモデルのデータプレーン権限が付かない**(ポータル作成は自動付与)。Memory(プレビュー)がストア構成のモデルをプロジェクト MI で呼ぶため 401 ResourceError になる。`Cognitive Services OpenAI User` をプロジェクト/アカウント MI に割り当てる(shared.bicep 参照)。**RBAC 伝播は5〜15分・ノード間で不均一**(片方のプローブが通った後もテストが数分 401 を返した)— Port 5
2. **データプレーンは Bicep の外**。AI Search のインデックス、Memory のストアは ARM で作れず、「Bicep → セットアップスクリプト」の**2段デプロイが定型**。IaC 完結を前提にした見積もりは崩れる — Port 4・5
3. **依存の版ピン3点**: (a) `mcp>=1.24,<2` — agent-framework の上限要求は推移的依存では強制されず、mcp 2.0 が入ると接続時 AttributeError(`InitializeResult.protocolVersion`)。(b) async の azure-search-documents は `aiohttp` が別途必要。(c) `from __future__ import annotations` はツールスキーマ推論・テストに `get_type_hints` 前提を強いる — Port 6・4・1。※2026-09-29: MAF 1.19 でも `mcp<2` は必要(`agent-framework-core[all]` / `-foundry-hosting` 自身が `mcp<2` を宣言。mcp 2.2 で同じ AttributeError を再現 — Port 6・10)。加えて **`agent-framework-foundry` 1.13.1 は `azure-ai-projects<2.7.0` を要求**し、MAF の Foundry 連携と同居させると projects は 2.6.1 止まり(2.7.0 の新機能は入らない)。同パッケージは廃止済みの `azure-ai-inference` も依存に持ち続ける — Port 11。※2026-10-06: MAF 1.20 でも `mcp<2` は必要(mcp 2.3 は型を別パッケージ `mcp-types` に移し `InitializeResult` は `protocol_version` のみ — Port 6・10)。`agent-framework-foundry` 1.14.0 は `azure-ai-projects<2.8.0`(2.7 系は入る、2.8.0 の GA API〈Agent Optimization・data generation・evaluator lifecycle〉は MAF の Foundry 連携と同居できない)。Foundry 連携を使わないラボ(Port 5・9、foundry-probes)は 2.8.0 に上げた
4. **MCP のヘッダー注入**: MAF の `MCPStreamableHTTPTool` の `header_provider` は **call_tool 時のみ**で接続時(initialize / tools/list)に付かない。全リクエスト認証のサーバー(GitHub リモート MCP 等)では `httpx.AsyncClient(headers=...)` を `http_client` に渡す — Port 6。※2026-09-29: この癖は 1.12.1 固有で **1.13.0 で解消**(接続時にも注入)。1.19.0 で**同一オリジンにだけ注入する `static_headers`** が追加され、自前 `http_client` にヘッダーを持たせる方式は MAF の docstring 上「漏洩しうる」扱いになった。Port 6・10 は `static_headers` に移行済み(1.18 以前は未知の引数を黙って捨てるため無認証接続になる — 下限 1.19 が必須。ライブ未検証)
5. **Foundry Memory の意味論**: mem0 の同期 `add` と違い **LRO+debounce(update_delay 既定300秒)**。「書いた直後に読む」は成立しない前提で UX・テストを設計する(`update_delay=0`+`previous_update_id` チェーン+完了待ちで吸収可能)。認証は Entra のみ・API キー不可 — Port 5
6. **reasoning 系モデルは temperature を受け付けない**。「温度で多様性」は死んだ技法 — ペルソナ差し替えで翻訳する(MoA 系の移植で必須)— Port 2
7. **検索をどの層で持つかは契約論点**。Foundry の Web search ツールは DPA 対象外・別課金(survey 側の調査結果)。ラボでは自前 DDG 検索を既定にした — クロージャ+`MockTransport` でテスト可能になる副次メリットもある — Port 1・3・4
8. **Foundry プロジェクトの MI は再デプロイでローテーションしうる**。ARM 制約でロール割り当て名に実行時値を使えないため、id 固定名だと**旧 principal への孤児割り当てが名前一致で温存**され PermissionDenied の温床になる。対策: RBAC を principalId パラメータの第2段テンプレート(roles.bicep)に分離 — Port 9
9. **クラウド評価の権限は3層**: builtin 評価器の `initialization_parameters.deployment_name`(ジャッジ用デプロイ=評価コストは自分持ち)/ プロジェクト MI(Foundry User + OpenAI User)/ **提出ユーザー自身の Foundry User**。エラーは一律 PermissionDenied で actor が分からず、切り分けに時間を溶かす — Port 9
10. **Routines の REST は `?api-version=v1` 必須**(Learn の例に記載なし・欠くと BadRequest)。プレビュー機能はサブ機能ごとにリージョン集合が違う(Routines 8 / Memory 19 / hosted agents 31) — Port 11。※2026-09-26 注記: Routines は 2026-09-24 に GA。use-routines(ms.date 2026-08-27)は `api-version=v1` 必須を本文に明記し、リージョンも「UK West / Switzerland West / Japan West / UAE North / Norway East を除く全リージョン」に拡大(8 リージョン限定は解消)。Python SDK 面は `client.beta.routines` のまま([casebook 02 P-A11](./survey/casebook/02-pitfalls-index.md#b-agent-service-コア))。※2026-09-29: `Foundry-Features: Routines=V1Preview` は現行の REST 仕様から消え(任意ヘッダーの値は `V2Preview`、SDK 2.5.0 以降が自動付与)、Port 11 はヘッダーを外した(ライブ未検証)
11. **Voice Live のリージョンは「機能×モデル×事前デプロイ」の3段で読む**: Japan East は Voice Live 対応だが gpt-realtime 系ネイティブ音声モデル非提供。マネージド提供モデルはデプロイ不要(Bicep 差分ゼロ) — Port 12
12. **middleware の関数形態は `from __future__ import annotations` で型判定が壊れる**(MiddlewareException)。デコレータ明示(`@function_middleware` 等)が必須 — 罠3(c)の middleware 版。short-circuit は2方式で意味が別: `context.result` セット=拒否をモデルに見せてループ続行 / `MiddlewareTermination`=全停止 — Port 14。※2026-10-06: agent-framework-core 1.20 で文字列注釈もクラス名で判定されるようになり、前段の MiddlewareException は解消(1.19 以前はデコレータ明示が必要。版差をテストで固定 — Port 14)
13. **オフラインテスト戦略は Protocol 注入で統一できる**: LLM は `SupportsRun`(`.run()→.text`)、外部サービスはコンストラクタ注入 — ScriptedAgent / MockTransport / fake ストアで **約470テストをネットワークなしで回せた**(14ポート合計)。「エージェントはテストできない」は設計の問題 — 全ポート。※2026-09-29: 依存を最新化(agent-framework 1.19 / openai 3.20)した時点の 14 ポート合計は **544 件 passed**(+hosting extra 込みで 1 件。いずれもネットワーク不要)。※2026-10-06: agent-framework 1.20 / openai 3.24 で 14 ポート計 **586 件**(Port 15 を含む 15 ポートで 829 件)passed。オフラインで通っていてもライブで見つかった不具合が 6 件あった(§6)— オフラインテストは「ライブを省く」ためでなく「ライブで見る点を絞る」ためにある

## 3. パターン別リファレンス(どこを見るか)

| 作りたいもの | 実証済みの型 | コード |
| --- | --- | --- |
| 直列パイプライン | Executor+エッジ、進捗は intermediate output | [trend-analysis](../labs/maf-ports/ports/trend-analysis/) |
| 並列実行+合流 | `add_fan_out_edges` / `add_fan_in_edges`(fan-in はエッジ定義順で決定的) | [mixture-of-agents](../labs/maf-ports/ports/mixture-of-agents/) |
| ルーティング/トリアージ | 構造化出力(Literal ルート)+`add_switch_case_edge_group` | [research-handoff](../labs/maf-ports/ports/research-handoff/) |
| 自己補正 RAG | 採点→分岐→書換→フォールバックのグラフ+AI Search(埋め込みは MAF の `OpenAIEmbeddingClient` — 2026-10-06) | [corrective-rag](../labs/maf-ports/ports/corrective-rag/) |
| 長期記憶 | `beta.memory_stores`(SDK)+Protocol 注入 | [travel-memory](../labs/maf-ports/ports/travel-memory/) |
| 外部システム連携 | リモート MCP+`http_client` 認証 | [github-mcp](../labs/maf-ports/ports/github-mcp/) |
| 役割リング(旧 Swarm) | 型付き context を運ぶ明示グラフ+ループエッジ | [game-design-team](../labs/maf-ports/ports/game-design-team/) |
| サーバー側コード実行 | `get_code_interpreter_tool` + Files API | [data-analysis-ci](../labs/maf-ports/ports/data-analysis-ci/) |
| 評価駆動の品質ループ | サイクリックグラフ+クラウド評価(evals API) | [critique-loop](../labs/maf-ports/ports/critique-loop/) |
| マルチソース RAG 委譲 | Foundry IQ(KS×N→KB→MCP) | [db-routing-iq](../labs/maf-ports/ports/db-routing-iq/) |
| 常時稼働+スケジュール | hosted agent(ResponsesHostServer)+ Routines。本番リリース手順(ピン留め→候補→昇格)は `--candidate` / `--promote` | [hn-briefing-hosted](../labs/maf-ports/ports/hn-briefing-hosted/) |
| 音声エージェント | Voice Live(3層分離: コア/テキスト/音声) | [claim-voice-live](../labs/maf-ports/ports/claim-voice-live/) |
| 相談型協調(通信制約) | agent-as-tool(許可ペア分の talk_to_* 動的生成) | [services-agency](../labs/maf-ports/ports/services-agency/) |
| ガバナンス/監査 | middleware(ポリシー割込+信頼ゲート+ハッシュ連鎖監査) | [governed-agent](../labs/maf-ports/ports/governed-agent/) |
| 利用者の権限で動かす(委任) | hosted agent × アプリ管理 OBO(判定点 APIM / MCP サーバー)。toolbox 経由(方式 C)は設計メモ | [delegated-access-hosted](../labs/maf-ports/ports/delegated-access-hosted/) |

先行実装: [agentic-search-maf](../labs/agentic-search-maf/)(評価ループ付きリサーチ。Rust からの移植)。

各ポートの **Azure アイコン付きアーキテクチャ図**(リソース配置・認証・課金注記)は `ports/<port>/docs/architecture.png`(README 冒頭に埋め込み済み。再生成手順は [tools/README.md](../labs/maf-ports/tools/README.md))。

## 4. 未検証領域(次の実験候補)

実装で確かめていないため、本ガイドではまだ語れないもの(Wave 2 候補 → [INVENTORY.md](../labs/maf-ports/INVENTORY.md)):

- ~~Code Interpreter / Voice Live / Foundry IQ / Routines / hosted agent 化~~ → **Wave 2 で検証済み**(上記参照)
- ポータル(prompt agents)だけでどこまで組めるかの限界線(コード無しの上限)
- 音声入出力の実機検証(Wave 2 は WebSocket 接続+ツールループまで。マイク環境が必要)
- Toolbox 経由のツール共有、エージェント向けガードレール(プレビュー)の実運用。**toolbox 経由の利用者委任(OAuth identity passthrough+`FoundryToolbox`)** — Port 15 に方式 C の設計メモとオフラインの配線あり。着手条件は `FoundryToolbox` の stable 化か、利用者×接続ごとのブラウザ同意を回す手段
- Port 15(委任アクセス)の最新依存でのライブ再実施(Entra のアプリ登録・テスト用ユーザー・権限付与を伴うため保留 — 2026-10-06)
- hosted agent の版束縛の条件の切り分け(§6-2: MAF ホスティングと Agent Server SDK だけの最小エージェントで結果が割れた)
- トレース本文の保護テーブル(`AppGenAIContent`)を早期フラグ登録後に Protected にした効果(サブスクリプション全体の設定変更になるため未実施 — §6-1)
- マルチリージョン・高可用構成の実証(現状は単一リージョンのラボ構成)

## 5. 委任アクセス(利用者の権限でエージェントを動かす)— Port 15、2026-09-30

[labs/maf-ports/ports/delegated-access-hosted](../labs/maf-ports/ports/delegated-access-hosted/README.md)。hosted agent × アプリ管理の OBO(2026-09-28 公開の公式手順)で、社内文書(AI Search のセキュリティフィルター)と基幹 API(MCP)への操作を利用者のロールで変える。最終判定点を **APIM(方式 A)** と **MCP サーバー自身(方式 B)** の両方で実装して比較した。オフライン検証(239 テスト)と SDK ソースの確認に加え、**2026-09-30 にライブ検証済み**(japaneast・gpt-5.4-mini・新規テスト用ユーザー 2 人 × 方式 A / B。検証後に Azure・Entra のリソースは全削除)。1〜7 は実装時の知見、8〜11 はライブで分かったこと。

1. **「エージェントの権限 = 利用者の権限」は Foundry の機能ではなく部品間の契約で作る。**Foundry は `x-client-*` の転送と `x-ms-user-identity` による利用者の識別(会話の分離)だけを担い、トークンの取得・同意・更新・再認証・下流の判定はアプリ側に残る。ヘッダー名・スコープ・ロール名の綴りが 1 つずれると例外でなく「権限なし」で黙って動くので、名前を 1 モジュールに集め Bicep・ポリシー・`.env.example` との一致までテストで固定する — Port 15。※2026-10-14: 公式 4 ページ(isolate-sessions-per-user / multiplex-session-users ほか、ms.date 2026-10-13。新機能ではなく文書の整理)が、`x-ms-user-identity` で委任された利用者どうしはプラットフォームが隔てない(境界は委任あり / なしの間だけ)、意図的にセッションを共有する multiplex ではコンテナが自分で保存するデータは自動では分かれない、プロジェクトの Foundry User は全利用者のセッションを一覧・管理できる、と明文化した。「Foundry が担うのは識別と会話の分離だけ」という本項の結論の裏付けで、どの利用者をどのセッションに入れるか・コンテナ側の保存をどう分けるかもアプリ側に残る(casebook P-H30)
2. **MAF の `ResponsesHostServer` は利用者ごとの資格情報が要るツールに使えない**(エージェントと MCP ツールを起動時に 1 回だけ接続し、要求ヘッダーをツールへ渡さない)。Agent Server SDK(`azure-ai-agentserver-responses`)のハンドラーで要求ごとに MAF Agent を組む。hosted 化の摩擦は「ツールの出所」(Port 11)に加えて「ツールの資格情報が誰のものか」でも決まる — Port 15。※2026-10-06: `agent-framework-foundry-hosting` 1.0.0b261002 の要求ごとのファクトリ(request-scoped agent factories)でも置き換えられない — ファクトリは引数を取らず、公開されている要求の文脈は call_id / user_id / session_id だけで `x-client-*` に届かない。中間層が 401 + `WWW-Authenticate` に写すための応答 metadata もエージェントから設定できない(ソース確認+オフラインテストで固定。MAF が渡せるようになったら落ちるテストを置いた)。一方、公式が推奨に据えた toolbox 経由の委任では「ファクトリ+`FoundryToolbox`」が最短路で、**エージェントを要求間で使い回すと 2 人目の要求が 1 人目の `x-agent-foundry-call-id` で toolbox に届き、エラーなしで別人の権限になる**(オフラインで再現。casebook P-H26)
3. **トークンの露出面は 7 か所**(プロンプト・ツール引数・ツール結果・ログ・例外・GenAI メッセージのトレース記録・resilient モードの永続化)。特に **resilient / durable background モードは `client_headers` を復旧用に永続化**し、**GenAI のメッセージ内容のトレース記録は SDK 既定で有効**(ツール結果がミドルウェアより前に span に載る)。前者は起動拒否、後者は `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false` を既定にした — Port 15
4. **mcp 1.30 + MAF 1.19 では `tools/call` の HTTP 401 / 403 がツール結果にならず、セッションが死んで再接続・再送でハングする。**エージェントの HTTP トランスポートで 401 / 403 を JSON-RPC エラーに写し、403 は「権限がありません」、401 は再認証要求として中間層へ返す(アプリ権限へは切り替えない)— Port 15
5. **ゲートウェイ判定(方式 A)は「バックエンドを APIM 以外から呼べないこと」を別途保証して初めて成立する。**APIM Consumption は VNet も静的 IP も持たないので、共有シークレットのヘッダーで迂回を塞いだ(より強い手段は APIM のマネージド ID トークン、または v2 / Premium + VNet)。APIM は本文を見ないため判定粒度は API(= MCP サーバー)単位 → **MCP サーバーの分け方が権限境界になる**。実務の結論は「入口 A(宛先・スコープ・サーバー単位のロール)+ 中身 B(文書の絞り込み・ドメイン判定・監査)」の併用 — Port 15
6. **リードタイムはコードより管理者作業に出る。**アプリ登録 2 つ・管理者同意 3 件・アプリロール割り当て(Entra)と、`UserIdentityImpersonation/action` を含むカスタムロール(組み込みロールに無い)・Foundry Agent Consumer の割り当て(Azure RBAC)で、顧客側の担当ロールが最低 3 種類に分かれる。セットアップスクリプトを「既定 dry-run で全 Graph / ARM 呼び出しを表示」にして申請書に貼れるようにした — Port 15
7. **一覧の取得コスト:** 利用者に見えている MCP サーバー 1 つにつき、ツール呼び出し前に約 5 要求(疎通確認+MAF の initialize / initialized / ping / tools/list)。経理担当で 1 ターン 15 要求 — APIM Consumption の呼び出し課金とレイテンシに効く — Port 15
8. **権限による出し分けは方式 A / B ともライブで期待どおり、1 問の所要時間に差は出なかった**(A 9.7〜11.9 秒 / B 10.5〜13.7 秒、同じ質問 ×3)。時間はモデルの推論とツール往復が支配し、APIM のホップは誤差に埋もれる → **判定点の選定にレイテンシは効かない**。選定軸は統制の所有者(セキュリティ担当がポリシーを持つか)と判定の粒度(サーバー単位で足りるか)。ポリシー XML(2 段の validate-jwt・on-error の `WWW-Authenticate`・Named Values)も実 APIM で受け付けられた — Port 15
9. **hosted agent のプラットフォーム側トレースは会話全文を記録し、コンテナ側では止められない。**コンテナで `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false` にしても、`cloud_RoleName == "responsesapi"` の `chat` / `invoke_agent` スパンが `gen_ai.input.messages` / `gen_ai.output.messages` にツール結果まで残し、経理担当にしか見えない文書 ID が App Insights に出た(トークンは 0 件)。公式と突き合わせると、プロジェクトへの App Insights の**接続**が「プラットフォーム側トレースの有効化」と「同じ接続文字列のコンテナへの注入(コンテナのログも自動で同じ先へ)」を同時に起こし、止め方は接続の解除だけ。→ **設計の最初に「中身を残してよいか・誰が読めるか」を決め、App Insights を集約 / 2 つに分離(接続先 = 中身入りで閲覧者を絞る、別の App Insights = コンテナのログで運用)/ 接続しない、から選ぶ**。判断基準は [architecture 09 §3.6](./survey/architecture/09-operations.md#36-トレースに会話の中身を残すかhosted-agent-の選定基準)、ヒアリング項目は proposal 01 の 4-7(casebook P-O12)— Port 15。※2026-10-06: 公式の how-to「Restrict access to sensitive content in Foundry traces」(preview)が**第 4 案「同じ App Insights のまま中身だけ専用テーブル `AppGenAIContent` に隔離し、Protected + Privileged Monitoring Data Reader で読み手を絞る」**を示し、移行日 2026-09-30 以降は既定でこの振り分けになると書く。しかし **2026-10-06 の japaneast 実測(サブスクリプションの feature flag 未登録、MAF 1.20 のクライアント側スパン)では、本文は `AppDependencies` の `gen_ai.*` 属性と `AppGenAIContent` に二重書きされた**(`_MS.GenAIContentId` で対応、専用テーブルは約 5 分遅れ、`AppTraces` にもメッセージイベント)→ 保護テーブルだけでは本文は隠れない。採用するなら「従来テーブルに本文が残っていないこと」を KQL で確かめる工程を必須にする(casebook P-O13)
10. **会話の続きは利用者ごと・agent ごとに分かれる。**`x-ms-user-identity` が違うと他人の response ID は 404、同じ利用者でも別の hosted agent(方式 A ↔ B)で作った ID は 404。中間層はこれを 502 に丸めず「会話が見つからない」として返す。前段ルーターで別の agent に切り替える blue-green は会話を引き継げない前提になる(casebook P-H24)— Port 15。**同じ agent の版更新なら会話は続く**が、応答する版はセッションのコンテナで決まり、起動中(idle_timeout 以内)は旧版のまま・休止明けに現行版へ移る。ロールバックも同じで、旧版はセッションが残る限り `force=true` なしでは削除できない(`force=true` なら同じセッション ID のまま現行版で続き、履歴も `$HOME` も残った)。版の明示固定も休止明けは効かなかった(公式と食い違い)→ 全会話をすぐ移す修正は旧版の `force=true` 削除で行い、新版は旧版の履歴・`$HOME` に後方互換を持たせる([architecture 09 §6.3](./survey/architecture/09-operations.md#63-エージェントのバージョニングとリリース)、casebook P-H25)— foundry-probes probe 10(2026-09-30)。※2026-10-14: multiplex-session-users(ms.date 2026-10-13)が「他人の `previous_response_id` での継続は失敗する」と明記し、本項の 404 の実測と一致した。MAF ホスティングの既定ストアは更新後に旧来のデータを読まない(§6-5)ので、ホスティングライブラリの更新も「会話を引き継げない」リリースとして扱う(casebook P-F20)
11. **デプロイで踏むもの:** hosted agent の作成にはデプロイ実行者の **Foundry User** が要る(サブスクリプション所有者でも自動では付かず `agents/write` で拒否、反映まで約 5 分 — P-I01)。Foundry アカウント配下のプロジェクトとモデルデプロイを 1 つの Bicep で作ると並列実行で **RequestConflict** になり、再実行でも直らない → `dependsOn` で順序を固定(maf-ports 共有基盤を修正、P-C12)。条件付きアクセスの claims チャレンジと呼び出し中のトークン失効はライブでも未確認(P1 ライセンス・トークン寿命の都合)— Port 15

## 6. 2026-10-06 の最新化+ライブ再検証で分かったこと

全ラボを agent-framework-core 1.20 / openai 3.24 / azure-ai-projects 2.8.0(MAF の Foundry 連携を使う Port 11・15 は 2.7.0)へ上げ、Port 15 以外はライブも再実施した(Japan East、gpt-5.4-mini、共有基盤を新規構築して 14 ポートを並行実行し、検証後に全削除)。**オフラインで全件通っていても、ライブで直すものが 6 件出た**(トレースの間引き・Code Interpreter の出力 3 点・ルーブリック評価・再デプロイの版・継続評価の設定・CU のコスト費目)。

### 6-1. 観測

1. **azure-monitor-opentelemetry の既定サンプラーはエージェントのトレースを歯抜けにする。**1.8 系の既定は rate-limited(5 spans/秒)で、ワークフロー開始直後のスパンの山(`workflow.run` / `executor.process` / `invoke_agent`)が落ちる。親が残っても子は独立に再サンプリングされ、ローカル再現では 87 本中 27 本しか残らなかった。`configure_azure_monitor(..., sampling_ratio=1.0)` で解消(全ポートに適用)。§1-2 の「トレース配線は実質 2 行」には **3 行目(サンプリングの明示)**が要る。アプリ側の監査連鎖は間引かれないがトレースは間引かれる — トレースを証跡の代わりにしない理由が 1 つ増えた — Port 1・4(全ポート)。※2026-10-14: 1.8.11(2026-10-07)でも既定サンプラーは変わらず、`sampling_ratio=1.0` は引き続き必要(§6-5)
2. **会話本文の専用テーブル `AppGenAIContent` は、2026-10-06 時点では「二重書き」だった。**公式は移行日 2026-09-30 以降は専用テーブルだけに入ると書くが、サブスクリプションの feature flag 未登録の Japan East では、クライアント側(MAF)・プラットフォーム側(hosted の `responsesapi`、prompt agent)・合成スパンのすべてで、本文が `AppDependencies` の `gen_ai.*` 属性と `AppGenAIContent` の両方に入った(`_MS.GenAIContentId` で 1 対 1 に対応。専用テーブルの着信は 4 秒〜約 6 分遅れ)。**`gen_ai.*` 以外の属性名と MAF のメッセージイベント(`AppTraces`)は振り分けの対象外。**→ §5-9 の第 4 案(保護テーブル)は (1) 移行の有効化 (2) テーブルの Protected 化 (3) 読む人だけに Privileged Monitoring Data Reader (4) `gen_ai.*` 以外に本文を書く計装を止める、の 4 点がそろって初めて成立する — foundry-probes probe 11・Port 11
3. **`az monitor app-insights query` は既定で直近 1 時間しか見ない**(`--offset` の既定が KQL の期間指定より優先)。並行実行の集計は実行ごとに `OTEL_SERVICE_NAME` を変えて `cloud_RoleName` で絞った — 共有基盤

### 6-2. hosted agent・Routines

1. **既存セッションがどの版で答えるかは、構成によって結果が割れた(同日・同リージョン)。**MAF ホスティング(`agent-framework-foundry-hosting` 1.0.0b261002)の Port 11 では、切り替え前の会話は `agent_session_id` 付き・`previous_response_id` だけ・`stop_session` 後・idle(15 分)明けのすべてで作成時の版が答えた(公式の「作成時の版に束縛」どおり)。Agent Server SDK だけの最小エージェント(probe 10)では、起動中は作成時の版だが、`stop_session` 後と idle 明けは**現行のセレクタの版で再開**し、`version_ref` で明示固定したセッションも同じだった(3 回再現。クライアント SDK の版と切り替え API の形は原因から外れ、残る差はコンテナ実装)。→ **公式の記述を前提にせず、自分の構成で「`stop_session` 後・idle 明けにどの版が答えるか」を受入試験に入れる。**旧版で会話を最後まで続けさせたいならエージェント名を分ける — Port 11・probe 10
2. **応答の `agent_reference.version` は「答えた版」ではなく、その時点のセレクタの版。**判定はセッションの `version_indicator`(`get_session`)かコンテナ側スパンの `gen_ai.agent.version` で行う。**同じ zip・定義の再デプロイは新しい版を作らず既存の版を返す**ので、候補 = 本番の版なら止める判定が要る。エンドポイント設定にはサーバー側で認可方式が入るので、セレクタの更新は他の設定を保って差し替える(作り直すと消える)— Port 11
3. **Routine が作った応答は開発者の ID で読めない**(GET が 403 `session_not_accessible`。Routine は agent identity で呼ぶ)。完了の確認はトレースで行う。受付は 8 秒(コールドスタート込み)で、30 秒は「受付」までの上限 — Port 11
4. **リモートビルドの pip はプレリリースを混ぜる。**`agent-framework-foundry-hosting` の依存指定 `azure-ai-agentserver-responses>=2.2.0b1` によって、pip は 2.3.0b2(プレ版)を選んだ(uv は 2.2.0)。コンテナの requirements に上限を付け、`pip install --dry-run --report` の結果を lock と突き合わせるテストを置いた — Port 11(casebook P-H29)。※2026-10-14: 2.3.0 が stable になったので、いまは pip・uv とも 2.3.0 を選び食い違いは一時的に消えるが、2.3.0 はテレメトリ送出の既定が変わっている(§6-5)
5. **MAF ホスティングの「要求ごとのファクトリ」(b261002)でも、利用者ごとの資格情報は渡せない**(§5-2 の注記)。native workflow hosting は約 25 行で動くが、境界を越える型をすべてチェックポイントの許可リストに載せる必要があり、出力が JSON(structured_outputs)になって playground の会話面が失われる → 会話型のエージェントには採用せず — Port 11・15

### 6-3. ツール・RAG・評価

1. **Code Interpreter(Responses 経由)は `include=["code_interpreter_call.outputs"]` を付けないと実行ログ(stdout)が返らない。**生成画像は data URI(MAF では `data` 型のコンテンツ)で返り、`uri` 型だけ見ていると取りこぼす。アップロードしたファイルは削除するまで Files に残る(データの保持期間の論点)— Port 8
2. **Japan East の AI Search Free でも Foundry IQ(ナレッジベース+LLM のクエリ計画)が動いた**(小規模・同時 1 要求のみ)。7 月の「Basic が実質の下限」は訂正。ナレッジベース MCP の応答の形(参照の URI・ツール引数名)はプレビュー API の版に結び付いている — Port 10
3. **埋め込みは安定版の MAF クライアントに寄せると自前コードが消え、トレースにも出る**(`OpenAIEmbeddingClient`。`embeddings <deployment>` スパン)。`FoundryEmbeddingClient`(project embeddings)はプロジェクトエンドポイントで埋め込みを呼ぶのではなく、アカウントの `/openai/v1` を導出して呼ぶ(プロジェクト経由は今も 404 — probe 08)— Port 4
4. **ルーブリック評価器(`score_model`)は `pass_threshold` を省略すると run 全体が失敗する**(サービスが 0.0 とみなし範囲外エラー)。SDK は省略を許し、提出時にも `--dry-run` にも出ない。3.0 を設定してルーブリック込みのクラウド評価が初めて完走した — Port 9。※2026-10-14: ここでの「ルーブリック」は openai ネイティブの `score_model` グレーダーで、Foundry の Rubric 評価器(生成型)とは別物。Rubric 評価器のスコアは 0〜1 に正規化され、合格閾値の既定は 0.5(casebook P-O19)
5. **継続評価の `sampling_rate` は百分率(1.0 = 1%)**で、これが 8 月の「自動ランが出ない」の真因だった。評価が効くのは prompt agent をプロジェクトの Responses+`agent_reference` で呼んだ応答で、エージェントエンドポイント経由の応答はランが作られても failed になる。結果は `evals.runs` で SDK から取れる — probe 09

### 6-4. フレームワーク(MAF 1.20)と協調パターン

1. **switch-case の条件関数の例外が伝播するようになった**(1.19 までは黙って Default に流れた。Default がループエッジだと静かに回り続け得た)— Port 3・7
2. **承認の堅牢化は自作の agent-as-tool 層には効かない。**1.20 は承認の解決に失敗したら止める側に倒した(履歴に捏造した承認でツールが動かない。1.19 では通った)が、`Agent.as_tool()` の内部だけの処理で、自前の相談ツールは空の応答を返していた → 承認待ちを検出して理由付きで返す防御を追加 — Port 13。ネイティブ承認(`ToolApprovalMiddleware(auto_approval_rules=…)`)なら引数依存の自動承認も書けるが、停止→同一セッションで再開の型で、DENY を表せず、承認待ちは監査連鎖に残らない → ガバナンス用途は middleware のまま — Port 14
3. **agent-as-tool は「許されない相談が起きない」までしか保証しない。**評価データで期待した必須の相談は 12 件中 5 件しか起きず、日によって変わる(7 月は自発的に相談していた)→ 必須の相談はグラフで固定する — Port 13
4. **HandoffBuilder は順序が正しくても成果物が欠ける崩れ方をする。**初のライブで handoff は 7 回ともリング順だったが、1 体が本文を書かずに handoff だけ呼び、セクション欠落のまま終了条件で「完成」になった(§1-1 の「確率的になる」の実例)— Port 7
5. **外部検索のレート制限は例外にならず、「空のレポートが正常終了」する**(DuckDuckGo の HTTP 202)→ 結果 0 件なら失敗にするガードが要る。モデルが自己申告する数値(語数)は実測より 3〜4 割少ない → 数値はコードで数える — Port 1・7
6. **Voice Live: Japan East で gpt-realtime-2.1-mini(移行経路)が通ったが、実効モデル名は `-global-standard`(国内処理にはならない)。**表にない転写設定も受理された(受理 ≠ 動作保証)。ネイティブ音声モデルは決定論の次質問から外れやすく、音声出力も約 3.8 倍 → 決定論のフローはコア側に残す 3 層分離が引き続き効く。voice agents(`kind: voice`)はプレビューなので比較の記録に留めた — Port 12

### 6-5. 2026-10-14 時点の版の変化(ラボは再実行していない)

2026-10-06 の検証の後に出た版・ドキュメントのうち、ラボの結論や手順に効くもの。**再検証はしていない**(CHANGELOG・Learn で確認した事実と、ラボのコードを読んだ範囲での影響)。

1. **azure-monitor-opentelemetry 1.8.11(2026-10-07)でも既定サンプラーは変わらない**。変更は要求 Python を 3.10 以上に正したメタデータだけで、既定は 1.8.6 から続く `RateLimitedSampler`(rate-limited)のまま → §6-1-1 の `sampling_ratio=1.0` は引き続き必要(全ポートの設定はそのままでよい)。同時公開の exporter 1.0.0b58 はスパン / ログの `session.id` を Azure Monitor のセッション文脈に写すようになった(未検証)
2. **`azure-ai-agentserver-responses` 2.3.0(2026-10-12)が stable になり、テレメトリ送出の既定が async から background に変わった**(`AGENTSERVER_FLUSH_MODE`。CHANGELOG は「要求の完了はテレメトリの到達を保証しない。background 送出にはサスペンド / 停止前のドレイン時間が要る」と明記)。Port 11 の `hosting/requirements.txt` と Port 15 の `toolbox` extra は 2026-10-06 に上限 `<2.3` を付けたので 2.2.0 のまま。一方、**Port 15 の方式 A / B のコンテナ(`hosting/requirements.txt`)は `>=2.2.0` で上限がなく、次の REMOTE_BUILD では pip が 2.3.0 を選ぶ**(uv.lock は 2.2.0。2026-10-06 の「pip の解決と uv.lock が全パッケージ一致」は 2.3.0 の公開前の確認)。上限を外す・付けないままにするなら、`AGENTSERVER_FLUSH_MODE=async` を明示するか、トレースが要求の完了より遅れて届く前提で受入試験を直す。§6-2-4 のプレ版混入は、`agent-framework-foundry-hosting` 1.0.0b261008 の依存が `>=2.2.0b1` のままなので、次のプレ版(2.4.0b1 は `FileResponseStore` の保存先を利用者別に変える BREAKING を予告)で再発しうる — casebook P-H20・H29
3. **`agent-framework-foundry-hosting` 1.0.0b261008(2026-10-08)は `agent=` に `WorkflowAgent` を渡すと警告を出す**(b261002 で非推奨になった旧経路。移行先は §6-2-5 で試した native workflow hosting = `workflow=` と要求ごとのファクトリ)。Port 11 は単体のエージェントを渡しているので影響しない。同じ時期のドキュメント(agent-framework の hosting/foundry-hosted-agent 2026-10-08)には、既定ストアがユーザー ID × セッション ID で状態を分けて最終書き込みから 30 日で期限切れになり、**分割前の旧来のデータを読まない**こと(更新前の `previous_response_id` は引き継げない — casebook P-F20)と、`steerable_conversations=True` が一時的に使えず構築時に `RuntimeError` になること(P-F21)が書かれている。Invocations ホストの既定のワイヤー形式は 1.20.0 / b261002 から JSON + SSE に変わっている(アップグレードガイドが BREAKING として掲載。旧形式は `legacy_wire_format=True` で一時的に維持)が、ラボは Invocations プロトコルを使っていない
4. **azd 拡張 `azure.ai.agents` 1.0.0-beta.19(2026-10-08)は camelCase 化の破壊的変更を含み、`azd ai agent init` の `--manifest` / `-m` は非推奨の別名になった**(正式は `--template` / `-t`)。同じ日の `azure.ai.toolboxes` beta.10・`azure.ai.routines` beta.9 も camelCase に統一、beta.18(2026-09-30)はエージェント定義を azure.yaml に必須化した。ラボは SDK(`create_version_from_code`)でデプロイしており、手順に `-m` は出てこない(Port 11 の azd 代替の記述も `azd ai agent init` だけ)。azd の経路に切り替えるときは拡張の版を固定する — casebook P-C16
5. **パッケージの現況(2026-10-14。ラボは 2026-10-06 の組のまま):** agent-framework(-core)1.21.0(CHANGELOG に BREAKING 表記なし)/ agent-framework-foundry 1.14.1(依存は引き続き `azure-ai-projects<2.8.0` なので、MAF の Foundry 連携を使う Port 11・15 は 2.7.0 のまま)/ openai 3.29.0(3.25〜3.29 に Azure 固有の変更・BREAKING なし)/ azure-ai-projects 2.8.0(変化なし)/ azure-ai-evaluation 1.18.8(バグ修正のみ)/ hosting 系の `mcp<2` も継続 / azd 1.35.1。上げるかは次回の最新化で判断する
6. **評価まわりの公式の変化:** Learn の Rubric 評価器・traces→dataset・合成データセット・会話評価のページから「(preview)」が外れたが、GA 一覧表は Preview のまま(SDK = GA / Learn = ラベルなし / GA 一覧表 = Preview の 3 者併記)。トレース評価は Learn が `azure-ai-projects==2.7.0` に固定し、Simulation seed は 2.8.0 では作れない、Quality Grader は実行できなくなった(casebook P-O22〜O24)。Port 9 の評価器構成(`score_model` のルーブリック)には直接は効かない

## 更新履歴

| 日付 | 内容 |
| --- | --- |
| 2026-10-14 | 注記のみ(ラボは再実行していない): §6-5「2026-10-14 時点の版の変化」を新設 — azure-monitor-opentelemetry 1.8.11 でも `sampling_ratio=1.0` は必要、`azure-ai-agentserver-responses` 2.3.0 の flush 既定 background(Port 15 の方式 A / B のコンテナは上限なしで次の REMOTE_BUILD から 2.3.0 になる)、`agent-framework-foundry-hosting` b261008 の `WorkflowAgent` 警告と既定ストアの分割・steerable の RuntimeError、azd 拡張 beta.19 の camelCase 化と `-m` 非推奨、パッケージの現況、評価まわりの公式の変化。§5-1・5-10(ユーザー分離の明文化)・§6-1-1・6-2-4・6-3-4 に「※2026-10-14」 |
| 2026-10-06 | §6 を追加: 全ラボの最新化(agent-framework 1.20 / openai 3.24 / azure-ai-projects 2.8.0)+ライブ再検証(Port 15 を除く)で分かったこと 19 点(既定サンプラーによるトレースの間引き、トレース本文の二重書き、hosted の版束縛の結果の割れ、Code Interpreter の `include`、ルーブリックの `pass_threshold`、継続評価の `sampling_rate` など)。§1-1・罠 3・12・13・§3・§4・§5-2・9 に「※2026-10-06」を付記 |
| 2026-07-31 | 初版。Wave 1(7ポート+agentic-search-maf)の実装ナレッジを集約 |
| 2026-07-31 | 第2版。Wave 2(5ポート: Code Interpreter / クラウド評価 / Foundry IQ / hosted agent+Routines / Voice Live)の実装ナレッジを追加。ハマりどころを8点→12点に拡充 |
| 2026-07-31 | 第3版。Wave 3(services-agency / governed-agent)を反映。**協調の分水嶺を2軸3値に改訂**(グラフ/相談型 agent-as-tool/担当交代)、middleware の知見を追加、全ポートにアーキテクチャ図を整備 |
| 2026-09-30 | §5 を追加: 委任アクセス(Port 15 delegated-access-hosted。hosted agent × アプリ管理 OBO、判定点 APIM / MCP サーバーの比較)の実装ナレッジ 7 点。オフライン検証のみ(ライブ未検証と明記) |
| 2026-09-30 | §5 にライブ検証の結果 4 点(8〜11: 方式 A / B のレイテンシ差なし、プラットフォーム側トレースの会話全文記録、会話継続の分離、デプロイ時の Foundry User と RequestConflict)を追加 |
| 2026-09-30 | §5 の 10 に、hosted agent の版更新をまたぐ会話の継続(foundry-probes probe 10 の実測)を追記 |
| 2026-09-30 | §5 の 9・10 を選定基準として整理: 9 はトレースの「接続」の仕組み(プラットフォーム側の記録+接続文字列の注入)と 3 案(集約 / 分離 / 接続しない)を architecture 09 §3.6・proposal 01 の 4-7 に接続、10 は版更新・agent 切り替えをまたぐ会話の扱いを追記 |
| 2026-09-26 | 注記のみ追加(本文の実測は不変): 罠 10(Routines GA・リージョン拡大・`api-version=v1` の Learn 明記) |
