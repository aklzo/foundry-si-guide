# Foundry 提案実務ガイド

> **最終更新:** 2026-07-31 / 2026-09-26(全 5 本を一次情報で再確認)/ 2026-09-29(02 / 03 に features 差分更新を波及)/ 2026-09-30(01 に 4-7 を追加)/ 2026-10-06(2026-09-29 以降の差分を全 5 本に反映)/ **版:** 初版 / 2026-10-14(2026-10-06 以降の差分を 01〜04 に反映、05 は差分確認のみ)
> [features(機能ステータス)](../features/README.md) が「その機能は使えるのか」、[architecture(設計ガイド)](../architecture/README.md) が「どう組むか」に答えるのに対し、本セットは **SI の提案活動そのもの**(ヒアリング → 構成決定 → 見積もり → リスク説明)を支援する実務ドキュメント群。

## ドキュメント構成

| # | ドキュメント | 用途 | 使うタイミング |
| --- | --- | --- | --- |
| 01 | [要件ヒアリングシート](./01-hearing-sheet.md) | 業務側の言葉から構成候補に落とすための質問リストと分岐 | 初回〜2回目の顧客ヒアリング |
| 02 | [コスト見積もり手順](./02-cost-estimation.md) | トークン量の推計 → 単価取得 → 月額試算 → PTU 判断の手順書(単価は書かない主義) | 概算提示・提案書作成 |
| 03 | [日本規制対応メモ](./03-japan-compliance.md) | ISMAP / FISC / 個情法 / 医療等と Foundry 構成の対応整理 | 規制業種の案件開始時 |
| 04 | [前提 Azure 知識マップ](./04-azure-knowledge-map.md) | 提案・設計に必要な Azure 基礎知識のサブセットと学習リンク | チームメンバーのオンボーディング |
| 05 | [公開事例集](./05-case-studies.md) | 提案書で引用できる Microsoft 公式事例(日本エージェント型・生成 AI・グローバル) | 提案書の類似事例欄・プリセールス |

## 使い方(提案フローとの対応)

1. **ヒアリング**: [01](./01-hearing-sheet.md) の質問リストで要件を採取 → 構成候補(architecture のユースケース型)を 1〜2 案に絞る → 最も近い要件シナリオを [casebook 01](../casebook/01-scenario-playbook.md) で照合し、詰まりどころ(P-ID)を [casebook 02](../casebook/02-pitfalls-index.md) から抽出
2. **実現可否チェック**: 候補構成で使う機能を [features](../features/README.md) で GA / プレビュー確認 → プレビュー依存と廃止日程をリスク一覧化
3. **概算**: [02](./02-cost-estimation.md) の手順で月額レンジを試算
4. **リスク・規制説明**: [03](./03-japan-compliance.md) で顧客説明の論点を準備
5. **体制**: [04](./04-azure-knowledge-map.md) でチームの知識ギャップを確認

## 更新方針

- 本セットは features(月次)ほど頻繁な更新は不要。**単価・規制・ISMAP 登録状況は「案件ごとに最新を確認する」設計**にしてあり、ドキュメント側には手順と参照先のみを持たせている。
- features / architecture の大型更新(Ignite・Build 後)の際に、分岐条件・チェックリストへの波及を確認する。

## 更新履歴

