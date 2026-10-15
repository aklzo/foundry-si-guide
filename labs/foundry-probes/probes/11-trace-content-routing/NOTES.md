# トレース本文の保護テーブル振り分け(AppGenAIContent)— 挙動発見メモ(2026-10-06 実測)

環境: japaneast・main.bicep の基盤(rg-foundry-probes。Log Analytics + App Insights をプロジェクトに接続)・azure-monitor-opentelemetry 1.8.10・azure-ai-projects 2.8.0・agent-framework-core 1.20.0 / -openai 1.15.0(`--extra maf`)・gpt-5.4-mini。サブスクリプションの feature flag `protectGenAISensitiveData` / `optOutProtectGenAISensitiveData` はどちらも **NotRegistered**(サブスクリプション全体の設定変更になるので登録していない)。`AppGenAIContent` テーブルは作成済みで、`protectionLevel` は未設定(管理 API `2025-07-01` の応答にこのプロパティが現れない)。2 回実測した。1 回目(run `p11d2c67821`、13:18:46 UTC 送信)は azure-monitor-opentelemetry の既定サンプラー(rate-limited、5 spans/秒)のまま、2 回目(13:50 送信)は `sampling_ratio=1.0` で全件送信。1 回目でも送ったスパン(A1 2・A2 1・C 2)はすべて届いており間引きは起きていなかったが、件数を比べる probe なので 2 回目以降は全件送信にした。**結果の分類は 2 回とも同一**。

問い: **公式 traces-sensitive-content(プレビュー、ms.date 2026-07-21)の「移行日 2026-09-30 以降、機微な gen_ai.* 属性の値は従来テーブルから消え、AppGenAIContent への短いポインタに置き換わる」は、発生源ごとに実際どうなっているか。**

## 結果(発生源 × テーブル。目印 `p11d2c67821-<発生源>` で KQL)

| 発生源 | AppDependencies / AppTraces(従来テーブル) | AppGenAIContent | `_MS.GenAIContentId` |
| --- | --- | --- | --- |
| A1 合成スパン(chat に input / output / system_instructions / tool.definitions、execute_tool に tool.call.arguments / result) | 2 行。**6 属性とも本文が残る** | 2 行。InputMessages / OutputMessages / SystemInstructions / ToolDefinitions / ToolCallArguments / ToolCallResult | 2 行とも付与し、AppGenAIContent.Id と一致 |
| A2 対照(同じ本文を `probe.input_text` に) | 1 行。本文が残る | **なし** | なし |
| A3 ログレコードの属性 `gen_ai.input.messages` | AppTraces 1 行。属性の本文が残る | 1 行(InputMessages) | 付与・一致 |
| B prompt agent のプラットフォーム側スパン(`invoke_agent <agent>:1` / `chat gpt-5.4-mini-2026-03-17`) | 2 行。input / output messages の本文が残る(system_instructions の属性はそもそも無い) | 2 行(InputMessages ほか) | 付与・一致 |
| C MAF のクライアント側スパン(`invoke_agent` / `chat`、sensitive data 有効) | 2 行。input / output / system_instructions の本文が残る | 2 行(InputMessages / SystemInstructions ほか) | 付与・一致 |
| C MAF のメッセージイベント(ログ) | **AppTraces 2 行。本文はログの Message 本体**(`{"content": "…指示…"}` / `{"content": "…入力…"}`)で、gen_ai.* の機微属性ではない | **なし** | なし |

着信時刻(ingestion_time): 1 回目は B(プラットフォーム側)が送信の 4 秒後、A・C(クライアントのエクスポーター)が約 2.5 分後、**AppGenAIContent が 13:24:37 に一括で従来テーブルより 3〜6 分遅れ**。2 回目は 3 テーブルとも送信の 30〜40 秒後にほぼ同時に届いた → 遅れは一定ではない(親の予備実測では約 5 分)。

## 発見(挙動)

1. **2026-10-06・japaneast・flag 未登録では、どの発生源でも「二重書き」**(従来テーブルにも本文が残り、AppGenAIContent にも入る)。公式の「移行日 2026-09-30 以降は従来テーブルの値がポインタに置き換わる」は、このサブスクリプション・リージョンではまだ有効になっていない。親の予備実測(MAF のクライアント側のみ)と同じ結論を、合成スパン・ログ・プラットフォーム側スパンでも確認した。
2. **振り分けはテーブルの取り込み側で、属性名で決まる。**発生源(自前の OTel スパン / ログ / Foundry のプラットフォーム / MAF)を問わず、公式の 7 属性名の値だけが AppGenAIContent にコピーされる。同じ本文でも別の属性名(A2)なら対象外。→ 自前の計装で本文を `gen_ai.*` 以外のキー(例: `input_text`、ログのメッセージ本体)に入れると、保護テーブルの仕組みの外に漏れる。
3. **MAF のメッセージイベント(AppTraces の Message 本体)は対象外。**MAF 1.20 で sensitive data を有効にすると、スパン属性に加えてログイベントも出る(`enable_instrumentation(enable_sensitive_data=True)` だけで出た)。このイベントは本文をログの本体に持ち、gen_ai.* 属性ではないので振り分けられない。**移行が有効になっても、このイベントの本文は AppTraces に残る**と考えるのが安全。
4. 従来テーブル側の行には `_MS.GenAIContentId` が付き、AppGenAIContent の `Id` と 1 対 1 で一致する(スパン 1 本 = 1 行)。KQL で `join` できる。
5. **Foundry のプラットフォーム側スパン(prompt agent)は、オプトインなしで会話の本文(input / output messages)を記録する**(maf-ports Port 15 の hosted agent での観察と同じ)。system instructions の属性は出ていなかった。

## つまりどころ

- **「AppGenAIContent を Protected にすれば本文が隠れる」は 2026-10-06 時点では成り立たない。**従来テーブル(AppDependencies / AppTraces / AppEvents)にも本文が残り、通常の Log Analytics Reader で読める。保護テーブル案を採用する前に、従来テーブルに本文が残っていないことを KQL で確かめる:
  `AppDependencies | where TimeGenerated > ago(1h) | where isnotempty(Properties["gen_ai.input.messages"]) | take 5`(値がポインタ形式に置き換わっているか)と、AppTraces の Message 本体。
- AppGenAIContent は最大で数分遅れて届く(遅れは一定しない)。直後に照会して 0 件でも「振り分けられていない」と判断しない(本 probe は最大 20 分待つ)。

## SI 判断メモ

- 会話の本文を運用ログに残すかの選択肢(architecture 09 §3.6)に「同じ App Insights のまま本文だけ保護テーブルへ」を加えるのは、**(1) 移行の有効化(flag の登録、または移行の完了を実測で確認)(2) テーブルを Protected に(3) 読む人に Privileged Monitoring Data Reader**の 3 点がそろってから。さらに **(4) 本文を gen_ai.* 以外に書く計装(MAF のメッセージイベント・自前のログ)を止める**、を加える。
- 移行の進み具合はリージョン・サブスクリプション・時期で変わりうる。採用する案件では、本 probe(または同じ KQL)を受入試験と定期点検に入れる。
- 早期有効化の flag を登録した後の挙動(従来テーブルの値がポインタに置き換わるか、AppTraces のメッセージイベントはどうなるか)は**未検証**(サブスクリプション全体の設定変更なので実施していない)。
