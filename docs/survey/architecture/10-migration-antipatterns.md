# 10. 移行アーキテクチャとアンチパターン集

[← アーキテクチャ TOP](./README.md)

> **最終更新:** 2026-07-30(公式ドキュメントとの突合検証で訂正) / 2026-09-04(アンチパターン A12〜A14 を追加)/ 2026-09-26(廃止期限表をリタイア表 2026-09-21 版・各出典で再検証し、期限到来分の表記とモデルのリタイア日を更新。Routines の GA 化を A6 に反映)/ 2026-10-06(リタイア表 2026-09-28 版で Claude 4.5 系の期限を更新、Anomaly Detector のサービス終了・Voice Live × classic 連携の Deprecated・トレース本文の専用テーブル移行を期限表に追加、アンチパターン A16〈latest 追従のまま CI でデプロイしてからテスト〉・A17〈保護テーブルの設定だけで本文を隠せたと判断〉を追加、A11 に公式間不整合の例を追加) / 2026-10-14(差分更新: `gpt-4.1-nano` のリタイアが 2027-04-14 に戻った〈3 度目の往復〉ため行を移動、On Your Data は本日が期限当日、直近の期限・Fireworks の Pay-per-token 終了・Grok の最低 6 か月提供を追記、hosted agent の idle timeout 上限の両論〈REST 仕様・azd = 240 分 / Learn = 60 分〉とユーザー分離ページの整理を 2.0 に、A11 に 2026-10-14 の食い違い例、A17 に「公式の確認手順は従来テーブルの残存を見ない」を追加)

Foundry は「GA だが足元が動いている」プラットフォームで、**2026 年後半から 2027 年にかけて確定済みの廃止が集中している**。新規設計であっても、廃止スケジュールを知らずに選ぶと 1 年以内に作り直しになる。本ページは (1) 既存資産からの移行アーキテクチャ、(2) 廃止期限の設計への効き方、(3) 提案時に踏みやすいアンチパターン、をまとめる。公式ドキュメント以外の出典(公開記事・実測)による詰まりどころは [casebook 02](../casebook/02-pitfalls-index.md) に分離してある。

## 1. 確定済み廃止スケジュールと設計への影響

