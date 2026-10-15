"""Foundry トレーシング(App Insights 送信)の配線。

agent-framework は既定で OTel 計装が有効。エクスポータだけ App Insights に
向ければ、エージェント実行・ツール呼び出しがトレースとしてポータル
(プロジェクトの Traces / App Insights)に届く。

ports/trend-analysis 以降の各ポートの observability.py と同一。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: 全スパンを送る(azure-monitor-opentelemetry 1.8.6 以降の既定 = 5 スパン/秒の
#: レート制限サンプラーを無効化する。理由は setup_tracing のコメント)
FULL_SAMPLING = 1.0


def setup_tracing(connection_string: str | None) -> bool:
    """App Insights へのトレース送信を構成する。

    接続文字列が無い、または azure-monitor-opentelemetry 未インストール
    (オフライン実行)の場合は何もしない。戻り値は有効化されたかどうか。
    """
    if not connection_string:
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:
        logger.warning(
            "azure-monitor-opentelemetry が未インストールのためトレース無効"
            "(uv sync --extra live で導入)"
        )
        return False
    # sampling_ratio=1.0 で全スパンを送る(2026-10-06 ライブで発覚)。
    # azure-monitor-opentelemetry は 1.8.6 から既定のサンプラーが RateLimitedSampler
    # (5 スパン/秒)で、エージェント・ワークフローのように短時間に多数のスパンを
    # 出す処理では**同じトレースの一部のスパンだけが欠ける**(親が 100% で採られた
    # 場合、子は現在のレートで個別に再判定されるため)。ラボはトレースで分岐・周回・
    # ツール呼び出しを確認するので全件を残す。環境変数 OTEL_TRACES_SAMPLER /
    # OTEL_TRACES_SAMPLER_ARG を設定すればそちらが優先される
    configure_azure_monitor(connection_string=connection_string, sampling_ratio=FULL_SAMPLING)
    return True
