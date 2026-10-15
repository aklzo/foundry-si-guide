# 継続評価(evaluation_rules)— 挙動発見メモ(2026-08-04 実測)

環境: gpt-5.4-mini / japaneast / azure-ai-projects 2.4.0
critique-loop はバッチ評価(その場でランを作る)を検証済み。ここはイベント駆動の自動評価。

## 発見(挙動)

- **継続評価ルールは prompt agent スコープ必須**。filter なしで作ると:
  `(UserError) Filter.AgentName is required and cannot be empty.`(target: filter.agentName)
  → survey には無い制約。**生の `responses.create` には掛けられない**。`EvaluationRuleFilter(agent_name=...)` で対象エージェントを指定し、その agent 経由の応答だけが評価対象になる。
- 配線自体は SDK で完結: `client.evals.create`(builtin.coherence)→ `project.evaluation_rules.create_or_update(id, EvaluationRule(event_type=RESPONSE_COMPLETED, filter=EvaluationRuleFilter(agent_name=...), action=ContinuousEvaluationRuleAction(eval_id, max_hourly_runs, sampling_rate)))`。
- 作成したルールは `list` に現れる(action.type=`continuousEvaluation`、enabled=True)。ただし **list の戻りで `event_type` が None**(create の戻りには入るのに list では欠ける)= SDK/サービスの表現揺れ。
- `systemData.createdAt` は `MM/DD/YYYY hh:mm:ss` 文字列(ISO ではない)。

## つまりどころ

- **自動評価ランは `client.evals.runs.list(eval_id)` では観測できなかった**(agent 経由の応答 3 件生成後 120 秒ポーリングして 0 件)。継続評価の結果は evals のラン一覧ではなく **Monitor ダッシュボード / App Insights 側に集計される**設計と推測(survey 05:「Monitoring 領域はプレビュー」)。バッチ評価(critique-loop)とは結果の見え先が違う。
- したがって「継続評価を SDK だけで結果取得してアサートする」CI 的な使い方は現状しにくい。設定は SDK、結果確認はポータル、という分業になる。
- `max_hourly_runs`(既定上限 100/時)があるので、高トラフィックの agent では全応答は評価されない(サンプリング)。`sampling_rate=1.0` でも hourly 上限が効く。

## SI 判断メモ

- 継続評価は「prompt agent を本番運用し、その品質を継続監視する」シナリオ専用。maf-ports のようなクライアント側(MAF)オーケストレーションの応答には掛けられないので、**継続評価を要件にするなら agent を prompt agent(サービス側)で建てる**という構成上の縛りが先に来る。
- PoC の品質確認はバッチ評価(critique-loop の evals API 直叩き)で十分。継続評価は「本番監視」フェーズの機能、と割り切る。

## 2026-09-29 追記(最新化チェック・ライブ未検証)

- **上の「自動ランは evals.runs.list で観測できない」は probe 側の設定不備だった可能性が高い。** 公式の継続評価手順(how-to-monitor-agents-dashboard 2026-09-03 版)と SDK サンプル `sample_continuous_evaluation_rule.py` は、eval を `data_source_config={"type": "azure_ai_source", "scenario": "responses"}`(data_mapping なし)で作り、ランは `openai_client.evals.runs.list(eval_id, order="desc")` に `continuousevalrun_*` として現れて `report_url` を持つ、としている。2026-08-04 の probe は critique-loop(バッチ評価)と同じ `custom` + `item_schema` + `data_mapping` で eval を作っていた。
- もう 1 つの前提「**プロジェクト MI に Foundry User(旧 Azure AI User)**」は roles.bicep で付与済みだったので、差分はデータソースの形のみ。App Insights 接続も main.bicep で作成済み。
- probe を公式の形に修正し、ポーリングを 300 秒に延長・`report_url` を表示するようにした。**再デプロイして再実測するまで、上の「つまりどころ」1〜2 点目は未確定として扱う。**
- 変わらない点: ルールの `filter.agent_name` 必須(公式サンプルも `EvaluationRuleFilter(agent_name=...)`)、既定 100 回/時の上限(公式トラブルシューティング表にも記載)、継続評価は Monitoring 領域ごとプレビュー。
- SDK 2.7.0 では `allow_preview=True` を付けると `evaluation_rules.create_or_update` に `Foundry-Features: Evaluations=V1Preview` が付く。付けずに 403 `preview_feature_required` が返った場合は `AIProjectClient(..., allow_preview=True)` にする(2026-09-03 版の公式サンプルは付けていない)。
- 出典: https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard / https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_continuous_evaluation_rule.py

## 2026-10-06 追記(最新化チェック・ライブ未検証)