| 期限 | 対象 | 設計への効き方 | 移行先 |
|---|---|---|---|
| ~~2026-07-31~~ **ブロック中** | コンテナプロトコル 1.0.0 | 移行ガイド(migrate-hosted-agent-preview、2026-09-25 更新)で「**1.0.0 is no longer supported, and the platform blocks requests**」(現在形)を確認(2026-09-26)。旧記載の「2026-07-31 からブロック」という日付は現行の出典(isolate-sessions-per-user 等)から消えている。2.0.0 でないと 1 セッション内の複数ユーザー多重化ができない | プロトコル 2.0.0 |
| ~~2026-08-20~~ **期限到来** | Hosted agents 初期プレビュー基盤 | サポート終了済(ガイドは「supported only until August 20, 2026」の表現のまま)。未移行の hosted agent は**再デプロイ必須**。新基盤の SDK 要件は `azure-ai-projects` **2.3.0 以降**(旧 2.0.0) | 新基盤へ再デプロイ |
| ~~2026-08-26~~ **廃止済** | Assistants API(Azure OpenAI) | 出典冒頭が「**The Assistants API is retired**」(ページは previous-versions 配下へ移動)。Threads / Runs 前提のアプリは全面改修。**状態データは自動移行されない** | Responses API(Agents v2) |
| ~~2026-08-26~~ **廃止済** | `azure-ai-inference` SDK | 全言語対象。beta のまま GA せず終了(features 第3版で retired 表記を確認) | OpenAI SDK + v1 API |
| ~~2026-09-25~~ **期限到来** | Azure AI Vision Image Analysis 4.0/3.2 の**移行計画策定目安** | migration-options に「Make a plan to transition away ... by September 25, 2026」。廃止本体は下の 2028-09-25 | (下記) |
| ~~2026-09-30~~ **移行日到来** | トレースの会話本文(GenAI 機微属性 7 種)の専用テーブル `AppGenAIContent` への振り分け(既定化) | 公式は「移行日以降に取り込むデータは既定で `AppGenAIContent` だけ」とするが、**2026-10-06 の japaneast 実測(feature flag 未登録)では従来テーブルとの二重書き**。従来テーブルから `gen_ai.*` の値を読む自作 KQL・アラートは書き換え対象。**一時 opt-out フラグ `optOutProtectGenAISensitiveData` は 2027-09-30 で廃止**([09 §3.6](./09-operations.md#3-6-トレースに会話の中身を残すか-hosted-agent-の選定基準)) | `AppGenAIContent` を読むクエリ + 保護テーブル |
| ~~2026-10-01~~ **サービス終了** | Anomaly Detector | Learn の anomaly-detector 配下は 2026-10-05 にアーカイブ削除 | (自前の異常検知 / Fabric 等) |
| ~~2026-08-31~~ **Deprecated** | Voice Live × Agent Service (classic) 連携 | クイックスタートは 2026-10-05 に Deprecated 配下へ。新規の音声体験には voice agents(preview)が案内される([08 E1](./08-usecase-specialized.md#e1-音声エージェント-コンタクトセンター)) | Voice Live with Foundry Agent Service / voice agents |
| **2026-10-14(本日が期限当日)** | **Azure OpenAI On Your Data** | 廃止日が公表済み(use-your-data 2026-09-10 版で再確認)。「モデルが直接データを読む(オーケストレーター不要)」構成が終わる。RAG の既存提案書は要更新。**2026-10-14 確認:** 出典は「will be retired on October 14, 2026」の未来形のまま(updated_at 2026-09-11)で、廃止後の表記にはまだ変わっていない → 次回更新で廃止済みの表記と既存デプロイの挙動を確認する | **Foundry Agent Service + Foundry IQ** |
| ~~2026-10-19~~ → **2026-11-15 〜 11-30** | `claude-haiku-4-5`(v1・v2)= **2026-11-15** / `claude-opus-4-5` = **2026-11-24** / `claude-sonnet-4-5` = **2026-11-30** | リタイア表 2026-09-28 版で旧 2026-10-19 から後ろ倒し(リタイア表は往復改訂するので「延長された」と断定せず直前に再確認)。Replacement 欄は sonnet-4-5 のみ `claude-sonnet-5-5`、opus / haiku は空欄 | 後継の Claude(4.6 以降 / 5 系)を自社評価で選定 |
| **2026-11-19** | `o1` / `o1-pro` / `o3` / `o3-pro` / `o3-deep-research` / `o3-mini` / `o4-mini` | リタイア表 2026-09-21 版で **2026-11-19 に一本化**(features 第3版が記録した 2026-09-02 版の 10-01〜10-21 から後ろ倒し)。後継は gpt-5.6-sol(o3-mini / o4-mini は gpt-5.6-terra) | gpt-5.6 系 |
| **2026-12-01** | ビジュアル Workflows | **ポータルでマルチエージェントを組む構成が消える。**長期案件で提案不可(workflow 2026-09-17 更新・GA 一覧でも同日付) | Microsoft Agent Framework(推奨)/ Logic Apps / A2A |
| **2026-12(月単位の表記)** | Text to speech アバターの標準アバター: **Jeff(全スタイル)と Lisa の 4 スタイル**(graceful-sitting / graceful-standing / technical-sitting / technical-standing) | standard-avatars(2026-10-12 版)が「2026 年 12 月から利用不可」と記載(日付は月単位のみ。追加時期は公開ミラー消失で特定できず)。標準アバターのうち Harry / Jeff / Lisa / Lori / Max / Meg は実在の俳優ベースで、提供は俳優とのライセンス契約に依存すると明記 — **標準アバターを固定の UI キャラクターとして設計しない**(本ドキュメントの判断)([08 E1](./08-usecase-specialized.md#e1-音声エージェント-コンタクトセンター)) | 他の標準アバター / カスタムアバター / システム選択のフォールバック |
| **2026-12-09** | `gpt-4o`(2024-05-13) | リタイア表 2026-09-21 版で 2026-12-09(同 2026-09-02 版の 10-01 から後ろ倒し)。**gpt-4o の 2024-08-06 / 2024-11-20 版と gpt-4o-mini・gpt-4.1・gpt-4.1-mini は 2027-04-14**(2026-10-14: gpt-4.1-nano も同日に戻った → 下の行)。モデル固定でチューニングしたプロンプトの再検証が必要 | gpt-5.6-sol / gpt-5.1 |
| **2027-03-31** | Agents (classic)(v1) | classic プロジェクト上のエージェント資産(classic whats-new 2026-09-10 版で再確認) | Agents v2 |
| ~~2026-10-14~~ → **2027-04-14** | `gpt-4.1-nano`(2025-04-14) | リタイア表 2026-09-21 版で 2026-10-14(features 第3版が参照した 2026-09-02 版では 2027-04-14 と記録されている。**表の日付が版ごとに動く**ので直前に再確認)。**2026-10-14 更新: リタイア表(en-us・foundry-classic・ja-jp の 3 ページで一致)は再び 2027-04-14**(Deprecated、後継欄は空欄)で、gpt-4.1 / gpt-4.1-mini と同日に戻った(2026-09-07 = 2027-04-14 → 09-26 = 2026-10-14 → 10-14 = 2027-04-14 の 3 度目の往復。期限当日の直前まで動いた例)。旧記載の「On Your Data と同じ 2026-10-14」は当てはまらなくなった | gpt-5.x 系 |
| 2027-04-20 | prompt flow | **新規開発に非推奨。**ランタイムコンテナはセキュリティ更新も停止済み | Microsoft Agent Framework |
| 2027-10-01 〜 11-19 | ファインチューン済みモデルの **deployment** | gpt-4o / gpt-4o-mini = 2027-10-01、gpt-4.1 / 4.1-mini / 4.1-nano = 2027-10-14、o4-mini = 2027-11-19(training は既存顧客のみ各 6 か月前まで)。**FT は作り直しが前提** | 後継ベースモデルで再ファインチューニング |
| **2028-09-25** | Azure AI Vision Image Analysis 4.0/3.2 | 画像解析パイプラインの作り替え | Document Intelligence / Content Understanding / Foundry Models |
| **日付未公表(Planned/TBD)** | Agent Applications(旧 publishing モデル) | 廃止告知(Planned)と EOS(TBD)が予告済み。レガシー ID のエージェントは現時点で**インプレース昇格不可**(作り直し)。ただし「Legacy agent identity upgrade gesture」が **Coming soon** と表示(migrate-agent-applications 2026-09-25 更新) | 新オブジェクトモデル(Agent に統合) |
| 未発表(投資停止) | ハブベースプロジェクト(classic) | 廃止日は未発表だが新規投資は停止。**新規案件で選ぶ理由はほぼない** | Foundry プロジェクト |

出典・詳細は [features/README の重要期限表](../features/README.md)。モデルのリタイア日は [Model retirement schedule](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule)(ms.date 2026-09-28、2026-10-06 確認。**2026-10-14 注記:** 「09-28」は公開リポジトリ上の ms.date で、Learn のページ meta は ms.date 2026-09-21・updated_at 2026-09-23 のまま include 経由で表が差し替わる〈ja-jp 版の updated_at 2026-10-08 が改訂日の目安〉。updated_at だけで「変化なし」と判定しない)。プレビューモデルの短期リタイア(`gpt-image-1` 2026-10-23、`sora-2` 2026-10-15、`MAI-Image-2.5` 系 2026-10-01〈到来済み〉など)は [08 章 E4](./08-usecase-specialized.md) を参照。**2026-10-06 時点の直近:** gpt-4.1-nano 10-14、gpt-4o-transcribe / -mini-transcribe / -mini-tts・sora-2 10-15、Cohere-command-a-plus-05-2026 10-16、gpt-image-1 10-23、codex-mini 11-15、o1 / o3 / o4-mini 系 11-19、gpt-4o(2024-05-13)12-09、tts / whisper 12-15。**2026-10-14 時点の直近:** On Your Data 10-14(当日)、**gpt-4o-transcribe / -mini-transcribe / -mini-tts(各 2025-03-20 版)・sora-2 10-15(明日。Voice Live の転写モデル選択肢には `gpt-4o-transcribe` / `gpt-4o-mini-transcribe` が残っており、Voice Live 側の扱いは記載なし)**、Cohere-command-a-plus-05-2026 10-16、gpt-image-1 10-23、codex-mini・claude-haiku-4-5 11-15、o1 / o3 / o4-mini 系 11-19、claude-opus-4-5 11-24、claude-sonnet-4-5 11-30、TTS アバターの Jeff / Lisa 4 スタイル 2026-12、gpt-4o(2024-05-13)12-09、tts / whisper 12-15(gpt-4.1-nano は 2027-04-14 に戻ったので外れた。リタイア表の他の全行は 10-06 から不変)。**リタイア表を経由しない終了もある:** Fireworks の `FW-Kimi-K2.6` / `FW-Kimi-K2.7-Code` / `FW-Inkling` の **Pay-per-token は 2026-09-25 に終了済み**(enable-fireworks-models の表。PTU は継続、リタイア表の Fireworks 行には載っていない)。

### 設計判断への翻訳

- **「ポータルだけで完結するマルチエージェント」を提案してはいけない。** 2026-12-01 で消える。単一の Prompt agent + ツールは廃止対象外なので、そこまでで足りるかを先に確認する。
- **PTU を使うなら、モデル更改が手動である前提の運用設計を入れる。** Standard は自動アップグレードされるが Provisioned は手動。リタイア通知は GA モデルで 60 日前。
- **モデルの最低提供期間は提供元で違う(2026-10-14 追加):** 「GA の SpaceXAI Grok モデルは **Grok 4.7 以降、最低 6 か月提供**」(models-sold-directly-by-azure・grok how-to・model-retirements、2026-10-14 確認)で、Azure OpenAI(18 か月)・他のパートナーモデル(12 か月)より短い下限になった。Grok 4.7 は Japan East の Global Standard で使えるが、**長期案件の固定モデルにはせず、半年ごとの差し替え評価を運用に入れる**(本ドキュメントの判断)。新しいモデルほどリタイア表への掲載が遅れる(grok-4.7・claude-haiku-5-5・GPT-6 系は 10-14 時点で未掲載)
- **classic(ハブベース)にしかない機能に依存すると出口がない。** prompt flow、serverless API デプロイ、Azure Language の一部機能(CLU / CQA / カスタム NER)、Risks & safety モニタリングは classic 側にしか無い(マネージドコンピュートのモデルデプロイは新ポータルに対応済み〈パブリックプレビュー〉なので前版の列挙から外した。GA 一覧表「Models — managed compute is a Preview deployment type」)。これらが要件に入るなら、classic を選ぶ判断ではなく**代替手段で要件を満たす設計**を先に検討する。

## 2. 移行パターン別アーキテクチャ

### 2.0 【最優先】Hosted agent 初期プレビュー基盤 → 新基盤(期限 2026-08-20)

> **2026-09-26 注: 期限到来済み。**旧基盤はサポート終了(移行ガイドは 2026-09-25 更新でも「supported only until August 20, 2026」の表現)。以下は未移行資産を棚卸しするときの差分表として残す。

**本ドキュメント作成時点(2026-07-29)で残り約 3 週間。** 2026 年 4 月より前に `azure-ai-agentserver-agentframework` / `azure-ai-agentserver-langgraph` またはプレビュー hosting API で作った hosted agent が対象で、**自動移行されない**。

「SDK のバージョンを上げる」レベルの話ではなく、パッケージ構成・API・エンドポイント・ID・ライフサイクル管理がまとめて変わる。

| 項目 | 旧(初期プレビュー) | 新 |
|---|---|---|
| サーバーパッケージ | `azure-ai-agentserver-agentframework` / `-langgraph`(**削除済み**) | `azure-ai-agentserver-responses` / `-invocations` |
| MAF パッケージ | `agent-framework` 単一 | `agent-framework-core` / `-openai` / `-foundry` / `-orchestrations` + `agent-framework-foundry-hosting` |
| MAF API | `AzureAIAgentClient` / `ChatAgent` / `@ai_function` | `FoundryChatClient` / `Agent` / `@tool(approval_mode=...)` |
| 起動 | `from_agent_framework(agent).run()` | `ResponsesHostServer(agent).run()` |
| ルーティング | 共有プロジェクトエンドポイント + `agent_reference` | **エージェント専用エンドポイント**(`project.get_openai_client(agent_name=...)`) |
| 実行 ID | プロジェクトのマネージド ID(共有) | **デプロイ時に専用の Entra agent identity を自動発行** |
| ライフサイクル操作 | `az cognitiveservices agent start/stop`、min/max replicas | **全廃**(自動プロビジョン / アイドルタイムアウトで停止。既定 15 分、バージョンごとに 2〜60 分で設定可 — hosted-agents 2026-09-11 版。**2026-10-14: 上限は両論** — REST 仕様〈azure-rest-api-specs PR #46925、2026-10-06 マージ〉と azd 拡張 `azure.ai.agents` 1.0.0-beta.19 は 240 分〈14,400 秒〉まで受け付けるが、Learn の hosted-agents は 2〜60 分のままで、azd 側は「60 分超はサービス側の対応がデプロイされてから有効」と注記 → 60 分超を前提にしない。停止後もセッション状態〈`$HOME`・`/files`〉は保持され、非アクティブ 30 日で完全削除) |
| Capability host | 作成が必要 | **不要**(削除) |
| プロトコルバージョン | `"v1"` | `"1.0.0"`(semver) |
| CLI | `az cognitiveservices agent` 拡張 | Agent Service ドキュメントは削除済みとして `az rest` / `azd ai agent` を案内(※ Azure CLI リファレンスには Core・Preview として現存しており公式間で表記揺れ) |
| 必要ロール | Foundry Owner 等 | **Foundry Project Manager**(プロジェクトスコープ) |

**さらにコンテナプロトコル 1.0.0 自体もサポート終了**で、**1.0.0 のエージェントへのリクエストはプラットフォームがブロックする**(2026-09-26 時点の移行ガイドは現在形。旧記載の「2026-07-31 から」の日付は出典から消えた)。2.0.0 では `x-agent-foundry-call-id` の転送が必要になる代わりに、**1 セッション内の複数ユーザー多重化**が安全に行える(1.0.0 では不可)。**ヘッダーの役割に注意(2026-09-26 訂正):** 中間層(自社サービス)がエンドユーザーを指定するのは **`x-ms-user-identity`** で、送るには組み込みロールに含まれない `.../agents/endpoints/UserIdentityImpersonation/action` を**カスタムロールで明示付与**する必要がある(無いと 403。以前は `Microsoft.CognitiveServices/*` で足りたが、現在は含まれない)。`x-agent-user-id` はプラットフォームがコンテナ側へ注入するヘッダーで、**呼び出し側から送ってはいけない**(isolate-sessions-per-user 2026-09-21 更新・multiplex-session-users 2026-07-30 更新)。値はブラウザ由来ではなくサーバー側で認証済みの ID から導出する。マルチテナントで hosted agent を使うなら 2.0.0 が前提。**2026-10-14 注記(文書の整理であり新機能ではない):** isolate-sessions-per-user / multiplex-session-users / pass-isolation-keys / invoke-hosted-agent の 4 ページが ms.date 2026-10-13 に改訂されたが、分離モデルは 2026-09-26 時点と同じ(差分は azd の `--user-identity` の追記)。押さえる点は (1) **委任された利用者どうしはプラットフォームが隔てない**(アプリが 2 人を同じセッション ID に送れば互いのデータが見える)、(2) 意図的に 1 セッションを共有する multiplex でも、**コンテナが自分で保存するデータ(ファイル・行・キャッシュ)は自動では分かれない**ので `(agent_session_id, user_id)` をキーにする、(3) プロジェクトの **Foundry User** を持つ ID は利用者を問わず全セッションを一覧・管理できる(内容の読み取りまで含むかは記載なし)、(4) 旧 isolation key(`x-agent-user-isolation-key` 等)は**プロトコル 1.0.0 用の履歴資料**扱いで、現行の azd 拡張は旧フラグを受け付けず、2.0.0 の経路に旧ヘッダーを送るとエラー。**1.0.0 から移行するときは isolation key をそのまま移さず `x-ms-user-identity` に置き換える**([06 ③④](./06-usecase-customer-facing.md#分離設計で必ず潰す点))。

**LangGraph を載せている場合の追加作業:** LangGraph 専用アダプタは削除されたため、`ResponsesAgentServerHost` + `@app.response_handler` で `context.get_history()` から履歴を LangChain のメッセージ型に自分で変換する実装が要る。モデル接続も `AzureChatOpenAI` ではなく `ChatOpenAI(base_url=f"{FOUNDRY_PROJECT_ENDPOINT}/openai/v1", use_responses_api=True)` に変える(プロジェクトスコープ権限だけで済むようになる)。Toolbox 接続には `langchain-mcp-adapters` + `mcp` が必要。

### 2.0b Agent Applications(旧 publishing モデル)→ 新オブジェクトモデル

エージェントの公開まわりも世代交代している。旧モデルは Agent(データプレーン)+ **Agent Application**(コントロールプレーンの ARM リソース)+ Deployment の 3 階層だったが、新モデルでは **Agent オブジェクトに統合**され、作成時点で安定エンドポイント・プロトコル構成・エージェント ID・agent card を持つ。「creating an agent is the only step needed」。

- **旧 Agent Application は制約が大きい:** ステートレスな `POST /responses` のみ利用可で、`/conversations`・`/files`・`/vector_stores`・`/containers` にアクセスできない。理由は「プロジェクト内の会話について、エンドユーザー間の分離をまだ強制していない」ため — **会話 ID を知られると他人の履歴にアクセスできてしまう**からで、恒久仕様ではなく修正中と明記されている。マルチユーザーのアプリを旧モデルで組んでいるなら、会話履歴はクライアント側で持つ必要がある。
- **レガシーエージェント(`agent.identity == null`)はインプレース昇格できない。**同じ定義で新規作成し直す。
- 廃止告知と EOS は「Planned / TBD」で日付未定。**日付が出る前に移行計画を立てておくべき項目。**

### 2.1 Assistants API / Agents v1 → Agents v2(Responses API)

```
  [Before]                                  [After]
  App ──> Assistants API                    App ──> Responses API
           ├ Threads      (会話)                     ├ Conversations
           ├ Messages     (発言)                     ├ Conversation Items
           ├ Runs         (実行)                     ├ Responses
           └ Assistants   (定義)                     └ Agents / Agent Versions

  クライアント 1 本                          クライアント 2 本
   (OpenAI SDK beta)                          - OpenAI クライアント(会話・実行)
                                              - プロジェクトクライアント(定義・版管理)
```

**移行の実務ポイント:**
- 公式の移行ツールはコード構造を変換するが、**過去の runs / threads / messages は移行されない**。会話履歴を業務上残す必要があるなら、旧 API から自前ストアへエクスポートする工程を別途設計する。
- 新 API では「会話・実行は OpenAI クライアント、エージェント定義・バージョン管理はプロジェクトクライアント」の 2 クライアント構成になる。DI やラッパーを 1 本の抽象に寄せていた実装ほど改修範囲が広い。
- 旧 `create_agent()` は SDK v2.0.0 で削除済み。

### 2.2 ビジュアル Workflows → コードファースト

移行先は 3 つあり、**「ビジュアルを維持したいか」「Foundry に閉じたいか」で選ぶ**。

| 移行先 | 向く場面 | 得るもの / 失うもの |
|---|---|---|
| **Microsoft Agent Framework**(公式推奨) | 今後もエージェント中心に育てる | エクスポートした YAML を宣言的ワークフローとしてほぼ持ち込める。以後 VS Code で反復。ビジュアル編集は失う(Agent Inspector で可視化は可) |
| **Azure Logic Apps** | ビジュアルデザイナーを業務部門が触る前提を維持したい | デザイナーと 1,400+ コネクタを維持。Foundry エージェントはワークフローの 1 ステップに降りる |
| **A2A エンドポイント** | 正式なワークフローは要らず、エージェント間の軽量な委譲で足りる | 疎結合。ただし v1.0 は JSONRPC・テキストのみ・ストリーミング非対応 |

エクスポートした workflow YAML は **hosted agent としてなら実行を継続できる**ため、いったん hosted agent に載せて時間を稼ぎ、その後 MAF のコードへ寄せる二段構えも取れる。

### 2.3 ハブベース(classic)→ Foundry プロジェクト

- **自動移行ツールはない。**新規プロジェクトを作り、接続を作り直す方式(公式ガイドの想定所要は 5〜10 分だが、これはリソース作成部分の話)。
- 移行対象: モデルデプロイ、データファイル、fine-tuned モデル、vector store(2026-09-26: migrate-project 2026-09-10 版で **Assistants が移行対象リストから削除**。Assistants API 自体が 2026-08-26 に廃止済み)。
- **移行対象外:** プレビュー期の Agent の state、OSS モデルのデプロイ。
- classic に残る機能(prompt flow 等)を使っている場合は、移行ではなく**機能の代替設計**が必要。

### 2.4 Azure OpenAI 単体 → Foundry リソース

kind を `OpenAI` → `AIServices` + `allowProjectManagement: true` に変えるアップグレードが提供されており、**エンドポイント・キー・fine-tune / batch の状態を保持したまま**変換できる(非破壊、ロールバック可)。

- ポータル手順は classic ポータル + Azure ポータル側。新ポータルからの手順は記載なし。
- **CMK 利用リソースは申請フォーム経由のみ。既存 Private Endpoint 付きはポータル経由不可**(削除→再作成 or IaC)。
- Microsoft 側の自動アップグレードプログラムも走っており、`foundryAutoUpgrade` プロパティで状態確認・オプトアウトが可能(SDK の enum は Enabled / Disabled のみで「Deferred」は存在しない。ロールバックは手動アップグレードと同じ別手順)。**顧客に予告なく変わるものではないが、IaC 側で意図しない差分が出る可能性があるため、Terraform/Bicep の drift 検知に入れておく。**

### 2.5 既存システムへの後付け(移行というより組込み)

既存の業務システムに AI を足す案件では、**Foundry をプラットフォームとして採用せず、モデルとツールだけ借りる**構成が現実的なことが多い。

```
  [既存業務システム]                    [Foundry]
   ┌────────────────────┐              ┌──────────────────┐
   │ 既存の認証・認可    │              │ モデルデプロイ    │
   │ 既存の監査ログ      │  Responses   │ ガードレール      │
   │ 既存の業務DB        │ ─── API ───> │ (File Search)     │
   │ ┌────────────────┐ │              │ (Code Interpreter)│
   │ │ AI オーケスト  │ │              └──────────────────┘
   │ │ レーション(自前)│ │
   │ └────────────────┘ │              会話状態・ツール認可・監査は
   └────────────────────┘              すべて既存システム側に残す
```

この構成の利点は、**既存の認可・監査・データ保持ポリシーをそのまま使える**こと。欠点は、Foundry の Tracing / Evaluations / エージェント公開といった運用機能を使えないこと(トレースは自前 OTel 計装で App Insights に寄せれば部分的に取り戻せる)。

## 3. アンチパターン集

### A1. 「ポータルで全部できます」と言ってしまう

ポータル(構成のみ)で本当に完結するのは、**単一 Prompt agent + カタログのツール + 公開**まで。分岐・ループ・リトライ・承認待ちの明示制御、ミドルウェア、ローカルテストは入らない。しかもマルチエージェントのビジュアル構成は 2026-12-01 で消える。

**対処:** 提案時に「ポータル完結の範囲」と「コードが要る範囲」を線引きした表を必ず添える。

### A2. 閉域要件を後から足す

Standard setup(BYO VNet 注入)は**後付け・変更が不可**で、再デプロイが必要。加えて、ネットワーク分離下では Memory・Logic Apps・Browser Automation・Computer Use・Image Generation・Fabric Data Agent 等が使えず、Tracing VNet と Workflow Agents の outbound は未対応 / プレビュー。File Search は公式表記が「対応」に変わったが Blob Storage のファイル連携は非対応、Work IQ は data proxy 経由で呼べるが宛先は公開エンドポイント(→ [07 章 §3](./07-usecase-regulated-edge.md#3-閉域で使えない機能の一覧-設計の出発点))。

**対処:** ネットワーク要件はアーキテクチャ検討の最初のゲートに置く。「閉域で使える機能一覧」から設計を始める。

### A3. File Search で品質が出ないまま押し切る

File Search は埋め込みモデル(text-embedding-3-large / 256 次元)もチャンク設定(800 / オーバーラップ 400)も固定。日本語の長文契約書・表主体の技術文書では、この設定が合わないことがある。

**対処:** PoC 段階で**代表的な難しい文書 20〜30 件**で検索品質を測り、駄目なら早期に AI Search 自前索引へ切り替える。切り替えコストは後になるほど上がる。

### A4. Claude を選んだのにガードレール設計を変えない

Claude は Foundry の組み込みコンテンツフィルターが**適用されない**。Anthropic 自身の安全システムに依存する形になり、Foundry の Guardrails 画面で設定しても効かない。

**対処:** Claude 採用時は Content Safety API をアプリ側で呼ぶ設計を最初から入れる。あるいはモデル選定をやり直す。

### A5. Web search / Grounding with Bing を規制業種で使う

いずれも **DPA 対象外で、データがコンプライアンス境界の外に出る**と明記されている。

**対処:** 規制業種では原則不可として扱い、必要なら社内キュレーション済みの外部情報を AI Search に取り込む方式に置き換える。

### A6. プレビュー機能を本番の必須経路に置く

Memory、Monitoring ダッシュボード、エージェント向けガードレールの Tool call / Tool response 介入、**A2A の v0.3(既定バージョン。v1.0 は GA)**、Routines の reminder ツール、hosted agent の network egress controls、Voice Live のエージェント連携(GA 一覧表上)、Foundry IQ のポータル体験はいずれもプレビュー。プレビューは SLA がなく仕様変更もあり得る。**2026-09-26 注:** 前版でプレビューに挙げていた **Routines は GA**(GA 一覧表 2026-09-23 更新+devblogs 2026-09-24)、**A2A は v1.0 が GA**(enable-agent-to-agent-endpoint 2026-09-11 版。Azure Blog 2026-09-24「Ship agents faster…」も A2A・Routines・Tool search の GA を告知)に変化。一方、同ブログで **Voice agents(prompt / hosted の新エージェント種別)・長時間実行 hosted agents・Foundry insights・prompt agent への Toolbox 拡大はパブリックプレビュー**、Rubric / trace→dataset 生成 / Agent optimizer は「今月後半 GA 予定」(2026-09-26 時点のドキュメントはプレビュー表記)。ただし A2A はバージョン未指定時の既定が preview の v0.3 なので、本番は `A2A-Version: 1.0` を明示する。

**対処:** Azure Policy の「Foundry model deployments must meet eligibility requirements」(`denyPreviewModels`)や、タグ `AZML_DISABLE_PREVIEW_FEATURE=true` でプレビューを組織的に抑止できる。本番サブスクリプションには入れておく。

### A7. クォータをアプリ設計で無視する

Foundry のクォータはデプロイ単位。複数部門・複数アプリが 1 デプロイを共有すると、1 つの暴走が全体を止める。

**対処:** 部門・アプリ別にデプロイを分けるか、APIM のトークンレート制限で切る。429 のリトライ/バックオフはアプリ側の必須実装。

### A8. 会話状態を Foundry に預けたまま法定保存要件を受ける

basic セットアップの会話は Microsoft 管理ストレージにあり、所在と保持をこちらで細かく制御できない。しかも basic → standard の切替はセットアップのやり直し。

**対処:** 保存・削除・開示の要件が見えている案件は、最初から standard(BYO Cosmos DB)か自前セッションストアを選ぶ。

### A9. `az` CLI で自動化できる前提で見積もる

**専用の `az foundry` コマンド群は存在しない**(Azure CLI リファレンスの `cli/azure/foundry` は 404。2026-09-26 確認)。リソース管理は `az cognitiveservices`(GA)、エージェント開発は azd 拡張 `azure.ai.agents`(プレビュー。7・8 月号ブログの基準は azd 1.32.0+ / 拡張 1.0.0-beta.13)、それ以外の多くは「ポータル + SDK/REST のみ」でドキュメントに CLI 手順がない。2026-09 公開の Foundry Dev Pack(0.1.3、プレビュー。winget / brew / curl)は az・azd・Foundry 用 azd 拡張・Foundry Skill を一括導入するインストーラーで、CLI の機能範囲自体は変えない。

**対処:** 自動化は Bicep/Terraform(基盤)+ SDK/REST(データプレーン)前提で工数を積む。

### A10. RBAC ロール名をスクリプトに直書きする

ロール名が旧名(Azure AI User 等)から Foundry User 等へ改名ロールアウト中。ID と権限は不変。

**対処:** IaC / スクリプトではロール ID(GUID)を指定する(公式推奨)。

### A11. ドキュメントのステータス表記を 1 ページだけ見て判断する

hosted agents(GA と preview の混在表記)、Trace Replay、Voice Live のエージェント連携(GA 一覧表 = Preview / devblogs 7・8 月号 = 「Hosted Agents with Voice Live は GA」)、Claude のライフサイクルなど、**公式ページ間でステータスが食い違っている**箇所が複数ある(Toolbox は GA 一覧表・7・8 月号ブログとも GA で揺れは解消。2026-09-26 確認)。さらに**リタイア表の日付自体が版ごとに前後する**(例: gpt-4.1-nano は features 第3版が記録した 2026-09-02 版で 2027-04-14、2026-09-21 版で 2026-10-14)。

**2026-10-06 の例:** `azure-ai-projects` 2.8.0 の changelog は Agent Optimization API を「GA」とするが GA 一覧表は Agent optimizer = Limited preview。Browser Automation もページは「(preview)」のまま 2.8.0 で「GA ツール型」が追加。hosted agent のトラフィック分割は本番昇格ページ(preview)が 90/10 のカナリアを示し、manage-hosted-agent・configure-agent は「分割不可」。既存セッションの休止明けの版は、公式と MAF ホスティングの実測(Port 11)が「作成時の版」、Agent Server SDK だけの最小エージェントの実測(probe 10)が「現行セレクタの版」で、同じ日に構成によって割れた。

**2026-10-14 の例:** `gpt-4.1-nano` のリタイア日が 2027-04-14 → 2026-10-14 → 2027-04-14 と 3 度目の往復をした(期限当日に元へ戻った)。Agent optimizer・Rubric 評価器・traces→dataset・合成データセット・会話評価 / シミュレーションは **Learn の機能ページから「(preview)」が外れたが、GA の明記はなく GA 一覧表(updated_at 2026-09-23)は Preview / Limited preview のまま**(SDK 2.8.0 は GA)の 3 者割れ。Browser Automation もツールページ本文が「generally available」と書く一方、移行ガイドの表・TOC は preview、閉域は Not supported のまま。hosted agent の idle timeout 上限は REST 仕様・azd = 240 分 / Learn = 60 分。capability settings の設定ページは 301 で記述のないページへ転送され、他ページは旧 URL を参照したまま。

**対処:** [Feature readiness at GA](https://learn.microsoft.com/en-us/azure/foundry/concepts/general-availability) を一次情報とし、モデルのリタイア日は [Model retirement schedule](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule) 側を採用する。SDK の changelog の「GA」は SLA の根拠にしない。挙動に関する食い違いは実測を受入条件に入れる。

### A12. 閉域で hosted agent を VNet 注入なしで作る

hosted agent の VNet 注入は **Foundry アカウントの作成時にしか入れられず、既存アカウントへの後付けは非対応**([virtual-networks](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/virtual-networks) の Limitations)。一方で、閉域のツール対応表は公式テンプレート(15 / 11)で作った構成が対象と明記され([configure-private-link](https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-private-link))、AI Search ツールのページも「VNet 注入なしのエージェントは private endpoint 付きの Search に接続できないことがある」と書く([04 章 A3](./04-usecase-chat-rag.md#a3-既存-ai-search-資産の活用-ai-search-ツール直結))。インバウンド遮断(PE)だけで作ってから注入が要ると分かると、アカウントの作り直しになる。

**対処:** 閉域で hosted agent を使うなら、最初から VNet 注入つきで Foundry アカウントを作る。

### A13. project → App Insights 接続なしで hosted agent を運用する

接続がないとプラットフォームは接続文字列(`APPLICATIONINSIGHTS_CONNECTION_STRING`)を注入せず([probe 10](../../../labs/foundry-probes/probes/10-hosted-version-continuity/NOTES.md) で確認)、自前の送信設定もなければコンテナ内部ログがどこにも届かない。障害時に「無応答の原因が分からない」状態になる([casebook P-H02](../casebook/02-pitfalls-index.md#a-hosted-agent))。

**対処:** Bicep に `connections/appinsights` を含め、「テレメトリ 0 件でも失敗扱い」のスモークテストをデプロイ直後に置く。**ただし接続するとプラットフォーム側トレースに会話の中身が入る**ので、中身の扱い(集約 / 分離 / 接続しない / 保護テーブル)を先に決める([09 §3.6](./09-operations.md#3-6-トレースに会話の中身を残すか-hosted-agent-の選定基準))。

### A14. プロンプトの正本をポータル(管理画面)と Git で二重化する

ポータル編集は評価ゲートを通らず、Git からの次のデプロイで上書きされ、Git と乖離して退行の原因になる。

**対処:** 正本は Git、Foundry へは一方向デプロイ。ポータル編集を開放するなら評価ゲート付きの反映経路を作ってから。

### A16. 本番エージェントを「latest 追従」のまま CI でデプロイしてからテストする

hosted agent のエンドポイントは既定で最新版を追う。「`azd deploy` → スモークテスト」のパイプラインは、**テストより先に本番の版が変わる**(公式が set-up-ci-cd-cli 2026-09-23 版で明記)。さらに `azd deploy` は構成済みのエンドポイント設定を適用するため、ピン留めしたつもりでも上書きされうる。Terraform の state lock は別の書き手(ポータル・SDK・別パイプライン)による版作成を止めない。

**対処:** 公式の 6 段階(production を具体版に `FixedRatio` 100% でピン留め → 候補作成 → `active` とイメージ一致の確認 → `version_ref` の候補専用セッションで内容まで検証 → 昇格直前に再確認して昇格 → 版指定なしの新しいセッションで確認)をパイプラインの形にし、エージェントの書き手を 1 つに絞る([09 §6.3](./09-operations.md#6-3-エージェントのバージョニングとリリース))。「ログが出た」「接続できた」を合格条件にしない。

### A17. `AppGenAIContent` を Protected にしただけで「トレースの本文は隠せた」と判断する

公式は移行日 2026-09-30 以降、会話本文が専用テーブル `AppGenAIContent` だけに入るとするが、**2026-10-06 の japaneast 実測(feature flag 未登録)では従来テーブル `AppDependencies` の `gen_ai.*` 属性と二重書き**で、従来テーブルの本文は通常の Log Analytics Reader で読めた。また振り分け対象は 7 属性だけで、コンテナがログ本文・例外・独自属性に書いた中身は対象外。

**対処:** 「フラグ登録または移行完了」「`AppGenAIContent` の Protected 化」「Privileged Monitoring Data Reader の限定付与」「`gen_ai.*` 以外に本文を書く計装〈MAF のメッセージイベント・自前ログ〉の停止」の 4 点をそろえ、**従来テーブルに本文が残っていないことを KQL で確認**(`AppDependencies | where isnotempty(Properties['gen_ai.input.messages']) | count` が 0、`AppTraces` も同様)してから運用に入る。**公式の確認手順だけでは足りない(2026-10-14 補強):** traces-sensitive-content(en 2026-10-06 版・ja 10-12 版)の検証手順は「Log Analytics Reader だけの利用者には本文が見えず、Privileged Monitoring Data Reader の保持者には見える」ことの確認だけで、**従来テーブルに本文が残っていないかは確認対象に含まれない** — 公式手順どおりに合格しても二重書きの本文は残りうるので、KQL の確認を受入試験に別項目で入れる。コンテナ側のマスクは続ける([09 §3.6](./09-operations.md#3-6-トレースに会話の中身を残すか-hosted-agent-の選定基準))。
