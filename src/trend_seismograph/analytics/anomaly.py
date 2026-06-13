from __future__ import annotations

from datetime import datetime
from typing import Any

from .scoring import compute_topic_signals


def detect_anomalies(
    items: list[dict[str, Any]],
    *,
    config,
    history_snapshots: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    window_hours: int = 24,
) -> list[dict[str, Any]]:
    signals = compute_topic_signals(
        items,
        config=config,
        history_snapshots=history_snapshots,
        now=now,
        window_hours=window_hours,
    )
    for signal in signals:
        signal["metrics"]["magnitude"] = signal["magnitude"]
    return signals
