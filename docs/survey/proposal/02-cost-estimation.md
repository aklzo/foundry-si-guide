# 02. コスト見積もり手順(トークン推計 → 月額試算 → PTU 判断)

[← 提案実務ガイド TOP](./README.md)

> **最終更新:** 2026-07-31 / 2026-09-26(課金単位を pricing ページ・learn で再確認: hosted agent・Foundry IQ Serverless・Voice Live・CU・Data Zone / Regional プレミアム・flex を追記、URL 1 件差し替え)/ 2026-09-29(Flex processing の専用ページ公開〈preview・50% 割引・gpt-5.6-sol のみ〉を反映)/ 2026-10-06(ラボ還元: AI Search Free での Foundry IQ PoC・CU のキャッシュ入力費目・既定サンプラーと取り込み量)/ 2026-10-06(GPT-6 系 PTU の normalized token〈キャッシュ入力も容量を消費〉、合成評価器、Routines の再試行 5 回、GPT-Live の WebRTC 最低 15 秒、voice agents、Agent 365、Fireworks のクォータプールと PTU 既定値の改訂、priority processing の確認方法を反映。単価は引き続き書かない) / 2026-10-10(Step 6 に Copilot Studio〈Copilot Credits〉との比較手順を追加: イベント別レート・M365 Copilot 利用者の扱い・GitHub Copilot harness の換算率非公開・比較の式・構造上の傾向。Step 3 に取得先を追加。単価は引き続き書かない) / 2026-10-14(Flex processing の対象 7 モデル、Model router の既定プールに Fireworks、Bing 系ツールではプロンプトキャッシュが効かない、評価サービス側のキャッシュ・TOON によるトークン削減〈Tech Community〉、voice agents の料金ページと推定コスト属性、M365 公開の共有データアクセスの従量課金、hosted agent の idle timeout 上限の両論、Grok の最低 6 か月。単価は引き続き書かない) / 2026-11-22(Copilot harness のサンドボックス課金〈12-01 開始〉・Model router のルーティング料・GPT-5.6 以降のキャッシュ書込課金と PTU の重み・決定モデル judge と評価 run の推定コスト・Insights のジャッジ費用、cost controls〈preview〉の対象範囲と「ハードリミットはない」の更新、コストの閲覧権限〈Cost Management Reader〉と 8〜24 時間の遅れ・エージェント名のタグ、Baseten / fal の契約差、hosted agent の idle 待機の課金と 240 分の確定、M365 公開で Bot Service が不要に、Foundry IQ Serverless の表記とインデクサーの CU、Web IQ と Bing の別メーター、CU の 2,000 ページ。単価は引き続き書かない) / 2026-11-22 訂正(Foundry IQ: ユーザートークンを渡さないときの KB の挙動は Learn のページで食い違うので両論に。閉域取り込みの tier を S2 / S3 / L1 / L2 と明記)
> **方針: このドキュメントに単価を書かない。**モデル単価は改定・リタイア・新モデル投入で頻繁に変わるため、ここには「変わらないもの」= 見積もりの手順・式・コスト構成要素のチェックリスト・単価の取得先だけを置く。試算例も単価は記号のまま示す。

## Step 1: ワークロードのプロファイリング(トークン量の推計)

### 1-1. 日本語のトークン換算

- 現行主要モデル(o200k 系トークナイザー)では**日本語はおおむね 1 文字 ≒ 1 トークン前後**(英語は 1 単語 ≒ 1.3 トークン程度)。かな漢字混在率で変わるため、**精度が要る見積もりでは実データでトークナイザーにかけて実測する**(OpenAI の tiktoken / Claude は Token counting API)。
- ざっくり係数: 日本語ドキュメント 1 ページ(A4・1,200字)≒ 1,200〜1,500 トークン。

### 1-2. 1 リクエストの構造を分解する

チャット/RAG の入力トークンは「ユーザーの質問」だけではない。**毎回送られるもの全部**を数える:

```
入力トークン/ターン = システムプロンプト
                    + RAG コンテキスト(チャンクサイズ × 取得件数。File Search 既定: 800トークン × 最大20チャンク)
                    + 会話履歴(ターン数とともに線形増加。要約・打ち切り設計で抑制)
                    + ツール定義(ツール数が多いと massive。Toolbox の tool search で削減可。※2026-10-06: ただし検索の往復が 1 回増え遅延は伸びうる → casebook P-A14)
                    + ユーザー入力
出力トークン/ターン = 回答本文(+ reasoning モデルは思考トークンが出力課金になる点に注意)
```

### 1-3. 月間量の式

```
月間入力トークン = ユーザー数 × 稼働日/月 × クエリ/人日 × 平均ターン/クエリ × 入力トークン/ターン
月間出力トークン = 同 × 出力トークン/ターン
月額(モデル推論・従量) = 月間入力 × P_in + 月間出力 × P_out + キャッシュヒット入力 × P_cached
                     + キャッシュ書込 × P_cache_write(GPT-5.6 以降のモデル。2026-11-22 追加)
```

