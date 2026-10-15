"""トレース送信の配線(azure-monitor-opentelemetry は差し替えて検証。ネットワーク不要)。"""

import sys
import types
from typing import Any

from travel_memory_maf.observability import FULL_SAMPLING, setup_tracing


def test_setup_tracing_disables_rate_limited_sampling(monkeypatch) -> None:
    """azure-monitor-opentelemetry 1.8.6 以降の既定(RateLimitedSampler 5 スパン/秒)
    では、ワークフローの一部スパンだけが欠ける(2026-10-06 ライブで実測)。
    sampling_ratio=1.0 を明示して全件送ることを固定する。"""
    calls: list[dict[str, Any]] = []
    fake = types.ModuleType("azure.monitor.opentelemetry")
    fake.configure_azure_monitor = lambda **kwargs: calls.append(kwargs)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "azure.monitor.opentelemetry", fake)

    assert setup_tracing("InstrumentationKey=00000000-0000-0000-0000-000000000000") is True
    assert calls == [
        {
            "connection_string": "InstrumentationKey=00000000-0000-0000-0000-000000000000",
            "sampling_ratio": FULL_SAMPLING,
        }
    ]
    assert FULL_SAMPLING == 1.0


def test_setup_tracing_is_noop_without_connection_string() -> None:
    assert setup_tracing(None) is False
