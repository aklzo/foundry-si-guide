# NOTICE — 第三者由来の内容

本リポジトリの自作部分にはライセンスを付与していない(著作権者がすべての権利を保有する)。以下の第三者由来の内容は、それぞれの原ライセンスに従う。

## 1. awesome-llm-apps(Apache License 2.0)

- 出典: <https://github.com/Shubhamsaboo/awesome-llm-apps>(参照時点のコミット `e46d6fe`、2026-07-23)
- ライセンス: Apache License, Version 2.0。全文は [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt)。上流に NOTICE ファイルはない。
- 対象: `labs/maf-ports/ports/` の次の 14 ポート。上流のエージェント構成を Microsoft Agent Framework(MAF)+ Microsoft Foundry 向けに書き換えたもの。各ポートの README に上流ディレクトリへのリンクと変更点がある。

| ポート | 上流ディレクトリ |
| --- | --- |
| trend-analysis | `starter_ai_agents/ai_startup_trend_analysis_agent` |
| mixture-of-agents | `starter_ai_agents/mixture_of_agents` |
| research-handoff | `starter_ai_agents/openai_research_agent` |
| corrective-rag | `rag_tutorials/corrective_rag` |
| travel-memory | `advanced_llm_apps/llm_apps_with_memory_tutorials/ai_travel_agent_memory` |
| github-mcp | `mcp_ai_agents/github_mcp_agent` |
| game-design-team | `advanced_ai_agents/multi_agent_apps/agent_teams/ai_game_design_agent_team` |
| data-analysis-ci | `starter_ai_agents/ai_data_analysis_agent` |
| critique-loop | `advanced_llm_apps/gpt_oss_critique_improvement_loop` |
| db-routing-iq | `rag_tutorials/rag_database_routing` |
| hn-briefing-hosted | `always_on_agents/always_on_hn_briefing_agent` |
| claim-voice-live | `voice_ai_agents/insurance_claim_live_agent_team` |
| services-agency | `advanced_ai_agents/multi_agent_apps/agent_teams/ai_services_agency` |
| governed-agent | `advanced_ai_agents/single_agent_apps/ai_agent_governance` |

- 上流のコード・プロンプト・サンプルデータを多く残しているファイル(変更内容は各ファイル冒頭の docstring に記載):
  - `claim-voice-live`: `src/claim_voice_live_maf/policies.py`、`schemas.py`、`agents.py` のエージェント指示文、`tests/data/` と `tests/eval_dataset.jsonl`(上流のサンプルから作成)
  - `services-agency`: `src/services_agency_maf/roles.py` の役割プロンプト
  - `github-mcp` / `hn-briefing-hosted` / `critique-loop` / `governed-agent`: エージェント指示文の一部
- `delegated-access-hosted`(Port 15)は上流を持たない新規パターン。

## 2. Microsoft Learn ドキュメント

- `docs/survey/` 以下の調査ドキュメント(features / architecture / proposal / casebook)、`docs/events/` のイベント変更まとめ、`docs/tech-selection-guide.md`、`labs/maf-ports/ports/corrective-rag/data/` の学習用要約は、Microsoft Learn の公開ドキュメントを要約・翻訳・再構成した内容と短い引用を含む。
- 原典: Microsoft Learn(© Microsoft)。Learn のドキュメントの一部は GitHub の公開リポジトリ(例: `MicrosoftDocs/azure-docs`)で Creative Commons Attribution 4.0 International(<https://creativecommons.org/licenses/by/4.0/>)として提供されている。Microsoft Foundry(`MicrosoftDocs/azure-ai-docs`)と Copilot Studio のドキュメントの公開リポジトリは、2026-11-23 時点で確認できない。
- 製品の画面画像は転載しない。`docs/events/` では掲載ページへのリンクで示す。
- 変更: 日本語への翻訳・要約、複数ページの統合、本リポジトリ独自の判断・注記の追加。各記述の出典ページは本文中の URL またはページ名と確認日で示す。本リポジトリの記述は Microsoft による確認・承認を受けたものではない。

## 3. Azure アーキテクチャアイコン

- `docs/survey/architecture/images/`、`labs/maf-ports/ports/*/docs/architecture.png` などの構成図は、Python パッケージ [diagrams](https://github.com/mingrammer/diagrams) に同梱の Azure アイコンを使って生成している。
- アイコンは Microsoft の Azure アーキテクチャアイコンの利用条件(アーキテクチャ図・ドキュメントでの使用を許諾)に従って使用している。アイコンの権利は Microsoft に帰属する。

## 4. 公開記事・ブログからの引用

- `docs/survey/casebook/02-pitfalls-index.md` ほかには、公開記事(技術ブログ・Qiita・Zenn 等)からの短い引用と要約がある。各箇所にサイト名・年月・URL を出典として示している。引用部分の権利は各著者に帰属する。

## 5. 商標

- Microsoft、Azure、Microsoft Foundry、Copilot ほかの製品名は各社の商標または登録商標である。
