# 03. 選定ガイド — 要件からアーキテクチャを決める

[← アーキテクチャ TOP](./README.md)

> **最終更新:** 2026-07-30(公式ドキュメントとの突合検証で訂正) / 2026-09-04(G2 表を公式 2026-08-14 更新で改訂、casebook への導線)/ 2026-09-26(A2A の GA 化を G3 に反映、G2 表を公式 2026-08-14 版のまま再確認) / 2026-10-06(提案チェックリストにトレース本文の閲覧者・Agent 365 送出・hosted agent のリリース手順と IaC の経路を追加) / 2026-10-14(G2 表に Browser Automation の GA 表明と閉域非対応の併存を注記) / 2026-11-22(features 差分更新〈10-14 以降+Ignite 2026〉の波及: G1 に GPT-6.x の APAC Data Zone・Model router の Policy・Web search の経路差・Modified Abuse Monitoring の縮小・Baseten / fal の DPA 対象外、G2 表に Browser Automation の閉域両論・閉域で voice の電話チャネル不可・Bot Service 不要・hosted のサブネット IP 共有と構成確定のタイミング、G3 に Copilot harness と Workflows 廃止まで 9 日、「自前オーケストレーションは可観測性から外れる」を外部エージェント登録〈GA〉で緩和、逆引き表とチェックリストを更新) / 2026-11-22 訂正(Foundry IQ: ユーザートークンを渡さないときの KB の挙動は Learn のページで食い違うので両論に。閉域取り込みの tier を S2 / S3 / L1 / L2 と明記)

[02. 構成要素カタログ](./02-building-blocks.md) がレイヤーごとの選択肢の一覧なら、本ページは**どの順番で何を決めるか**の手順書である。順番を間違えると手戻りが大きい項目があるため、決定順序そのものが設計判断になる。なお本ページは「Foundry を使うと決めた後」の判断を扱う。その手前(Copilot Studio か Foundry か・単一エージェントかマルチか・オーケストレーションパターンの選択)は [11. エージェント構成の判断フレームワーク](./11-decision-frameworks.md) を参照。**要件の言葉からシナリオ単位で逆引きしたい場合**(「閉域必須」「Copilot Studio から引き継ぎ」等)は [casebook 01 要件シナリオ別プレイブック](../casebook/01-scenario-playbook.md)、現場で詰まった点(公式・実測・公開記事)は [casebook 02](../casebook/02-pitfalls-index.md) を併読する。

## 決定順序 — 5 つのゲート

後戻りコストの大きい順に並べている。**上から順に閉じていく。**

```
 G1 データ・規制ゲート        「そのデータを、どこで、誰に処理させてよいか」
        │                     → モデル・デプロイタイプ・外部ツール可否が決まる
        ▼
 G2 ネットワークゲート        「閉域か、パブリックか」
        │                     → 使える Foundry 機能の一覧が決まる(後付け不可)
        ▼
 G3 制御ゲート                「明示的な状態遷移・承認・再開が要るか」
        │                     → ポータル完結か、コードファーストかが決まる
        ▼
 G4 統合ゲート                「既存システムとの主従はどちらか」
        │                     → Foundry をプラットフォームとして使うか、部品として使うか
        ▼
 G5 ライフサイクルゲート      「いつまで、誰が保守するか」
                              → プレビュー機能の可否・IaC の作り込み度が決まる
```

### G1. データ・規制ゲート

最初に「扱うデータの機密区分」と「処理してよい地理的範囲」を確定する。ここが決まらないとモデルすら選べない。