- **権限の前提は満たしている。**新ページ evaluation-permissions(2026-09-29)は「継続評価・スケジュール評価のルール作成にはプロジェクト MI に Foundry User」「モデルを呼ぶ評価は Foundry User を**アカウントスコープ**で(プロジェクトだけの割り当てでは推論が認可されない)」と明記。本ラボの roles.bicep はプロジェクト MI に Foundry User(+ Cognitive Services OpenAI User)を**アカウントスコープ**で付けている。how-to-monitor-agents-dashboard(2026-09-25 版)のトラブルシューティング表も同じ参照に更新されただけで、継続評価の手順(`azure_ai_source` / `scenario: responses`、既定 100 回/時)は変わっていない。→ 再実測で D にランが出なければ、原因は RBAC ではなくデータソースの形・非同期の遅延・観測面のいずれか。
- azure-ai-projects 2.8.0 でも `evaluation_rules` は GA の操作グループのまま、`allow_preview=True` のときだけ `Foundry-Features: Evaluations=V1Preview` を付ける実装は 2.7.0 と同じ。
- **要再実測のまま**(優先度: 高)。期待: D に `continuousevalrun_*` と `report_url` が出る(出れば上の「つまりどころ」1〜2 点目を訂正)。

## 2026-10-06 再実測(ライブ)— **自動ランが出なかった真因は 2 つ。どちらも probe 側の誤り**

環境: japaneast・rg-foundry-probes(aif-fprobes1006、App Insights 接続あり)・azure-ai-projects 2.8.0 / openai 3.24.0・判定 gpt-5.4-mini。13:22〜13:55 UTC に 5 回+補助実験 3 本。

1. **`sampling_rate` は割合ではなく百分率**(SDK の docstring: "Percentage (0-100] chance that a matching event triggers an evaluation"。2.4.0〜2.8.0 で同じ)。probe は 08-04 から `sampling_rate=1.0` を渡しており、**実際は 1% しか評価されなかった**。公式の形(`azure_ai_source` / `responses`)に直した 09-29 版でも、今日の 1 回目(応答 3 件)・2 回目(応答 6 件・600 秒)はどちらもランが 0 件。公式サンプルと同じ形の補助実験(`sampling_rate` 省略 = 100)では 20 秒以内にランが出た → `sampling_rate=100.0` に直した。
2. **エージェントエンドポイント経由の応答は、ランは作られるが `failed` になる。**直した後の 3 回目は、応答 6 件に対してラン 6 件(1 応答 = 1 ラン、16 秒以内)。内訳は、エージェントエンドポイント(`get_openai_client(agent_name=...)`)の 3 件が `failed`、プロジェクトの openai client+`agent_reference`(公式サンプルの呼び方)の 3 件が `completed`(coherence 4.0、判定 gpt-5.4-mini)。failed の `error`: `Evaluation failed with AOAI error: Error code: 404 - Response with id 'resp_…' not found.`。補助実験で、エージェントエンドポイント経由は `conversation` の有無にかかわらず 404、プロジェクト経由は `conversation` なしでも completed になることを確認した。評価器が応答をプロジェクトの Responses ストアから取りに行くため、エージェントエンドポイントの会話ストアにある応答は見えない(maf-ports Port 15 の「別エージェントの response ID は 404」と同じ種類の分離)。
- ランの `data_source` は `type: azure_ai_responses` / `item_generation_params: {type: response_retrieval, max_num_turns: 10, source: {type: file_content, content: [<response id>]}}` / `event_configuration_id: <ルール ID>`。ルールの判定が通った応答 1 件ごとに 1 ランができる。
- 補助実験: 公式サンプルの `builtin.violence`(安全性評価器)は、ランは completed でも結果は `errored=1`。coherence と同じ eval に混ぜても violence だけ errored だった(エラーの中身は未確認。japaneast での安全性評価器の提供状況による可能性)。

**上の「発見」「つまりどころ」の訂正**
- 「自動評価ランは `evals.runs.list` では観測できなかった」→ **誤り**。`continuousevalrun_*` として `evals.runs.list(eval_id, order="desc")` に出て、`report_url`(ポータルの評価画面)を持つ。SDK だけで結果を取ってアサートする CI 的な使い方もできる(`runs.output_items.list` で評価器ごとのスコア・理由が取れる)。
- 変わらない点: ルールは prompt agent スコープ必須(`filter.agent_name`)。list の戻りで `event_type` が None。

**つまりどころ(新)**
- `sampling_rate=1.0` を「100%」のつもりで渡すと 1% になる(型が float なので気づきにくい)。省略すれば 100。
- **エージェントエンドポイント(`/agents/<name>/endpoint/protocols/openai`)で呼ぶアプリに継続評価を掛けると、ランは作られるが全件 `failed`(404)になる。**ダッシュボードにランが並ぶので「動いている」と誤認しやすい。継続評価の対象にする呼び出しは、プロジェクトの `/openai/v1` に `agent_reference` を付けて呼ぶ(公式サンプルと同じ)。エージェントエンドポイントで発行した応答を評価する手段は、2026-10-06 時点の公式の手順には見当たらない。

**SI 判断メモ(改訂)**: 継続評価は「prompt agent+プロジェクトの Responses API(`agent_reference`)で呼ぶ」構成なら SDK だけで配線から結果の取得まで完結する。エージェントエンドポイント(エージェント単位の URL・ID)を使う設計とは両立しないので、継続評価を要件にするなら呼び出し方を先に決める。