- P_in / P_out / P_cached は Step 3 で取得する単価(100万トークンあたり)。**出力単価は入力の 3〜5 倍が通例**なので、出力を絞る設計(構造化出力・max tokens)がコストに効く。
- エージェントは 1 クエリで**内部的に複数 LLM 呼び出し**(ツール選択 → 実行 → 統合)が走る。平均ターン/クエリはエージェント構成では 2〜5 倍に見積もる(PoC で実測して補正)。
- ※2026-11-22 追加 — **キャッシュ書込の課金**: GPT-5.6 以降のモデルはキャッシュの読込割引に加えて**書込にも課金**される(GPT-5.6 より前は書込無料)。TTL は 30 分(既定)か 12 時間で、**12 時間キャッシュの書込は 2026-11-01 の利用分から課金**。書込量は応答の `usage.cache_write_tokens` で実測する。可変部分が先頭にあるプロンプトは書込ばかり増えるので、固定部分を前に置きブレークポイントを固定部分の直後に置く。キャッシュが効かない用途は explicit モードでブレークポイントを置かない([prompt-caching](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching)、[casebook P-M24](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト))。
- ※2026-10-06 追加 — **評価のジャッジ費用**: `評価の月額 = 評価件数/月 × ジャッジ呼び出し回数/件 × (ジャッジ入力トークン × P_in + 出力トークン × P_out)`。個別の評価器はそれぞれジャッジを呼ぶので「呼び出し回数/件 = 使う評価器の数」になるが、**合成評価器(preview)**の `builtin.output_quality`(Fluency / Coherence / Intent Resolution / Task Adherence / Groundedness / Task Completion の 6 つ)と `builtin.tool_use_quality`(ツール系 5 つ)は 1 回のジャッジ呼び出しに束ねる(ジャッジは GPT-5.6 系推奨、最安の選択肢として gpt-5.6-luna が挙がっている)。1 回あたりの入出力は個別より大きくなりうるので、PoC で `<composite>_properties` のトークン数を実測して係数を決める([built-in evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/built-in-evaluators))。※2026-11-22: (a) **決定モデル judge(preview)**は judge 呼び出しの費用を大きく下げうる — 課金は入力トークン(出力は無料とする記述。単価は Foundry Models の価格ページ)で、Tech Community 2026-11-20 の社内計測では 1,000 回あたりの費用が生成 judge の約 1/6〜1/290。ただし対応は Microsoft-Decision-1(preview、**2027-02-04 リタイア**)だけで 1.1 は judge 非対応(Learn)、理由文を返さず、Agent optimizer を駆動する評価器には向かない([casebook P-O29](../casebook/02-pitfalls-index.md#g-観測と評価))。(b) モデルをターゲットにした評価 run は `estimated_cost.target`(推定の推論コスト)を返すようになった(Global Standard のデプロイでトークンと価格データがそろう場合のみ。請求ではない)。(c) **Insights(GA)**のスキャンは GPT-5 以降の GPT デプロイをジャッジに使い、初回は過去 7 日分のトレースが対象 — スキャンの頻度 × トレース量のジャッジ費用を積む。
- ※2026-10-06 追加 — **Routines の起動回数**: `エージェント実行回数/月 = 起動回数/月 × (1 + 再試行率 × 追加試行数)`。既定の配信再試行は**最大 5 回(5〜60 秒の指数バックオフ)**に変わった(旧 3 回)。再試行は一時障害のときだけだが、上振れの幅として最悪 5 倍を置き、冪等キーで二重処理を防ぐ設計とセットで説明する([casebook P-A13](../casebook/02-pitfalls-index.md#b-agent-service-コア))。

## Step 2: コスト構成要素チェックリスト(見落とし防止)

**モデル推論以外**が月額の過半を占める構成は珍しくない。全項目を「使う/使わない/金額」で潰す:

| 分類 | 項目 | 課金の型 | 見落としポイント |
| --- | --- | --- | --- |
| モデル | 推論(入力/出力/キャッシュ) | トークン従量 or PTU 時間 | reasoning モデルの思考トークンは出力課金 |
| モデル | 埋め込み(初期 + 増分 + クエリ時) | トークン従量 | 初期インデックス構築は一時コストとして別掲 |
| ナレッジ | Azure AI Search | **SKU 時間課金**(+セマンティックランカー) | 使わなくても月額固定で発生。SKU とレプリカ数が支配項。※2026-10-06(ラボ還元): **Free は時間課金なし**で、Japan East はリージョン表の脚注で Free でも agentic retrieval とセマンティックランカーが使える — Foundry IQ の小規模 PoC は Free で積める(ナレッジソース・ナレッジベース各 3 個、1 サブスクリプション 1 サービス、PE 非対応、セマンティックランカーの上限表に Free の列なし)。閉域・本番・同時実行の検証から Basic 以上を積む([casebook P-R15](../casebook/02-pitfalls-index.md#e-rag-とナレッジ)) |
| ナレッジ | File Search / ベクトルストア | ストレージ課金(GB・日、1 GB 無料。モデル料と別) | standard setup では自前 Blob + AI Search 側に載る |
| ナレッジ | Foundry IQ(ナレッジベース / agentic retrieval) | **AI Search 側で課金**(agentic retrieval のトークン課金〈月 5,000 万トークン無料枠〉+ クエリ計画等のモデル従量)。SharePoint(remote)/ Web ナレッジソースは別課金 | **Serverless(Developer tier、プレビュー)は 2026-09-13 に課金開始**(Compute Unit 時間 + ストレージ)。PoC で無料前提にしない。※2026-11-22: 名称は Foundry IQ (Azure AI Search)、Serverless は「Serverless tier」の表記になり GA は両論(Search Learn = GA / Azure ブログ = 2026-12 GA)。**有償の Serverless はインデクサーの実行も CU を消費**し(セマンティックランカー・クエリ書き換え・スキル実行・KB のモデル呼び出しは別メーター)、インデクサーは累積 48 時間 / 24 時間の窓を共有する。閉域の取り込みは Dedicated の S2 / S3 / L1 / L2 のみ(Basic・S1 は不可)なので、閉域の本番を見込む見積もりは S2 以上で積む([casebook P-R19](../casebook/02-pitfalls-index.md#e-rag-とナレッジ)) |
| ツール | Web search / Grounding with Bing | 呼び出し従量(**別課金**) | DPA 対象外の説明とセット([03](./03-japan-compliance.md))。※2026-11-22: prompt agent への直付けは **Web IQ**(GA。Ignite で値下げを発表)、toolbox 経由は従来の **Grounding with Bing** で、メーターも契約条件も経路で違う。見積もりは経路ごとに分けて積む([casebook P-R18](../casebook/02-pitfalls-index.md#e-rag-とナレッジ)) |
| ツール | Code Interpreter | **セッション課金**(アクティブ1h/アイドル30分) | 会話ごとにセッションが立つ設計だと嵩む |
| エージェント | hosted agent セッション | **vCPU 時間 + メモリ GiB 時間の従量**(アクティブなセッション分。アイドルタイムアウト〈既定 15 分・2〜60 分で設定可。※2026-10-14: REST 仕様と azd 拡張 beta.19 は上限 240 分、Learn は 60 分のまま — 両論〉経過でコンピュート解放) | cpu / memory 指定は 1 セッションあたり → サンドボックスのオーバーサイズ × 同時実行数で倍増。※2026-11-22: idle timeout は **2〜240 分で確定**(両論解消)。課金は割り当て量(使用率ではない)で、**idle で止まるまでの待機時間も課金**され `stop` で終わる — timeout を延ばす設計は待機分を積む。shared subnet IPs の GA で同時実行の律速はセッションクォータ(既定 2,000 / 1,000)になった |
| エージェント | Microsoft Copilot harness(prompt agent のマネージドハーネス、preview)(2026-11-22 追加) | **サンドボックスの vCPU 時間 + メモリ GiB 時間の従量**(2026-12-01 開始。それまでは harness の実行は無料)。モデル推論と個別課金のツールは従来どおり別に課金 | 単価は devblogs 2026-10-28 に記載(Learn の料金ページへの掲載は要確認)。サンドボックスの CPU / メモリ / idle は利用者が設定できないので、会話数 × 会話あたりの実行時間で積む。PoC で使っている場合は 12-01 以降の費用を見積もり直す([casebook P-A18](../casebook/02-pitfalls-index.md#b-agent-service-コア)) |
| エージェント | Routines(スケジュール / イベント起動) | ルーチン自体の料金は pricing ページに記載なし(2026-09-26 確認) | 起動されたエージェント実行のモデル・ツール・hosted コンピュートは通常どおり課金。定期実行の回数 × 1 回あたりのコストで積む。※2026-10-06: 一時障害時の再試行(最大 5 回)の上振れを幅として置く(Step 1-3) |
| エージェント | Bot Service(Teams/M365 公開時) | SKU(※2026-11-22: 直接公開では**別途の Azure Bot Service リソースは不要**になった — publish-copilot 2026-11-12 版。Foundry の直接公開なら見積もりから外す) | 公開チャネル追加時のみ。※2026-10-14: 公開したエージェントは Microsoft 365 Copilot ライセンスのない利用者も Copilot Chat で使えるが、SharePoint や Copilot コネクタなどの**共有テナントデータにアクセスする利用は従量課金になりうる**(troubleshoot-publish-copilot の注記)— 利用者のライセンス構成と、共有データへのアクセスの有無を見積もりの前提に書く |
| 観測性 | Application Insights / Log Analytics | **取り込み GB 課金 + 保持** | トレース全量記録は高額になりがち。サンプリング設計必須(※2026-10-06: azure-monitor-opentelemetry 1.8.x の既定は 5 スパン / 秒のレート制限で、歯抜けを避けて `sampling_ratio=1.0` にすると取り込み量が増える — 全件か比率かを見積もりの前提に書く = casebook P-O16)。2026-10-14: 1.8.11 でも既定サンプラーは変わっていない。監査要件の長期保持は別途。※2026-10-06: 会話本文の属性は専用テーブル `AppGenAIContent` にも入る(2026-10-06 の japaneast 実測では従来テーブルとの**二重書き**)。移行期間の取り込み量への影響は未確認なので、本文を記録する構成では PoC で取り込み GB を実測する([casebook P-O13](../casebook/02-pitfalls-index.md#g-観測と評価)) |
| 観測性 | 評価(クラウド評価・継続的評価・Red Teaming) | 評価器の LLM 従量 | playground 評価は**既定で有効**(全プロジェクト・従量)。※2026-10-06: 合成評価器(preview)でジャッジ呼び出し回数を減らせる(Step 1-3 の式)。※2026-10-14: 評価サービス側でも 2 つの削減が入った — ジャッジプロンプトの静的部分を先頭に並べてプレフィックスキャッシュを効かせた(エージェント評価のジャッジ通信で入力トークンの約 70% がキャッシュ)、Rubric 評価器の判定出力を表形式(TOON)にして出力トークンを約 30% 削減(書式を守れない mini / nano 系の推論モデルは JSON のまま)。コード変更なしで全評価に効くが、顧客の請求額にどう効くかは書かれていない([Tech Community 2026-10-07「Making evaluations cost-efficient」](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/making-evaluations-cost-efficient/4561786))→ 係数は PoC の実測で決める。※2026-11-22: 決定モデル judge(preview)・評価 run の推定コスト・Insights のジャッジは Step 1-3 の注記。継続評価の既定の上限は 100 run / 時(`max_hourly_runs`) |
| 観測性 | Agent 365 へのエージェント活動データ(2026-10-06 追加) | Foundry の請求ではなく Agent 365 側の前提(テナントに M365 Copilot ライセンスと Frontier プログラムへの参加。料金は Agent 365 の案内で確認) | Agent 365 が有効なテナントでは Foundry リソースの収集設定(`a365LoggingEnabled`)が既定で有効。保存場所は Entra テナントのジオ。使わないならリソース単位で無効化(閉域では FW の拒否ログ対策にもなる — [casebook P-H27](../casebook/02-pitfalls-index.md#a-hosted-agent)) |
| ゲートウェイ | APIM | SKU 時間課金 | マルチテナント/チャージバック要件なら必須枠 |
| ネットワーク | Private Endpoint | 時間 + データ処理 | 閉域構成では PE が 5〜10 本になる |
| ネットワーク | Azure Firewall | **SKU 時間課金(高額)** | Managed VNet の FQDN ルールで**自動作成**される。SKU は後から変更不可 |
| ネットワーク | App Gateway + WAF | SKU 時間 + 処理 | 顧客向け公開時 |
| ガバナンス | Purview(従量)/ Defender for AI | 従量 | コンプライアンス要件時のみ |
| BYO | Cosmos DB(standard setup) | RU/s プロビジョン | **最低 3,000 RU/s/プロジェクト**(Responses 利用で実質 5,000)。プロジェクト数分乗算 |
| BYO | Storage / AI Search(standard setup) | 各 SKU | basic setup なら不要(Microsoft 管理) |
| フロント | App Service / Static Web Apps 等 | SKU | Foundry 外だが提案総額には必ず入る |
| 特化 | Voice Live(音声エージェント) | **100 万トークン単位**(テキスト / 音声の入力・キャッシュ・出力別)。ティアは選んだモデルで決まる(Pro / Standard / Lite / BYO) | アバターは TTS Avatar の分課金、カスタム音声・カスタム STT は学習・ホスティングが別課金 |
| 特化 | voice agents(`kind: voice`。※2026-11-22: Learn・SDK・ブログ = GA / GA 一覧表 = Preview の両論。GPT-Live・SIP・campaigns・post-call delivery・WebRTC は preview)/ GPT-Live(全二重音声)(2026-10-06 追加) | voice agents: 音声の入出力トークン・モデルのホスティング(`managed` はエージェント側で課金、`self_deployed` は自前デプロイの従量 / PTU)・接続時間・ツール・録音やアバター。GPT-Live: 音声の会話と、委任先のバックエンド(Responses 等)を別々に課金 | **GPT-Live の WebRTC セッションは 1 回あたり最低 15 秒の音声で課金**(WebSocket は対象外)— 短い通話・接続し直しが多い用途では「セッション数 × max(実時間, 15 秒)」で積む。voice agents のトレースの推定コストは請求ではない(Cost Management が正)。※2026-10-14: 料金の考え方は [voice-agent-pricing](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/voice-agent-pricing)(2026-10-06 版)— 推定コストはトレースの `microsoft.foundry.voice.estimated_cost.*` 属性(managed / self-deployed 別)、削減策は `max_output_tokens` の上限・短い instructions・`static_interim_response` の優先・`end_conversation` での明示終了・不要時の `store` オフ。TTS アバターの標準アバターの一部(Jeff の全スタイル・Lisa の 4 スタイル)は 2026 年 12 月から利用不可 |
| 特化 | Content Understanding | **コンテンツ抽出**(文書 = 1,000 ページ単位〈Minimal / Basic / Standard〉、音声・動画 = 時間単位〈分課金〉)+ **コンテキスト処理トークン** + **フィールド抽出の BYO モデル(生成 + 埋め込み)従量** | 3 層を合算しないと過小見積もりになる。※2026-10-06(ラボ還元): CU の usage に**キャッシュ入力の費目(`<モデル>-cached-input`)**が新たに出た。自前の集計は費目一覧を固定せず、キャッシュ入力の単価も積む([casebook P-D10](../casebook/02-pitfalls-index.md#l-文書処理と音声))。※2026-11-22: 非同期分析の上限が 300 → 2,000 ページになり、GPT-5.6 / 6 / 6.1 系を接続モデルに選べる(モデルの単価差がフィールド抽出の費用に直結)。入力文書も最長 24 時間保持される([casebook P-D14](../casebook/02-pitfalls-index.md#l-文書処理と音声)) |

**閉域構成の経験則**: Firewall + PE + APIM + App Gateway の**固定費だけで月額の下限が決まる**。小規模利用の閉域案件は「トークン代よりインフラ固定費」になるので、先にインフラ固定費を積んでから変動費を載せる。

## Step 3: 単価の取得先(見積もりの都度参照)

| 対象 | 参照先 |
| --- | --- |
| 総合(構成全体の試算) | https://azure.microsoft.com/pricing/calculator/ |
| モデル単価(Azure OpenAI / Foundry Models) | https://azure.microsoft.com/pricing/details/azure-openai/ (旧 URL `.../cognitive-services/openai-service/` はリダイレクト) |
| Agent Service(セッション課金等) | https://azure.microsoft.com/pricing/details/foundry-agent-service/ |
| AI Search(Foundry IQ・Serverless 含む) | https://azure.microsoft.com/pricing/details/search/ |
| Voice Live / Speech | https://azure.microsoft.com/pricing/details/speech/ |
| Content Understanding | https://azure.microsoft.com/pricing/details/content-understanding/ |
| Application Insights / Log Analytics | https://azure.microsoft.com/pricing/details/monitor/ |
| APIM | https://azure.microsoft.com/pricing/details/api-management/ |
| Azure Firewall / Private Link / App Gateway | pricing/details 配下の各ページ |
| Claude(パートナーモデル) | Azure Marketplace の該当オファー(**CCU 課金・クレジット/CSP 制約あり** → [features 02](../features/02-models.md)) |
| Copilot Studio(Copilot Credits)(2026-10-10 追加) | イベント別のクレジット数: [Billing rates](https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-messages-management) / パック価格: Microsoft の Copilot Studio 価格ページ / 従量のクレジット単価: Azure 小売価格 API(`serviceName eq 'Microsoft Copilot Studio'`、meter「Pay As You Go Copilot Credit」)/ 消費量の見積もり: [agent usage estimator](https://microsoft.github.io/copilot-studio-estimator/) / 最新の正: [Copilot Studio Licensing Guide](https://go.microsoft.com/fwlink/?linkid=2320995) |

注意: **デプロイタイプで単価が変わる**。2026-09-01 から Data Zone / Regional は Global 比のプレミアムが改定・新設(EU Data Zone 引き上げ、**APAC Data Zone 新設**、**米国外 Regional〈日本を含む〉引き上げ**)。Standard(従量)は 2026-09-01 以降に投入されたモデルのみ新プレミアム対象、**PTU は既存契約も対象**。率は出典で確認し、国内処理要件のある見積もりでは Global 単価を流用しない(出典: [Microsoft Foundry Model Deployment Pricing Update](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/microsoft-foundry-model-deployment-pricing-update/4535385)、2026-07-09 公開 / 07-27 更新)。**日本円建てはレート改定タイミングで USD 建てとズレる**。EA/CSP の割引率は営業経由でしか分からないため、提案書は「リスト価格ベース」と明記する。

## Step 4: PTU(プロビジョン)判断

1. **従量の月額を先に出す**(Step 1〜3)。
2. PTU 損益分岐の目安: `従量月額 ≧ 最小 PTU 数 × P_ptu_hour × 730h × (1 − Reservation 割引率)` なら PTU 検討ライン。
   - 最小 PTU 数・増分はモデル別(例: 15/5 や 25/50 など。必ず現行ドキュメントで確認)。
   - **PTU はモデル非依存(fungible)**なのでモデル乗り換えでも無駄になりにくい。Reservation は 1 か月 / 1 年。
   - ※2026-10-06 追加: **GPT-6 Astra / Sol / 6.1 Sol 以降は normalized token accounting**。`normalized TPM = Σ(トークン種別ごとの TPM × 重み)`、`必要 PTU = normalized TPM ÷ モデルの PTU あたり normalized TPM`(重み = その種別の単価 ÷ 同じモデルの短コンテキスト入力単価。入力・**キャッシュ入力**・キャッシュ書き込み・出力を短 / 長コンテキスト別に)。**キャッシュ入力も重みどおりに PTU 容量を消費**し、旧来の「キャッシュ分は 100% 控除」はこの方式のモデルには当てはまらない(他のモデルは従来どおり控除)。キャッシュ率の高い用途ほど旧規則で見積もると足りなくなる([provisioned-throughput-sizing](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/provisioned-throughput-sizing)、[casebook P-M16](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト))。※2026-11-22: GPT-5.6 以降のキャッシュ書込も重みを持ち、**12 時間キャッシュの書込の重みは 2.5**(Step 1-3 のキャッシュ書込)。
   - ※2026-10-06 追加: Fireworks モデルの PTU 既定値(最小デプロイ・増分・PTU あたり入力 TPM)は 2026-10-02 に多くのモデルで大きく改訂された(最小デプロイが倍増・PTU あたり TPM が減ったモデルが多い)。過去の試算・表を流用せず、見積もりのたびに現行の表で取り直す。
3. キャパシティ試算はポータルの **capacity calculator** で「想定 RPM・トークン/リクエスト → 必要 PTU」を出す(モデル世代で PTU あたり性能が大きく違うため手計算しない)。
4. **ピーク型トラフィックは「PTU をベースに、溢れを Standard に流す spillover 構成」**が定石(Azure OpenAI モデルのみ対応。DeepSeek/Llama 非対応)。
5. PTU デプロイは**モデルリタイア時に自動アップグレードされない(手動移行)**— 運用契約の論点([01 ヒアリング 6-4](./01-hearing-sheet.md))。※2026-11-22: 実例として、gpt-4o 2024-05-13(2027-01-14 リタイア)の後継 gpt-5.1 への自動アップグレードは Standard 系だけで、PTU と Batch は手動。o-series の後継 gpt-5.6-sol / terra は Batch・Regional Standard で提供されず、gpt-5.6-sol は Global Provisioned のカバレッジも限定的なので、再見積もりの対象モデルが変わりうる([casebook P-M21](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト))。

## Step 5: コスト削減レバー(提案の調整代)

| レバー | 効果 | 制約 |
| --- | --- | --- |
| Batch デプロイ | **50% 引き** | 24h ターゲット・SLA なし。夜間バッチ処理向け |
| Flex 処理(`service_tier: flex`、**プレビュー**) | 対応モデルでの低優先度処理 | **Standard のトークン単価の 50% 割引**(キャッシュ入力割引も併用可)、専用の Flex メーターで Cost analysis 上も分離。**対応モデルは当初 `gpt-5.6-sol`(2026-07-09)の Global Standard のみ**(※2026-10-14 更新: 2026-10-12 版で **7 モデル**に拡大 — `gpt-6.1-sol` / `gpt-6-sol` / `gpt-6-luna` / `gpt-6-astra` / `gpt-5.6-sol` / `gpt-5.6-luna` / `gpt-5.6-terra`、いずれも Global Standard の全リージョン〈Japan East の Global Standard を含む〉。Data Zone / Regional は対象外のままなので、データ所在の要件で Data Zone を使う案件には効かない)、SLA なし。容量不足の HTTP 429 は非課金だが、Flex と Standard は同じデプロイのクォータを共有する。**2026-09-25 に flex→standard の自動フォールバックが廃止**され、非対応モデルへの flex 要求は HTTP 400(2026-09-29: 専用ページ [Flex processing](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/flex-processing) が 2026-09-28 に公開され、「専用ページが見当たらず要確認」を解消)。見積では「Flex で回す比率」と「Standard へのアプリ側フォールバック率」を分けて置く。逆方向の Priority processing(低遅延・割増)は [priority-processing](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/priority-processing)。※2026-10-06: priority の効果・課金は応答の `service_tier` で確認する — 非対応モデルへの `priority` 指定はエラーにならず Standard で処理され(計測記事)、対応モデルでも急増時・ピーク時・長コンテキストは Standard に格下げされて Standard 料金になる([casebook P-M17](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト)) |
| プロンプトキャッシュ | キャッシュ入力単価が大幅減 | システムプロンプト・ツール定義を先頭に固定する設計が前提。※2026-10-06: 従量では単価が下がるが、GPT-6 系の PTU ではキャッシュ入力も容量を消費する(Step 4)。※2026-10-14: Grounding with Bing Search / Bing Custom Search を付けたエージェントでは、ツールが毎リクエストに現在時刻入りの指示を追加するため**プロンプトキャッシュがヒットしない**(bing-tools の既知事項)— キャッシュ割引なしで見積もる([casebook P-M19](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト))。※2026-11-22: **GPT-5.6 以降は書込にも課金**されるので、ヒット率が低い用途ではかえって高くなりうる(Step 1-3) |
| Model router | 簡単な質問を安いモデルへ自動ルーティング | Global / Data Zone Standard のみ。Claude をプールに入れるなら事前デプロイ必須(Claude 分は Marketplace 課金)。ルーティングプールはバージョン更新で入れ替わるため評価をやり直す(model-router 2026-09-01 版。非 OpenAI ルーティングのプレビュー表記は現行ページにない)。※2026-10-14: 2026-10 にプールが 35 モデルへ拡大し、Fireworks の 3 モデル(`FW-GLM-5.3` / `FW-GLM-5.3-Flash` / `FW-Kimi-K3`)が事前デプロイ不要で既定プールに入った(Fireworks の従量は別のクォータプール・推論は Microsoft 施設外 — 下記と [03](./03-japan-compliance.md) §2)。既定プールのままだとルーティング先の単価・課金経路が混ざるので、見積もりは model subset で絞った構成で行う([What's new in model router](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/whats-new-model-router))。※2026-11-22: 課金は**ルーティング料(入力トークンあたり)+選ばれたモデルの利用料**で、自前の PTU が応答した場合はルーティング料だけ — 見積もりにルーティング料の行を足す。プールは 45 モデル(Book of News は 50)、Fireworks は有効化したサブスクリプションだけ。Auto(preview)は常に Global Standard で処理し、Data Zone の router は Claude に流さない([casebook P-M22](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト))。AI Gateway の automatic model selection(preview)は **preview 中はルーティング料なし**(GA 時に課金開始とブログ)、ゲートウェイとバックエンドの料金は発生 |
| 合成評価器(preview、2026-10-06 追加) | 評価のジャッジ呼び出しを 1 回に束ねて評価費用・時間を削減 | preview。ジャッジは GPT-5.6 系推奨。主結果は全コンポーネント合格で 1 なので、ゲートの粒度が変わる(どの観点で落ちたかはコンポーネント結果で見る)。※2026-10-14: 公式の記事は「作業負荷に敏感なルーブリックは個別評価器を併用」と推奨。廃止された Quality Grader の後継も Output Quality([casebook P-O23](../casebook/02-pitfalls-index.md#g-観測と評価)) |
| セマンティックキャッシュ(APIM) | FAQ 的トラフィックの LLM 呼び出し自体を削減 | RediSearch 有効の Azure Managed Redis が別途必要(作成時のみ有効化可) |
| モデルの右サイズ化(mini/nano 系) | 単価 1/10 以下も | 評価で品質確認してから。リーダーボードはプレビュー |
| 出力トークン制御 | 出力単価は入力の数倍 | 構造化出力・max tokens・簡潔指示 |
| 履歴の要約・打ち切り | 長い会話の入力爆発を抑制 | UX とのトレードオフ |

## Step 6: Copilot Studio(Copilot Credits)と比べるとき(2026-10-10 追加)

「Copilot Studio で作るか Foundry で作るか」の比較では、**課金の単位が違う**ことを先に押さえる。Foundry はトークン量(+ページ・時間・固定費)に比例し、Copilot Studio の standard harness は**イベント数**に比例する。同じ業務でも、どちらが安いかは「1 件あたり何イベント起きるか」で逆転する。

### 6-1. Copilot Studio のイベント別レート(standard harness)

出典: [Billing rates and management](https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-messages-management)(2026-08-03 版、2026-10-01 更新)。**レート(クレジット数)は Copilot Studio が提供する全モデル共通**で、Foundry モデルの BYO は別課金。

| イベント | クレジット | 備考 |
| --- | --- | --- |
| 定型回答(classic answer) | 1 | 作成者が書いた固定の応答 |
| 生成回答(generative answer) | 2 | ナレッジを使った生成。**トークン量に関係なく固定** |
| エージェントアクション | 5 | トリガー・深い推論・トピック遷移(アクティビティマップに出る単位)。computer use もこの単価 |
| テナント Graph グラウンディング | 10 | Microsoft Graph 全体への RAG |
| エージェントフローのアクション | 13 / 100 アクション | Power Automate のクラウドフローは対象外(Power Automate のライセンス) |
| AI ツール(プロンプト)basic / standard / premium | 0.1 / 1.5 / 10(1K トークンあたり) | 表には旧表記の「10 応答あたり 1 / 15 / 100」も併記。入力には Microsoft のシステムプロンプト(約 1,200 トークン)が含まれる([Prompt tokens](https://learn.microsoft.com/en-us/ai-builder/licensing-prompt-tokens)) |
| 文書処理(content processing) | 8 / ページ | |
| 音声(classic / GenAI / premium GenAI) | 10 / 35 / 75(1 分あたり) | 中の回答・アクションは込み |

- **推論モデル**は「機能レート+premium(10 クレジット / 1K トークン)」の合算。
- **M365 Copilot ライセンスの利用者**が本人の ID で使う社内向け(B2E)の利用は**課金なし**(公正利用の上限あり。computer use は対象外、エージェントフローは「When an agent calls the flow」トリガーのみ)。
- **GitHub Copilot harness** は別体系: LLM トークン・ツール・harness 自体にクレジットを課金するが、**トークンからクレジットへの換算率は公開されていない**(見積もりツールの範囲図のみ)。しかも**作成・テストの段階から課金**される([Usage-based billing](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agents-experience/billing-credit-overview) 2026-09-10 版)。
- 前払いの容量は月ごとで繰り越しなし。**前払い容量の 125% に達するとカスタムエージェントが停止**する(従量課金に紐づけた環境は停止しない)。エージェント単位の月間上限も設定できる。

### 6-2. 比較の式

```
Copilot Studio 月額 = Σ(イベント種別ごとの件数 × クレジット数) × P_cc
                     − M365 Copilot 利用者の B2E 分
Foundry 月額       = Σ(LLM 呼び出し × トークン × P_tok)+ ページ / 時間課金
                     + 固定費(AI Search・監視・hosted agent・Cosmos DB、閉域なら Firewall / PE / APIM / App Gateway)
                     + 構築・運用の工数
```

`P_cc` は 1 クレジットの単価(パック・従量・前払いプランで異なる。Step 3 の取得先で確認)。

### 6-3. 構造上の傾向(2026-10-10 の定価で試算した本ドキュメントの判断)

| 業務の形 | 傾向 | 理由 |
| --- | --- | --- |
| 長い文脈で 1 回答える社内 Q&A | **Copilot Studio が同等以下になりうる** | 生成回答は文脈の長さに関係なく 2 クレジット固定。フロンティアモデルで同じ文脈を Foundry に投げるとトークン代だけで上回る場合がある。小型モデルに落とせるなら Foundry が安い |
| M365 Copilot 保有者の社内利用 | **Copilot Studio**(限界費用ほぼ 0) | B2E 利用が課金なし |
| 1 件で複数のツールを呼ぶ自律処理(受注処理など) | **件数が多いと Foundry** | アクション 1 回 5 クレジット。Foundry はツール呼び出しの分のトークンだけで、定価の試算では約 1/2(フロンティアモデル)〜1/10 以下(小型モデル) |
| 文書のページ処理 | **件数が多いと Foundry** | 8 クレジット / ページに対し、定価比較で Document Intelligence のプリビルトは約 1/8、カスタム抽出でも約 1/3(CU は抽出単価に BYO モデルのトークンを加算) |
| 推論モデルを使うプロンプト | **Foundry** | premium の 1K トークンあたりレートは、定価の試算で Foundry の同等モデルのトークン代の数倍〜20 倍程度 |

**分岐点** = 月間件数 ×(1 件あたりの差額)が「Foundry の固定費+運用工数」を超えるかどうか。閉域構成では固定費が大きい(Step 2 の経験則)ので分岐点は右にずれる。比較は必ず agent usage estimator の値と、Foundry 側の試作で測ったトークン量で行う(イベント数・トークン数とも、見積もりは実測で外れやすい — [casebook P-X05](../casebook/02-pitfalls-index.md#k-copilot-studio-m365-apim-業務連携))。

## 試算例(単価は記号。数字を入れて使う)

### 例 A: 社内 RAG チャット(500人・ポータル運用)

前提: 500人 × 20営業日 × 8クエリ/日 × 1.5ターン。入力 4,000 tok/ターン(システム 500 + RAG 2,400〈800×3チャンク〉+ 履歴 600 + 質問 500)、出力 500 tok。

```
月間入力 = 500 × 20 × 8 × 1.5 × 4,000 = 4.8 億 tok → 480 × P_in
月間出力 = 同 × 500                  = 0.6 億 tok →  60 × P_out
固定費   = AI Search SKU + App Insights 取り込み(+ フロント)
一時費   = 初期インデックス構築(文書量 × 埋め込み単価)+ 構築工数
```

**構造**: このパターンは変動費(トークン)が支配的。モデルの右サイズ化とチャンク取得数の調整が効く。

### 例 B: 顧客向けチャット(10,000 MAU・閉域寄りの公開構成)

前提: 10,000 MAU × 3クエリ/月 × 2ターン。入力 3,000 / 出力 400 tok。

```
変動費 = 10,000 × 3 × 2 × (3,000 × P_in + 400 × P_out) = 1.8億 in + 0.24億 out
固定費 = App Gateway/WAF + APIM + PE 群 + Bot Service + App Insights + AI Search
```

**構造**: この規模だと**固定費(ゲートウェイ層)が変動費を上回りがち**。「まず固定費の下限を提示 → 利用増でも変動費は緩やか」という説明が顧客に通りやすい。ピークが読めないため PTU は初期から入れず、従量 + クォータ監視で開始。

### 例 C: 文書処理バッチ(月 10 万ページ)

```
前処理 = 10万ページ × CU コンテンツ抽出単価(1,000 ページ単位)+ コンテキスト処理トークン + フィールド抽出の BYO モデル従量
推論   = 抽出後の要約・分類を Batch デプロイ(50%引き)で
固定費 = ほぼなし(Storage + 監視のみ)
```

**構造**: ページ課金(CU/DI)が支配項。**CU は BYO モデル接続必須**なのでそのモデル従量も忘れず加算。リアルタイム性不要なら全部 Batch に寄せる。

## 見積もり時の注意(検証済みの事実)

- **Azure OpenAI にコストのハードリミット機能はない**(公式明記)。Budget + アクショングループの自動化は自前開発。提案書に「上限保証」と書かない。※2026-11-22: **Foundry の cost controls(preview)**で予算超過の要求を HTTP 429(`x-ms-budget-cause: budget_exceeded`)で止められるようになったが、**対象は GPT と o-series のみ**(Claude 等は対象外)で、**PTU・ツール料金・hosted agent のコンピュートは数えず**、新しい GPT モデルは価格が入るまで約 1 週間計上されない。判定が間に合わなければ要求は通り(fail-open)、Spending は課金と突合しない推定。「上限保証」と書かない方針は変えず、cost controls は一次の歯止め+APIM / AI Gateway のトークン上限+予算アラートの多層で説明する。cost control を持つプロジェクトは削除できない([casebook P-M25](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト))。
- Cost Analysis への反映は**取り込みタイミングにより遅延あり**(公式は時間非特定)。分単位の照合はしない。※2026-11-22: Foundry の Cost 画面のページ(analyze-costs-cost-management)は「**コストは利用の 8〜24 時間後**(利用量は数分)」と明記した。**Foundry のロールではコストが見えない**ので、見積もりの前提に「Cost Management Reader を誰に付けるか」を書く([casebook P-I16](../casebook/02-pitfalls-index.md#c-id-と-rbac))。
- プロジェクト単位のチャージバック(`project` タグ)は**プレビューかつ Marketplace モデル(Claude 等)非対応**。テナント/部門別の正確な按分が要件なら **APIM の `llm-emit-token-metric`**(既定8ディメンション + カスタム最大5)で自前実装。※2026-11-22: エージェント名のタグ(`agent.name`)は 2026-11 以降の利用から付与され、内訳はタグ付きの課金だけなので合計より小さくなる。パートナー / コミュニティのモデルのメーターは Foundry リソースではなく RG 配下に出る。要求単位の独自タグでコストを分ける caller attribution は private preview(Tech Community 2026-11-19)。
- プレビュー期間中の機能(Memory 等)は**課金体系が変更されうる**と公式に明記。
- ※2026-10-06 追加: **Fireworks モデルの従量(pay-per-token)は Global Standard と Data Zone Standard で別々のクォータプール**(Enterprise 契約は既定で各プール 10M TPM / リージョン / サブスクリプション、プール内は全 Fireworks モデルで共有)。さらに Fireworks 側の**適応レート制限**で実効の上限はクォータより低くなりうる(利用増に合わせて自動で上がる)。スループットを前提にする見積もりは段階的な立ち上げと 429 の再試行を含めて PoC で確かめる([enable-fireworks-models](https://learn.microsoft.com/en-us/azure/foundry/how-to/fireworks/enable-fireworks-models))。データ処理場所は [03](./03-japan-compliance.md) §2。
- モデルリタイア(GA 後 12〜18 か月。温度感 18 か月・安全側 12 か月)のたびに単価が変わる。**年間契約の提案では「モデル移行時の再見積もり条項」を入れる**。※2026-10-14: xAI の Grok は「Grok 4.7 以降の GA モデルは最低 6 か月提供」という短い下限が新設され、Fireworks の一部モデルの従量はリタイア表にない期限で終了した([casebook P-M07 / P-M18](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト))— 再見積もり条項の対象にパートナーモデルを含め、提供期間の下限をモデルごとに書く。※2026-11-22: gpt-6.1-terra は GA から 12 か月(2027-10-26)でリタイアする。**Baseten(preview)の pay-per-token は 30 日前予告**で、Baseten / fal は Microsoft の Product Terms・DPA の対象外(Fireworks は DPA の範囲内)— 契約条件の違いを見積もりの前提に書く([casebook P-M23](../casebook/02-pitfalls-index.md#f-モデル-クォータ-コスト)・[03](./03-japan-compliance.md) §2)。
