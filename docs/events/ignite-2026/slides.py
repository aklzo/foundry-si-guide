"""Ignite 2026 — Foundry の変更点(PPTX の原本)。build.py が読む。"""

META = {"footer": "Ignite 2026 / Foundry"}

SLIDES = [
    {
        "layout": "title",
        "title": "Ignite 2026 — Microsoft Foundry の変更点",
        "subtitle": "継続改善の機能がそろった。「発表の GA」と「本番に使える GA」は分けて見る",
        "date": "2026-11-22 時点 ・ 詳細は docs/events/ignite-2026(HTML 版)",
    },
    {
        "layout": "figure",
        "title": "Ignite 2026 の概要",
        "message": "6 つの柱のうち、ここから先は Foundry を詳しく見る",
        "image": "images/fig-themes.png",
        "source": "Ignite 2026 Book of News、Azure ブログ・devblogs・Tech Community(2026-11-17〜21)",
        "notes": "全体の 6 つの柱。以降は Foundry に絞る。Copilot Studio の詳細は HTML 版の 4 章。"
                 "Microsoft IQ は新しい SKU なしの GA で、Foundry IQ・Work IQ・Fabric IQ・Web IQ を束ねる層。",
    },
    {
        "layout": "figure",
        "title": "Foundry の全体像: 継続改善ループ",
        "message": "見つける・測る・直す・鍛えるが、製品の機能として 1 本につながった",
        "image": "images/fig-loop.png",
        "source": "Azure ブログ「Continuous improvement comes to Microsoft Foundry」(11-17)、devblogs(11-18)",
        "notes": "Insights で本番の失敗を束ね、ルーブリックと人の注釈で測り、optimizer が改善案を出し、"
                 "足りなければ Managed / Programmed Training でモデルを鍛える。同じ基準で版を比べ続ける前提なので、"
                 "評価データセット(正解集)の持ち主を最初に決める。",
    },
    {
        "layout": "figure",
        "title": "ステータスの読み方",
        "message": "本番の必須経路に置けるのは左の列だけ。中央は公式 GA 一覧(Learn)が更新されれば GA になる候補",
        "image": "images/fig-status-map.png",
        "source": "Feature readiness at GA(2026-11-17 更新)と各発表",
        "notes": "公式 GA 一覧 = Microsoft Learn の「Feature readiness at GA」の表。Foundry ポータルの機能ごとに GA / Preview を示す。"
                 "11-17 に更新されたが、反映された GA は managed compute と"
                 "外部エージェントのトレースなど一部だけ。voice agents・Insights・egress 制御・optimizer は"
                 "ブログや Learn で GA と書かれても公式 GA 一覧では Preview か記載なし。提案書では「発表 GA/公式一覧 Preview」のように出典を添えて両方書く。",
    },
    {
        "layout": "figure",
        "title": "エージェントの動かし方",
        "message": "Copilot harness は 12-01 から課金・Japan East のみ。voice は閉域で電話が使えない。hosted の VNet は作成時だけ",
        "image": "images/fig-agent-types.png",
        "source": "devblogs「What's new in Foundry Agent Service at Ignite 2026」「Hosted agents … Ignite 2026」(11-18)",
        "notes": "Copilot harness は 12-01 から従量課金(0.0994 USD/vCPU 時・0.0118 USD/GiB 時。料金は地域・契約で変わり Learn には未掲載)、Japan West 不可、"
                 "BYOM と Memory は使えない。voice agents は閉域プロジェクトで電話・発信が使えない。"
                 "hosted は長時間実行の回復・サブネット IP 共有が GA。egress 制御は Learn・ブログが GA だが公式 GA 一覧に記載がない。自社 AKS は 12 月上旬に preview の目標。"
                 "M365 / Teams 公開は Bot Service リソースが不要になった。",
    },
    {
        "layout": "shots",
        "title": "観測・評価・最適化の新しい画面",
        "message": "本番の失敗を束ねて直す。外で動くエージェントも同じ基準で観測・評価できる",
        "arrange": "stack",
        "shots": [
            {"link": "https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/agent-insights", "label": "Microsoft Learn「agent-insights」", "caption": "Insights タブ: 繰り返す問題の一覧と説明(イベント前の 11-10 版。Preview 表記あり)"},
        ],
        "points": [
            ("Insights", "発表は GA・公式 GA 一覧には記載なし"),
            ("外部エージェント GA", "同じ基準で観測・評価。修正案は一般的な助言のみ"),
            ("人の注釈・正解集", "Preview。持ち主を体制に入れる"),
        ],
        "source": "Microsoft Learn(agent-insights)。画面は掲載ページを参照",
        "notes": "画面は公式ドキュメントの掲載ページを参照。Insights の画面は Preview 表記がある公開時の版。"
                 "品質ルーブリックは GA、安全・タスク単位のルーブリックは Preview。安全ルーブリックは日本リージョンでは使えない。"
                 "旧カスタムエージェント(AI Gateway 経由の登録)は 2027-05-07 に終了するので外部エージェントへ移す。",
    },
    {
        "layout": "figure",
        "title": "モデル",
        "message": "日本の Data Zone で選べる GPT-6 世代に 6.2 が加わった。router と新しい提供元は所在・契約を確認",
        "image": "images/fig-models.png",
        "source": "Learn(model-router 各ページ / リタイア表 11-18 / reasoning 11-20)、Book of News、devblogs(11-20)",
        "notes": "GPT-6.1 / 6.2 と Decision-1.1 は APAC Data Zone(Japan East)対応。managed compute は GA だが "
                 "Data Zone は US / EU のみ。Azure Policy では router の振り先を要求ごとに縛れず、router 経由の Claude は "
                 "Global のみ。Baseten / fal は Microsoft の DPA 対象外。GPT-5.6 以降はキャッシュの書き込みも課金。"
                 "GPT-6.2 は 2026-11-01 以降に提供開始したモデルなので Modified Abuse Monitoring の対象外になる(日付は 30 日前以上に通知)。",
    },
    {
        "layout": "figure",
        "title": "ナレッジ・ツール",
        "message": "Azure AI Search は Foundry IQ に改称。つなぎ方で GA 範囲とデータの扱いが変わる",
        "image": "images/fig-knowledge.png",
        "source": "Learn(search whats-new / foundry-iq-connect / web-search / browser-automation)、Tech Community(11-18)",
        "notes": "Search の API 2026-10-01 で計画・回答合成、SharePoint(indexed)・Azure SQL・ファイルのソースが GA。エージェントからの接続は Preview のまま。"
                 "ユーザーのトークンなしで呼んだときに権限付きの文書が返るかは Learn のページで食い違う。ユーザーのトークンを渡す設計にする。"
                 "Web 検索は直付けが Web IQ、Toolbox 経由は Bing のままで契約条項が違う。",
    },
    {
        "layout": "figure",
        "title": "エージェントにつなぐ RAG の選び方",
        "message": "複数ソースと文書の権限ならナレッジベース。1 インデックスで全経路 GA なら Search ツール",
        "image": "images/fig-rag-choice.png",
        "source": "Learn(foundry-iq-connect・agentic-retrieval の各ページ・tools/ai-search・file-search・MCP・OpenAPI・Feature readiness at GA)、Search REST 仕様 2026-10-01(2026-11-22 時点)",
        "notes": "ナレッジベースは API が GA でも、エージェントからの接続(RemoteTool)は Preview で、例は Preview 版の MCP。GA 版の MCP は抽出だけを返す。"
                 "調整できるのはフィルター・検索と回答への指示・件数と時間の上限・LLM 計画の省略まで。最終順位はスコアリングプロファイルで決められず、"
                 "自動で作るインデックスの埋め込みは Azure OpenAI に限られる。ユーザーのトークンなしの動きは Learn のページで食い違うので、トークンを渡して受入試験で確かめる。"
                 "閉域の取り込みは S2 以上、Japan West は medium effort なし、Serverless は閉域にできない。",
    },
    {
        "layout": "shots",
        "title": "管理・コストの新しい画面",
        "message": "Operate は Manage に統合。予算超過で要求を止められるが、上限保証には使えない",
        "arrange": "stack",
        "shots": [
            {"link": "https://learn.microsoft.com/en-us/azure/foundry/control-plane/monitor-fleet", "label": "Microsoft Learn「monitor-fleet」", "caption": "Manage の Fleet overview(11-18 版。上部ナビに Operate が残る統合前の画面)"},
        ],
        "points": [
            ("Manage に統合", "Fleet・Cost・Operations は Preview"),
            ("cost controls", "対象は GPT / o-series だけ"),
            ("閲覧権限", "Cost Management Reader が別に要る"),
        ],
        "source": "Microsoft Learn(monitor-fleet)。画面は掲載ページを参照。cost controls の画面は HTML 版 3.5 のリンク先",
        "notes": "Fleet の画面は上部ナビに Operate が残る統合前の版。cost controls は超過で HTTP 429 を返すが、"
                 "PTU・ツール料金・hosted の実行基盤は数えず、判定できないと通す。Azure Policy でエージェント種別・"
                 "イメージ・egress を縛る機能は Preview で、日本リージョンでは使えない。",
    },
    {
        "layout": "figure",
        "title": "期限と次の一手",
        "message": "12-01 に Workflows 廃止と harness 課金。2027 年前半に移行が集中する",
        "image": "images/fig-deadlines.png",
        "source": "model-retirement-schedule(2026-11-18)、docs/survey/features の重要期限表(2026-11-22)",
        "notes": "次の一手: (1) 提案中・構築中の案件で使っている機能を公式 GA 一覧で引き直す。"
                 "(2) Workflows を使っている案件は 12-01 までに MAF へ。(3) gpt-4o 2024-05-13 の PTU・Batch は手動移行。"
                 "(4) AI Gateway 経由で登録したカスタムエージェントは外部エージェントへ。"
                 "(5) CLU / CQA を使う FAQ ボットの提案には 2029-03-31 を書く。",
    },
    # ---------- 付録: 閉域と権限制御(README 5 章)・名称の整理 ----------
    {
        "layout": "title",
        "title": "付録: 閉域と権限制御",
        "subtitle": "公式の記述と、Japan East での実測(2026-11-22)を分けて示す",
        "date": "手順・生ログ: labs/foundry-probes の probe 12〜15 ・ 検証に使ったリソースは削除済み",
    },
    {
        "layout": "figure",
        "title": "A1 閉域の構成パターン",
        "message": "規制案件は C。VNet 注入はアカウント作成時にしか付けられないので、PoC から C で作る",
        "image": "images/fig-closed-patterns.png",
        "source": "Learn(configure-private-link・agents/how-to/virtual-networks・networking-options、2026-11-22 取得)、probe 12",
        "notes": "C は受信をプライベートエンドポイント、エージェントの送信を委任サブネット経由にし、Cosmos DB・Storage・AI Search を自社で持つ構成。"
                 "実測では Cosmos DB は Serverless で足りた。D の Managed VNet は FQDN 規則で Azure Firewall Standard(約 198 円/時)が"
                 "自動で作られ、SKU も後から変えられないため、費用見込み超過で実測していない。",
    },
    {
        "layout": "figure",
        "title": "A2 機能ごとの閉域対応",
        "message": "File Search と Code Interpreter は閉域で動いた。添付ファイル(input_file)は閉域でだけ失敗する",
        "image": "images/fig-closed-matrix.png",
        "source": "Learn(configure-private-link・toolbox-network-isolation・voice agent の各ページ)、probe 12(2026-11-22、Japan East)",
        "notes": "「実測」の印がない項目は公式ドキュメントの記述。Code Interpreter は Learn の virtual-networks に「ファイルの入出力がない場合だけ」と"
                 "あるが、実測では入出力とも動いた。Browser Automation・Work IQ・A2A は公式ページで記述が割れ、今回は試していない。",
    },
    {
        "layout": "figure",
        "title": "A3 実測: 閉域プロジェクトで何が動いたか",
        "message": "NAT なしで主要なツールが動いた。OpenAPI・MCP・harness は外にも出る(止め方は A4)",
        "image": "images/fig-verify-closed.png",
        "source": "probe 12(2026-11-22、Japan East。パブリックアクセス無効+VNet 注入+自社の Cosmos DB・Storage・AI Search)",
        "notes": "VNet の外からは Foundry User を付けていても 403。OpenAPI・MCP の要求はエージェントのサブネットから VM に届いた。"
                 "OpenAPI・MCP と Copilot harness の shell は、NAT がなくても公開インターネットに届いた。どれも委任サブネットの NSG・UDR を当てると止まった(A4)。"
                 "構築では、注入ありのアカウントの capability host が自動で作られ、IaC で作ると 400 / 409 になる。",
    },
    {
        "layout": "figure",
        "title": "A4 外向きの通信: 経路ごとの違い",
        "message": "harness の違いは宛先と中身をモデルが決めること。経路はツールと同じで、サブネットの NSG・UDR で止まる",
        "image": "images/fig-egress-compare.png",
        "source": "probe 15(2026-11-22、Japan East。エージェントのサブネットに NSG・UDR を当てた)、Learn(virtual-networks・agents-networking-deep-dive・web-search・deployment-types・Copilot harness)",
        "notes": "Global Standard はどの国で処理するかの話で、宛先は Microsoft の推論基盤に限られ DPA の範囲に残る。"
                 "Web search は宛先が固定のサービスで、出るのは検索語。Bing は DPA と Azure の境界の外で、サブネットの UDR では止まらない(管理者の設定で止める)。"
                 "OpenAPI と MCP は定義の URL に固定され、NAT がなくても委任サブネット経由で公開の URL に届き、NSG・UDR で止まった。"
                 "Copilot harness は shell・Web ツールで任意の URL とコマンドを使え、VNet 内の社内 API から読んだ内容も外へ送れる。"
                 "通信は委任サブネットを通り、NSG・UDR で止まった。RAI ポリシーの egress controls(Preview)では Deny にしたホスト名だけが 403 になった。"
                 "ただし egress controls を付けると、VNet 内の 8080 番と公開の 22 番への接続も拒否された。送信元の公開 IP は AzureCloud.japaneast のタグにしか入らず、宛先側では絞れない。",
    },
    {
        "layout": "figure",
        "title": "A5 ロールごとにできること",
        "message": "利用者には Agent Consumer。Project Runtime User では呼べず、コストの金額は別のロールが要る",
        "image": "images/fig-rbac.png",
        "source": "az role definition list(2026-11-22)、probe 13(2026-11-22、Japan East)",
        "notes": "Agent Consumer はエージェントのエンドポイントだけを呼べる。Project Runtime User は定義上 Responses を呼べそうに見えるが、"
                 "実測ではどの経路も 403。モデルだけを呼べる組み込みロールはなく、Foundry User を付けるとエージェントも作れる。"
                 "Project Manager は Foundry User と Agent Consumer を付与できたが、利用量のメトリクスは空で返る。",
    },
    {
        "layout": "figure",
        "title": "A6 プロジェクトの中で分けられないもの",
        "message": "分けたい単位ごとにプロジェクトを分け、API キーは止める",
        "image": "images/fig-isolation.png",
        "source": "probe 13(2026-11-22)、Learn(rbac-foundry・memory-usage・hosted agent の権限ページ)",
        "notes": "他人の応答 ID を previous_response_id に入れると続きが読めた(会話と応答の取得自体は分離されている)。"
                 "メモリはプロジェクトの経路なら x-memory-user-id で他人の記憶が読め、エージェントのエンドポイントではヘッダーが無視された。"
                 "API キーはエンドポイント・ファイル・メモリまで通る。disableLocalAuth は約 1 分で効き、拒否は 403 AuthenticationTypeDisabled。",
    },
    {
        "layout": "figure",
        "title": "A7 公式の記述と実測の食い違い",
        "message": "10 点が食い違った。設計に効くのは API キー・Code Interpreter・Agent Optimizer",
        "image": "images/fig-verify-gaps.png",
        "source": "probe 12〜14 の NOTES(2026-11-22、Japan East)",
        "notes": "Agent Optimizer は公式 GA 一覧で Limited preview だが、申請も機能登録もせずに見積もり(200)と最小ジョブ(約 2 分で完了、実費は数円)が通り、"
                 "閉域のプロジェクトでも動いた。申請の段取りは要らないが、GA ではないので Preview の条件は変わらない。",
    },
    {
        "layout": "figure",
        "title": "A8 検証の範囲と費用",
        "message": "費用は約 1,790 円の見込み(予算 5,000 円)。Managed VNet と Azure Firewall は費用見込み超過のため実施せず",
        "image": "images/fig-verify-scope.png",
        "source": "probe 12・15 の COST.md(Azure Retail Prices API の単価から計算。請求の確定値ではない)",
        "notes": "環境を 3 回作った。1,425 円は Private DNS ゾーン 6 つを毎回 1 か月分で計上した額で、日割りなら合計約 370 円。時間課金のリソースは合わせて約 4.3 時間で削除した。"
                 "hosted agent の閉域は構築に時間がかかるため、Foundry IQ の権限絞り込みとエージェント ID の無効化は Entra の"
                 "ユーザーや管理者ロールが要るため実施していない。",
    },
    {
        "layout": "figure",
        "title": "A9 Azure AI Search の改称の範囲",
        "message": "変わったのは表示名だけ。リソースの型・CLI・SDK・ロール名は Azure AI Search のまま",
        "image": "images/fig-rename.png",
        "source": "Learn「What's new in Foundry IQ (Azure AI Search)」(2026-11-17 版)、Azure CLI 2.93 の az search のヘルプ",
        "notes": "Microsoft.Search/searchServices、*.search.windows.net、azure-search-documents、RBAC のロール名、課金メーター名は旧名のまま。"
                 "Foundry 側の Microsoft.CognitiveServices/accounts と az cognitiveservices は Foundry リソース自体の型で、Search の改称とは関係がない。"
                 "設計書では「Search サービス」と「ナレッジベース」を言い分ける。",
    },
]
