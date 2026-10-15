#!/usr/bin/env bash
# ライブ再検証のスモーク(2026-10-06 追加): 少数本で upload → CU 解析(prebuilt / カスタム 2 段)→
# CER → 索引(A / C)→ 検索評価 → RAG 回答 → ragas → オフライン指標、の経路が最新の依存と
# サービスで通るかだけを見る。精度の再測定ではない(数本の索引では検索がほぼ自明に当たる)。
#
# 本測定(104 本)の logs/ と AI Search の cuvrag-<config> を上書きしないよう、出力は
# logs/smoke/、インデックスは cuvrag-smoke-<config> に分ける。前提は run_full_eval.sh と同じ
# (基盤デプロイ・setup_azure.sh・カスタムアナライザー作成済み、data/ に動画あり)。
#
#   ./scripts/run_smoke.sh 2>&1 | tee logs/smoke.log        # 最後に SMOKE_DONE
#   SMOKE_VIDEOS=vpn-setup,shortcut-tips ./scripts/run_smoke.sh   # 対象を変える
#
# 既定の 4 本 = 形態ごとに 1 本(ナレーション UI / 無音テロップ / スライド講義 / 長尺 3 章)、
# 計 4.3 分・クエリ 14 問(S 7 / N 4 / C 3)+根拠なし 8 問。
set -euo pipefail
cd "$(dirname "$0")/.."

VIDEOS="${SMOKE_VIDEOS:-vpn-setup,shortcut-tips,security-basics,newhire-orientation}"
LOGS_DIR="${SMOKE_LOGS:-logs/smoke}"
RUN="uv run python scripts/run_pipeline.py --videos $VIDEOS --logs-dir $LOGS_DIR --index-prefix cuvrag-smoke"

echo "=== upload ($VIDEOS) ===" && $RUN upload
echo "=== analyze prebuilt ===" && $RUN analyze --analyzer prebuilt-videoSearch --tag prebuilt --parallel 4
echo "=== analyze custom ===" && $RUN analyze --analyzer videoSearchJa --tag custom --parallel 4
echo "=== cer ===" && $RUN cer --tag prebuilt && $RUN cer --tag custom
echo "=== index (A, C) ===" && for c in A C; do $RUN index --config $c; done
sleep 20  # インデックス反映待ち
echo "=== retrieval eval (A, C) ===" && $RUN eval --configs A,C
echo "=== rag answers (A, C) ===" && $RUN rag-answer --config A && $RUN rag-answer --config C
echo "=== ragas (A, C) ===" && $RUN ragas --config A && $RUN ragas --config C
echo "=== offline metrics ===" && $RUN offline-metrics
echo "SMOKE_DONE"
