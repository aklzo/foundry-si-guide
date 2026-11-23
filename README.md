# foundry-si-guide

個人で進めている Microsoft Foundry(旧 Azure AI Foundry)のキャッチアップと、SI 案件における **AI エージェント関連の技術選定・アーキテクチャ選定基準の構築**を目的としたリポジトリ。

「Foundry ポータルで足りるのか / Microsoft Agent Framework (MAF) などのコード実装が必要か / LangGraph 等の他フレームワークを選ぶべきか / そもそも Foundry に乗せるべきか」を根拠を持って判断できる状態をゴールとする。

## 構成

| パス | 内容 |
| --- | --- |
| [docs/learning-plan.md](docs/learning-plan.md) | キャッチアップ計画書(技術選定判断力の獲得を主目的に構成) |
| [docs/survey/](docs/survey/README.md) | 調査ドキュメント群(下記) |
| [docs/survey/features/](docs/survey/features/README.md) | **機能一覧・ステータス調査** — GA / プレビューをサーフェス別(ポータル / CLI / SDK)に整理。出典 URL 付き。月次更新 |
| [docs/survey/architecture/](docs/survey/architecture/README.md) | **アーキテクチャ設計ガイド** — 公式リファレンス、レイヤー別の「Foundry 機能 vs 自前実装」、ユースケース別構成、運用・移行。四半期更新 |
| [docs/survey/proposal/](docs/survey/proposal/README.md) | **提案実務ガイド** — 要件ヒアリングシート、コスト見積もり手順、日本規制対応メモ、前提 Azure 知識マップ |
| [docs/survey/casebook/](docs/survey/casebook/README.md) | **SI ケースブック** — 要件シナリオ別プレイブック(10 本)、詰まりどころ索引(公式 / 実測 / 公開記事の 3 出典、約 260 項目、URL 実在確認済み)。「この要件が来たら何を決め、どこで詰まるか」を引く。02 は月次更新 |
| [docs/events/](docs/events/README.md) | **イベント変更まとめ** — Ignite・Build ごとに Foundry / Copilot Studio の変更を図中心にまとめた資料(製品の画面は Microsoft Learn の掲載ページへのリンク)。詳細版 HTML(原本は Markdown)と Foundry に絞った約 10 枚の PPTX。第 1 弾は Ignite 2026(2026-11-22 時点。閉域・権限・外向き通信は probe 12〜15 の実測つき) |
| [docs/tech-selection-guide.md](docs/tech-selection-guide.md) | **技術選定ガイド(実装検証ベース)** — labs の実装で実証したナレッジのみを集約(調査由来の survey とは出典分離) |
| [labs/agentic-search-maf/](labs/agentic-search-maf/README.md) | 検証ラボ: 自己評価型リサーチエージェントを MAF で実装した学習用プロジェクト |
| [labs/runbooks.md](labs/runbooks.md) | **ラボ実行ガイド索引** — 全ラボ・全ポートの実行手順と確認観点(Markdown が正、人間用 HTML `labs/runbooks.html` はチェックボックスで確認状況を記録できる)。`python3 labs/tools/build_runbooks.py` で生成 |
| [labs/maf-ports/](labs/maf-ports/README.md) | 検証ラボ: awesome-llm-apps の 14 パターンを MAF+Foundry へ移植+新規パターン 1(委任アクセス)。**2026-10-06 に agent-framework 1.20 / openai 3.24 で再検証(オフライン 829 件・Port 15 以外はライブも再実施)**。Azure リソースは検証後削除済み |
| [labs/foundry-probes/](labs/foundry-probes/README.md) | 検証ラボ: maf-ports に乗らなかった Foundry 機能 15 本の挙動確認 probe(10 = hosted agent の版更新と会話の継続、11 = トレース本文の保護テーブル振り分け、12〜15 = 閉域・権限の境界・Agent Optimizer・外向き通信の経路。01〜11 は 2026-10-06、12〜15 は 2026-11-22 にライブ。リソース削除済み) |
| [labs/cu-video-rag/](labs/cu-video-rag/README.md) | 検証ラボ: Content Understanding video × AI Search × RAG の精度検証(104 本・111 問+ragas。ラウンド 3〈評価設計是正後〉で CER 0.44% / カスタムフィールドで hit@3 0.937・画面のみ情報の ans@3 0.672。PDF レポート同梱。2026-10-06 に 4 本のスモークで最新依存のライブ確認。リソース削除済み) |

## 調査ドキュメントの読み方・更新

- **Markdown が正**(生成 AI 用)。人間用 HTML は各ディレクトリの `html/` 配下に自動生成される。HTML は直接編集しない。

```bash
# HTML の再生成(features / architecture / proposal / casebook の全セット)
python3 docs/survey/tools/md2html.py

# ラボ実行ガイド(labs/**/docs/runbook.md → runbook.html と索引)の再生成 / 同期確認
python3 labs/tools/build_runbooks.py
python3 labs/tools/build_runbooks.py --check

# アーキ図の再生成(survey 用+全幅の切り出し。日本語フォントは自動検出)
for f in docs/survey/architecture/diagrams/*.py; do uv run --with diagrams,pillow python "$f"; done
```

- 更新手順・ウォッチすべき一次情報(What's new / Feature readiness at GA / model retirement schedule)は [docs/survey/features/README.md](docs/survey/features/README.md) の「更新運用ガイド」を参照。

## メモ

- 2025 年 11 月(Ignite)に Azure AI Foundry から **Microsoft Foundry** へ改称。公式ドキュメントは `/azure/foundry/`(新)と `/azure/foundry-classic/`(ハブベース)に分割されている。
- 2026 年 11 月(Ignite 2026)は「継続改善」を軸に GA 化と新プレビューが大量に出た(voice agents・hosted の egress / long-running・外部エージェント・Insights・managed compute の GA、Microsoft Copilot harness・Cost in Foundry 等のプレビュー、Azure AI Search の Foundry IQ (Azure AI Search) への改称)。ブログの GA と GA 一覧表の Preview が食い違うものが多く、features では GA 一覧表を正に両論併記している(2026-11-22 更新)。
- ステータスは推測で書かず、公式ページで確認できないものは「要確認」+確認 URL を記録する方針。

## 免責・ライセンス

- 本リポジトリは個人の学習・調査の記録であり、所属組織の見解・方針を示すものではない。記載内容は各記載日時点の調査・実測に基づき、正確性・最新性は保証しない。採用判断の前に必ず一次情報(Microsoft Learn 等)を確認すること。
- 本リポジトリにはライセンスを付与していない(自作部分は著作権者がすべての権利を保有する)。第三者由来の内容(awesome-llm-apps からの移植コード〈Apache License 2.0〉、Microsoft Learn の要約・翻訳ほか)の出典とライセンスは [NOTICE.md](NOTICE.md) を参照。
