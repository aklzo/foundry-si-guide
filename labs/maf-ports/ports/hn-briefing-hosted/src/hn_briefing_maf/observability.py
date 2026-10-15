"""Foundry トレーシング(App Insights 送信)の配線 — クライアント実行(CLI)用。

agent-framework は既定で OTel 計装が有効。エクスポータだけ App Insights に
向ければ、ワークフロー各段(executor.process)・エージェント実行
(invoke_agent)・ツール実行(execute_tool)がトレースとしてポータルに届く。

hosted agent 側は**この配線が不要**: プラットフォームが接続文字列を
コンテナへ自動注入し、protocol ライブラリ(ResponsesHostServer)が OTel を
既定で発信する(README の学び参照)。
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
    # が落ちてトレースが歯抜けになる(2026-10-06 に trend-analysis のライブで実測)。
    # ラボはトレースの確認が検証項目なので全件送る。本番ではコストと相談して決める。
    # hosted 側(コンテナ)はプロトコルライブラリが構成するので、この設定は CLI 実行だけに効く。
    configure_azure_monitor(connection_string=connection_string, sampling_ratio=1.0)
    return True