| 日付 | 内容 |
| --- | --- |
| 2026-07-31 | 初版作成(4ドキュメント) |
| 2026-09-04 | casebook セット(要件シナリオ別プレイブック / 詰まりどころ索引)への導線を 01 の 4-1・クイックマップ末尾・アウトプット 6 と本ページの使い方に追加 |
| 2026-09-30 | 01 に 4-7「会話の中身を運用ログに残してよいか・誰が読めるか」を追加(Port 15 のライブ検証で、hosted agent のプラットフォーム側トレースが会話の中身を記録すると判明したため。判断基準は architecture 09 §3.6) |
| 2026-08-02 | **05 公開事例集を追加。**Foundry / Agent Service 名指しの日本事例(富士通・NTT データ・Sky)とエージェント型(Azure OpenAI 名義)・生成 AI 事例・グローバル事例を公式出典つきで収録。四半期更新の巡回先を明記 |
| 2026-09-26 | **全 5 本を一次情報で再確認**。01: Routines GA(2026-09-24)反映・hosted agent 同時セッション上限を 2 段(サブスクリプション×リージョン既定 2,000 / 1,000 + サブネット IP)に訂正・トラフィック分割は prompt / hosted とも非対応に訂正・閉域ツール表(File Search の公式表記変化)・Data Zone APAC の定義・Assistants 廃止済み。02: 課金単位を追記(hosted agent vCPU / GiB 時間・Foundry IQ Serverless 2026-09-13 課金開始・Voice Live・CU 3 層・Routines)、Data Zone / Regional 価格プレミアム(2026-09-01)、flex フォールバック廃止、Model router の制約更新、モデル単価 URL 差し替え。03: 国内処理 = geography 型(Japan East / West)、令和 8 年改正個情法・AI 法関連(AI 事業者ガイドライン 第 1.2 版)、DS-920、ISMAP の learn 掲載ページ、Work IQ の境界外処理、トレース VNet の現行表記。04: AI-102 退役 → AI-103、capability settings 移行中の注記。05: 日本の Foundry 事例 3 件追加・巡回先 URL 更新 |
| 2026-09-29 | features 差分更新の波及。**02:** Flex 処理の行を専用ページ(preview・Standard 比 50% 割引・当初 gpt-5.6-sol のみ・SLA なし・429 非課金)で更新し「専用ページが見当たらず要確認」を解消 / **03:** §2 のパートナーモデル行に Fireworks on Foundry のデータ処理場所(Microsoft 施設外の Fireworks GPU・現在 US のみ・SOC 1 Type 2 非準拠)と claude-sonnet-5-5 を追記 |
| 2026-10-06 | 2026-09-29〜10-06 の差分更新。**01:** 4-7 に第 4 の選択肢(本文だけを保護テーブル `AppGenAIContent` に隔離。フラグ登録か移行完了・Protected 化・Privileged Monitoring Data Reader の 3 点がそろって成立し、2026-10-06 の japaneast 実測は従来テーブルとの二重書き → KQL での残存確認を見積もりに)と Agent 365 への活動データ送信(テナントのジオ・`a365LoggingEnabled`)、新設 4-8(利用者委任 = toolbox 経由かアプリ管理 OBO か)・6-5(本番リリースの承認とピン留め・Terraform 指定)、1-3 に版間カナリアの公式間の食い違い、0-2(remote SharePoint の従量課金もテナントに Copilot ライセンス 1 つ以上)・5-3(Browser Automation のステータス両論)・7-3(直近の期限)、クイックマップに音声行。**02:** GPT-6 系 PTU の normalized token(キャッシュ入力も容量を消費)の式、評価のジャッジ費用の式と合成評価器(preview)、Routines の再試行 5 回の上振れ、Agent 365・voice agents / GPT-Live(WebRTC 最低 15 秒)の行、Fireworks の別クォータプール・適応レート制限・PTU 既定値の改訂、priority の `service_tier` 確認。単価は書いていない。**03:** §0 に観測データの層、§2 に Agent 365 のデータ所在(Entra テナントのジオ)、§3 に運用ログの個人データと保護テーブル(実測の二重書きと両論)、§7 の回答の型。Fireworks の FAQ は再確認して変更なし。**04:** 保護テーブルと Privileged Monitoring Data Reader、利用者委任の 2 方式、Terraform での hosted agent 管理。**05:** 期間内の新規公開なし(2026-10-06 確認)、前回未収録の JBS(2026-09-11)を追加 |
| 2026-10-06(ラボ還元) | ラボの 2026-10-06 最新化+ライブ検証の還元。**01:** 4-7 の保護テーブル案の成立条件を 4 点に(4 点目 = `gen_ai.*` 以外に本文を書く計装を止める)、KQL の確認期間(既定 1 時間)。**02:** AI Search Free で Foundry IQ の小規模 PoC が積めること(Japan East の脚注・Free の制約)、既定サンプラーと取り込み量、CU の usage のキャッシュ入力費目。**03:** §3 の成立条件を 4 点に。**04:** 保護テーブルの振り分け対象と既定サンプラー |
| 2026-10-10 | Copilot Studio との比較の材料を追加。**02:** Step 6(Copilot Credits のイベント別レート、M365 Copilot 利用者の B2E 無課金、GitHub Copilot harness の換算率非公開、比較の式、構造上の傾向)と Step 3 の取得先。**03:** §2 に Copilot Studio を入口にする構成のデータ所在を追加 — 日本の環境の生成 AI の推論場所は Power Platform(United States)と Copilot Studio のモデル表(既定モデルに cross-geo 表記なし)で食い違うため両論を併記し、§7 の回答の型に反映 |
| 2026-10-14 | 2026-10-06〜10-14 の features 差分更新の波及。**01:** 7-3 の期限(On Your Data は本日が廃止日・gpt-4.1-nano は 2027-04-14 に再延長・Grok の最低 6 か月・Fireworks の表外の期限・TTS アバターの 2026-12)、4-8 に委任された利用者どうしは隔てられないこと、5-1 に M365 公開の共有データアクセスの従量課金とゲスト不可、5-3 に Browser Automation のページ本文の GA 表明(移行表・TOC は preview の両論、閉域は非対応のまま)、クイックマップの音声行(Voice Live の処理スコープ・テレフォニーの voice agents 誘導)。**02:** Flex processing の対象 7 モデル、Model router の既定プールに Fireworks、Bing 系ツールではプロンプトキャッシュが効かない、評価サービス側のキャッシュ・TOON(Tech Community)、voice agents の料金ページと推定コスト属性、M365 公開の従量課金、idle timeout 上限の両論、Grok の最低 6 か月を再見積もり条項に。単価は書いていない。**03:** §2 に Voice Live の処理スコープ・新モデル(Grok 4.7 / Claude Haiku 5.5 / Microsoft-Decision-1)の日本リージョン・Model router の Fireworks・Prompt Optimizer の Japan West のみ・ファインチューニングの新方式の所在、§6 に AI 生成コンテンツの来歴(透明性規制、義務の履行は顧客責任)。**04:** capability settings ページの 301、AI Search の DNS ラベル。**05:** 差分確認のみ(追加なし) |
| 2026-10-10(ヒアリング) | **01:** Phase 0.5「どこで作るか — Copilot Studio / Foundry / 既存システムへの組み込み」を追加(5 問: 利用者が社員か社外か・チャットを使うか / 月間件数と 1 件あたりの処理 / システム改修か業務部門が育てるか / M365 Copilot の保有割合 / 閉域・国内処理の明文化)。判定のしかた(全部 Copilot Studio 側なら Foundry は提案しない・Foundry にする理由を要件の文で書けるか)、Copilot Studio の案件の中で Foundry 候補を記録する使い方、クイックマップ 3 行、アウトプット 0 を追加 |