| 要件 | 帰結 |
|---|---|
| 国内処理が必須 | 日本国内限定処理が必須なら Standard / Regional Provisioned(geography 型。Japan East / Japan West。処理は geography 内で、geography 内のリージョン間処理はありうる — 2026-09-26 に deployment-types 2026-08-06 版で確認)。域内(APAC: 豪・日・韓・星・印)処理で足りるなら Data Zone も可。Global Standard は不可。使えるモデルが絞られる。**2026-11-22:** GPT-6 世代で APAC Data Zone に載るのは `gpt-6.1-sol` / `gpt-6.1-terra` / `gpt-6.2-astra` / `gpt-6.2-sol`、**managed compute は APAC Data Zone なし(日本は Global のみ)**、**Model router は Azure Policy で要求時のルーティング先を絞れない**ので Data Zone の router+モデルサブセットにし Auto(常に Global)は使わない、Voice Live の一部モデル・HD 音声は日本リージョンでも Global 処理([01 §7](./01-official-baselines.md#7-日本の案件で特に効く公式事実)) |
| 外部インターネットへのデータ送出が不可 | **Web search / Grounding with Bing は使用不可**(DPA 対象外・境界外送信と明記。2026-11-22: 直付けの Web search は Web IQ、toolbox 経由は Grounding with Bing で条項が経路ごとに違うが、どちらも境界外で処理されうる)。Browser Automation も同様に要注意。**Baseten / fal(preview)のモデルは Microsoft の Product Terms・DPA の対象外**(Fireworks は DPA 適用) |
| 「プロンプトを Microsoft 側に保存させない」が要件(2026-11-22 追加) | 悪用監視のデータ保存を止める Modified Abuse Monitoring は、**2026-11-01 以降に提供開始したモデルでは告知日から対象外**(既存の承認があっても。gpt-6.2 系が該当)。採用モデルの提供開始日を確認し、対象外なら旧世代モデルに留めるか要件を顧客と再合意する([07 章](./07-usecase-regulated-edge.md)) |
| 顧客の個人情報を扱う | Guardrails の PII 検出(プレビュー)+ アプリ側のマスキング。会話ログの保持場所(basic か standard か)を確定 |
| 監査で「誰の権限で何を見たか」の証跡が要る | OBO(ユーザー委任)前提。app-only で動くバッチ的エージェントとは両立しない |
| Claude を使いたい | **Foundry 組込みコンテンツフィルターが効かない。**Content Safety を自前で呼ぶ設計が必須。課金も Marketplace 経由 |
| M365 のデータを使いたい | SharePoint / Work IQ ツール → **M365 Copilot ライセンスまたは Retrieval API の pay-as-you-go 課金が前提**。ライセンス費(または従量課金)が案件コストに乗る |

### G2. ネットワークゲート

**このゲートの結論は後から変えられない。** Standard setup(BYO VNet 注入)は後付け・変更不可で再デプロイが必要、Managed VNet は有効化後の無効化不可、BYO VNet からの移行パスもない。

閉域を選んだ時点で使えなくなる主な機能:

| 機能 | 閉域での状態 |
|---|---|
| Tracing | トレース本体は prompt / hosted / 外部エージェントで GA(2026-11-17 版で外部エージェントも GA)だが **Tracing VNet は Preview**(GA 一覧 2026-08-14 版・11-17 版とも)。閉域の監査主系には置かない(→ [casebook P-N14](../casebook/02-pitfalls-index.md#d-ネットワークと閉域)) |
| Memory | **VNet 非対応** |
| Work IQ | **VNet 統合非対応** |
| File Search | 公式ツール表は 2026-08-14 更新で「✅ Through private endpoint」に変わった(2026-07 時点は Not supported)。**Blob Storage のファイルを File Search で使う構成は非対応のまま**(virtual-networks) |
| Logic Apps / Computer Use / Image Generation | Private Link 環境で「Not supported / Under development」と明記 |
| Browser Automation | ~~configure-private-link の表は Not supported~~ → **2026-11-22: 公式間で割れた** — configure-private-link のツール表 = **Supported**、toolbox-network-isolation = **Not supported**(private website access は別の preview)。ステータスも本文・TOC = GA / 移行ガイドの表 = preview の両論。閉域の必須経路には置かず、使うなら実機で確かめる(本ドキュメントの判断) |
| Foundry MCP Server | ネットワーク分離未対応(Private Link 裏のリソース不可) |
| Teams / M365 への公開 | パブリックネットワーク無効プロジェクトは**ポータルからの公開不可・REST のみ**(送信元 IP フィルタ付きの公開 Activity 経路を作る = 完全閉域にはならない)。2026-11-22: 別途の Bot Service リソースは不要になった(経路の性質は不変) |
| voice agents の電話チャネル(2026-11-22 追加) | **Teams Phone / Twilio / SIP と発信は閉域プロジェクトでは使えない**と明記。電話窓口は非閉域プロジェクトに分けるか、Voice Live を自前で使う([08 E1](./08-usecase-specialized.md#e1-音声エージェント-コンタクトセンター)) |
| Workflow Agents | アウトバウンド注入非対応 |
| **hosted agents** | 公式は「既存のネットワークテンプレートで作った private Foundry に hosted agent をデプロイできる」とし、アウトバウンドの VNet 注入は prompt / hosted の両方に同じく適用される(configure-private-link)。**hosted agent の VNet 注入は Foundry アカウントの作成時にしか入れられない**(既存アカウントへの後付けは非対応 — virtual-networks)。閉域のツール対応表も公式テンプレート(15 / 11)で作った構成が対象。private ACR は 2026-06-25 以降作成のプロジェクトのみ。**2026-11-22:** ネットワーク構成は**最初の hosted agent 作成時に確定**(以後の変更は新プロジェクト)。セッションはサブネット IP を共有(GA、/24 で計画上約 60,000 セッション)し、PE を `192.168.0.0/24` に置かない。エンドポイントが閉域でも公開到達可能かは記述が消えて要確認 |

**判断:** 閉域が必須なら、RAG は自前索引(L5 の H/S)、記憶は自前(L4 の S)、観測は自前 OTel(L12 の H)に倒す前提でコストを積む。「閉域だが Foundry のマネージド機能をフルに使う」は成立しない。**hosted agent を閉域で使うなら最初から VNet 注入つきで Foundry アカウントを作る**(hosted agent の注入は後付け不可。AI Search ツールのページも「VNet 注入なしのエージェントは private endpoint 付きの Search に接続できないことがある」と明記 — [04 章 A3](./04-usecase-chat-rag.md#a3-既存-ai-search-資産の活用-ai-search-ツール直結))。

### G3. 制御ゲート

**「明示的な状態遷移が要るか」の一点で判断する。**

| 要件に含まれる言葉 | 帰結 |
|---|---|
| 「FAQ に答える」「文書を検索して要約する」「1〜2 個の API を呼ぶ」 | **Prompt agent(M)で足りる。**コードを書くのは過剰 |
| 「条件によって処理を分ける」「失敗したら別の手順を試す」 | コードファースト(H)。MAF か LangGraph |
| 「担当者が承認してから実行」「承認待ちで数時間〜数日止まる」 | H 以上。チェックポイント / 永続化のあるフレームワーク、または Logic Apps / Durable Functions |
| 「失敗したステップだけ再開したい」 | H 以上。チェックポイント必須 |
| 「毎朝レポート」「Teams / GitHub のイベントで起動」 | **Routines(2026-09-24 GA)で起動側だけマネージドにできる。**1 トリガー + 1 アクションで分岐は持てないため、処理本体の制御要件は上の各行で別途判断(Japan West 非対応・CMK 非対応) |
| 「各ステップの入出力を監査ログに残す」 | H 以上(ミドルウェアで挟む)、または S |
| 「CI で回帰テストしたい」 | H 以上。ポータル定義はテストしにくい |
| 「ファイルを読み書きしてコマンドを実行」「調べ物をサブエージェントに分担」をコードなしで(2026-11-22 追加) | prompt agent の **Microsoft Copilot harness**(preview、2026-12-01 からサンドボックス課金)で M のまま扱える。ただし Japan West 不可・BYOM / Memory 不可・既存エージェントの切り替え不可なので、本番の必須経路にするなら G5 で判断 |
| 「複数のエージェントが協調する」 | **ポータルのビジュアル Workflows は 2026-12-01 廃止(2026-11-22 時点で残り 9 日)のため選ばない。**MAF、または A2A(`a2a` ツール = v1.0 が GA、旧 `a2a_preview` = v0.3 はプレビュー。2026-09-11 版で GA 化。v1.0 はテキストのみ・ストリーミング非対応) |

```
       要件に「承認」「再開」「分岐」「監査」があるか？
                    │
         ┌── No ────┴──── Yes ──┐
         ▼                       ▼
   Prompt agent            既存の業務フローエンジンが主役か？
   (ポータル / SDK)              │
                     ┌── Yes ───┴─── No ──┐
                     ▼                     ▼
              Logic Apps /          コードファースト
              Durable Functions     (MAF / LangGraph)
              + Foundry を1ステップ         │
                                  どこで動かす？
                                  ┌────────┴────────┐
                                  ▼                 ▼
                          Hosted agent      Container Apps / AKS
                          (Foundry が実行)   (自分で実行)
```

**「長時間・確実な再開」だけが要件なら、フレームワークを乗り換える前に耐久実行の拡張を検討する。** Microsoft Agent Framework には Durable Extension があり、**エージェントのコアロジックを変えずに**チェックポイント・障害回復・分散ホスト間スケールを付与できる。ホストは Azure Functions(マネージド・scale-to-zero)か自前コンピュート、バックエンドは Durable Task Scheduler が推奨で、専用ダッシュボードで会話履歴とオーケストレーションを可視化できる。「MAF では長時間処理が無理だから LangGraph へ」と結論する前に、ここを確認する。

**自前オーケストレーションを選ぶと Foundry の可観測性から外れる。** 「When you build your agent in code that runs on App Service (orchestration in your application), the agent metrics aren't visible in Azure AI Foundry because Foundry only sees fully managed Foundry agents」と公式に明記されている。OpenTelemetry の GenAI セマンティック規約(`gen_ai.agent.name`、`gen_ai.usage.*` 等)に沿って計装すれば Application Insights 側や App Service の Agents タブでは集計されるので、**「Foundry のダッシュボードを見せる」ことが要件に入っているかを事前に確認する。****2026-11-22 緩和:** Foundry 外で動くエージェント(LangGraph / LangChain / CrewAI 等)を **external agents として登録する機能が GA**(2026-11-18。GA 一覧表でも Tracing は external agents で GA)になり、同じ `gen_ai.agent.id` で計装しておけば**トレース・Insights・スケジュール型のトレース評価は Foundry で見られる**。ただし人手評価・red teaming のターゲット化・イベント起動の継続評価は非対応で、登録はトラフィックを中継しない(ゲートウェイでのブロックもない)。旧来の Control Plane の custom agents(AI Gateway 経由の登録)は 2027-05-07 に非推奨化 — [09 §3](./09-operations.md)。

### G4. 統合ゲート

既存システムとの主従関係で、Foundry の使い方が変わる。

| 状況 | 構成 | Foundry の役割 |
|---|---|---|
| 新規の AI アプリが主役 | フル統合。Prompt / Hosted agent として Foundry 上で実行 | プラットフォーム(ID・スケール・観測・公開まで) |
| 既存業務システムに機能追加 | Responses API のみ利用。オーケストレーションは既存アプリ内 | モデル + プラットフォームツールの供給元 |
| マルチクラウド / ロックイン回避が要件 | Foundry 非依存。抽象レイヤーを自前で持つ | モデル供給元の 1 つ(差し替え可能に保つ) |
| 業務部門がノーコードで育てたい | Copilot Studio / Logic Apps 側を主に、Foundry エージェントを部品として呼ぶ | 高度な処理を担う部品 |

**「既存システム組込み」は SI で最頻出だが、Foundry の運用機能(Tracing / Evaluations / エージェント公開)を捨てることになる**点を提案時に明示する。トレースだけは自前 OTel 計装 → App Insights で部分的に取り戻せる。(2026-11-22: さらに external agents として登録すれば、トレースの閲覧・Insights・トレース評価は Foundry 側でも使える。エージェント公開とイベント起動の継続評価は引き続き使えない)

### G5. ライフサイクルゲート

| 状況 | 帰結 |
|---|---|
| PoC / 3 か月で捨てる | プレビュー機能の使用可。ポータル手動構成でよい。速度優先 |
| 1〜2 年運用、内製チームが保守 | プレビューは代替可能な範囲に限定。IaC 必須。評価の自動化を入れる |
| 5 年以上 / 顧客に納品して保守を離れる | **プレビュー機能を必須経路に置かない。**廃止予定の機能を使わない。移植性を確保(オーケストレーションを Foundry 固有機能に依存させない) |
| 顧客の内製化前提 | ポータルで触れる範囲を意図的に広く取る。ただし Workflows 廃止があるため、ノーコードの受け皿は Logic Apps / Copilot Studio 側に置く |

## 要件キーワード → 効いてくるレイヤー(逆引き)

RFP や要件定義の言葉から、どのレイヤーの判断が必要になるかを引く表。

| 要件の言葉 | 効くレイヤー | 判断すべきこと |
|---|---|---|
| 「社内文書を検索して答える」 | L5 | File Search で品質が出るか。出ないなら AI Search 自前索引 |
| 「最新のニュースも踏まえて」 | L5 / G1 | Web search は境界外送信。規制業種なら別手段 |
| 「担当者の承認を経て実行」 | L2 | コードファースト確定。チェックポイントのある基盤 |
| 「基幹システムに書き込む」 | L6 / L9 | ツールの認可を app-only にするか OBO にするか。冪等性・リトライ |
| 「Teams から使いたい」 | L14 | M365 管理者承認(2026-11-22: 別途の Bot Service リソースは不要)。閉域なら REST 公開のみ(受信は公衆インターネット経由) |
| 「音声で対話したい」 | 特化 | Voice Live / voice agents(voice agents は Learn・SDK・ブログ = GA / GA 一覧表 = Preview の両論)。~~SIP 非対応~~ → SIP 直結は preview で日本リージョンなし(FAQ は非対応のまま)、閉域プロジェクトでは電話チャネル不可、一部モデル・HD 音声は日本でも Global 処理([08](./08-usecase-specialized.md)) |
| 「請求書を読み取って」 | 特化 | Document Intelligence(決定論的)か Content Understanding(LLM)か |
| 「複数のお客様に SaaS として提供」 | L9 / L11 / L3 | テナント分離の単位。APIM でのレート制限・課金按分 |
| 「オンプレでも動かしたい」 | L1 | Foundry Local / Azure Local。モデル選択肢が絞られる(2026-11-22: Foundry Local 2.1 で BYOM。顧客 AKS への hosted agent 配置は 12 月上旬に public preview 目標で本番設計には未使用) |
| 「응答が 1 秒以内」 | L1 / L11 | PTU 検討。ガードレールは介入点あたり 50〜100ms 加算 |
| 「月間 N 万リクエスト」 | L1 / L11 | クォータ設計。PTU + Spillover。Batch に回せる処理の切り分け |
| 「AI の回答品質を継続的に測りたい」 | L13 | Evaluations(Entra 必須)。継続的評価は既定 100 回/時(GA 一覧表 Monitoring = Preview のためプレビュー扱い)。2026-11-22: 品質ルーブリックは GA の両論、Insights は GA(日本リージョン可)、safety rubric と red teaming は日本リージョンなし、人手のレビューを評価データにする HITL は preview |
| 「情報漏えいを防ぎたい」 | L8 / L9 | Prompt Shields、PII、Purview / Defender for Cloud |
| 「コストを部門別に按分したい」 | L11 / L16 | Foundry のクォータはデプロイ単位。APIM のトークンメトリクスが実質必須。2026-11-22: Cost in Foundry / cost controls(preview)で予算超過を 429 で止められるが、対象は GPT / o-series のみで PTU・ツール・hosted のコンピュートは数えず、閲覧には Cost Management Reader が別途要る |
| 「予算を超えたら止めたい」(2026-11-22 追加) | L11 | cost controls(preview)が候補だが、判定が遅れると fail-open・データは 8〜24 時間遅れ → 予算アラート+自動化か APIM のトークン上限と併用する |

## 判断軸マトリクス(方式の比較)

| 軸 | Prompt agent(M) | Hosted agent + MAF(H) | Hosted agent + LangGraph(H) | 自アプリ + Responses API(S) |
|---|---|---|---|---|
| 立ち上がり速度 | 最速 | 中 | 中 | 遅い |
| 制御の細かさ | 低 | 高 | 高 | 最高 |
| 状態・チェックポイント | なし | あり | あり(成熟) | 自作 |
| ローカルテスト | 難 | 可 | 可 | 容易 |
| 運用負荷 | 最小 | 小(ホスティングは Foundry) | 小 | 大 |
| 移植性 / ロックイン | 低 / 強 | 中 | 高 / 弱 | 高 / 弱 |
| Foundry 運用機能(観測・評価・公開) | フル | フル | フル | 自前(2026-11-22: external agents 登録でトレース・Insights・トレース評価は可) |
| 言語 | — | Python / C#(Go はプレビュー) | Python 中心 | 任意 |
| エコシステム成熟度 | — | 新しい(1.0 が 2026-04) | 成熟 | — |
| 費用構造 | 推論 + ツール | 上記 + コンピュート | 上記 + コンピュート | 上記 + 自前基盤 |

**「MAF か LangGraph か」は「Foundry を使うか」とは独立した判断**である点に注意。Hosted agent は MAF 専用ではなく、LangGraph / Semantic Kernel / CrewAI / カスタムコードも公式にサポートされる(プロトコルライブラリはフレームワーク非依存のため任意のフレームワークが利用可)。

## 提案時チェックリスト

設計レビューで潰しておく項目。

- [ ] 扱うデータの機密区分と処理可能リージョンを確定したか(G1)
- [ ] ネットワーク要件を確定し、**閉域で使えない機能の一覧**を顧客と合意したか(G2)
- [ ] 「ポータルで出来る範囲」と「コードが要る範囲」を線引きした表を提示したか(G3)
- [ ] 2026-12-01 の Workflows 廃止を前提にした構成になっているか(2026-11-22 時点で残り 9 日。移行未了の資産は YAML のエクスポートを先に)
- [ ] Microsoft Copilot harness・Browser Automation・voice agents など「ブログは GA / GA 一覧表は Preview またはなし」の機能を必須経路に置くなら、両論を顧客と合意したか(2026-11-22 追加)
- [ ] 採用モデルの提供開始日を確認し、Modified Abuse Monitoring の対象か(2026-11-01 以降の提供開始は対象外)、APAC Data Zone があるかを G1 と照合したか(2026-11-22 追加)
- [ ] 使用するプレビュー機能を列挙し、代替手段を用意したか(G5)
- [ ] モデルのリタイア日を確認し、更改の運用を設計に入れたか(PTU なら手動移行)
- [ ] クォータ設計と 429 時の挙動を決めたか
- [ ] 会話ログ・トレースの保存場所と保持期間を決めたか
- [ ] トレースに入る会話の中身を**誰が読めるか**を決めたか(接続しない / App Insights を分ける / `AppGenAIContent` の保護。hosted agent は Agent 365 への送出〈`a365LoggingEnabled`〉も確認 — [09 §3.6](./09-operations.md#3-6-トレースに会話の中身を残すか-hosted-agent-の選定基準))
- [ ] コストの内訳(推論・ツール・コンピュート・検索・ストレージ)を分解して見積もったか
- [ ] IaC の範囲(基盤 / エージェント定義 / ナレッジ)と、手動運用に残す部分を決めたか(hosted agent の版を azd と Terraform のどちらが持つか、本番の昇格を誰がやるか — [09 §6.3〜6.4](./09-operations.md#6-3-エージェントのバージョニングとリリース))
- [ ] 評価(品質・安全性)を CI に組み込む計画があるか

## よくある「決めきれない」論点への回答

**Q. とりあえず Prompt agent で始めて、後で MAF に移せるか。**
移せるが、無料ではない。ツール定義・ナレッジ接続・ガードレールは概ね引き継げる一方、オーケストレーションのロジックは書き直しになる。**要件に承認・分岐・再開が入っているなら最初から H を選ぶほうが安い。**

**Q. Foundry IQ を使うか、AI Search を自前で組むか。**
「複数のエージェント / アプリで同じナレッジを共有する」「ACL・Purview 連携が要る」なら Foundry IQ の価値が出る(2026-11-22: Azure AI Search 自体が「Foundry IQ (Azure AI Search)」に改称されたので、この問いは「knowledge base〈agentic retrieval〉を使うか、索引を直接引くか」と読み替える。Search `2026-10-01` で indexed SharePoint・document-level 権限・クエリプランニングが GA。**KB 接続にユーザートークンがないときの挙動は Learn のページで食い違う**(絞らずに返すと書くページと、ACL 付きの文書は返さないと書くページがある)ので、トークンを必ず渡す — [04 章](./04-usecase-chat-rag.md))。逆に「1 つのアプリのための索引」「チャンク戦略を作り込みたい」なら自前。なお **Foundry IQ の knowledge base は MCP 経由で Foundry Agent Service 以外(MAF・LangGraph・自作アプリ)からも使える**ため、「ナレッジ層だけ Foundry IQ、オーケストレーションは自前」という組合せが成立する。

**Q. マルチエージェントは本当に必要か。**
多くの案件では単一エージェント + 複数ツールで足りる。マルチエージェントが要るのは「担当領域ごとにプロンプト・ナレッジ・権限を分けたい」「並列に調査させたい」場合。**ポータルのビジュアル Workflows が廃止される以上、マルチエージェントを選ぶ = コードファーストを選ぶ**とほぼ同義になった。CAF が公式の判断基準(最初からマルチにしてよい 3 条件と、単一で始めるべき状況の一覧)を出しており、[11 章 §3](./11-decision-frameworks.md) にまとめてある。

**Q. コストはどこで効くか。**
推論トークンだけを見積もると外す。実際には (1) ツールの追加課金(File Search / Web search / Code Interpreter / Bing)、(2) hosted agent のコンピュート、(3) AI Search のティア、(4) Cosmos DB、(5) App Insights の取り込み量、が積み上がる。**ツールを増やすほど従量が増える構造**である点を最初に共有する。
