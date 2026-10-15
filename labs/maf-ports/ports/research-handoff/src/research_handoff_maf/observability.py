"""Foundry トレーシング(App Insights 送信)の配線。

agent-framework は既定で OTel 計装が有効。エクスポータだけ App Insights に
向ければ、エージェント実行・ツール呼び出しがトレースとしてポータル
(プロジェクトの Traces / App Insights)に届く。

ports/trend-analysis/src/trend_analysis_maf/observability.py と同一。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


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
    # azure-monitor-opentelemetry 1.8.x の既定サンプラーは rate-limited(5 spans/秒)。
    # ワークフロー開始直後のスパンの山(workflow.run / executor.process / invoke_agent)
    # が落ちてトレースが歯抜けになる(2026-10-06 ライブで実測)。ラボはトレースの確認が
    # 検証項目なので全件送る。本番ではコストと相談してサンプリングを決める。
    configure_azure_monitor(connection_string=connection_string, sampling_ratio=1.0)
    return True
