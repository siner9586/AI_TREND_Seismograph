from __future__ import annotations

import math


def severity_label(magnitude: float) -> str:
    if magnitude < 2.0:
        return "微弱波动"
    if magnitude < 3.0:
        return "局部升温"
    if magnitude < 4.0:
        return "明显异常"
    if magnitude < 5.0:
        return "疑似爆发"
    return "强趋势震荡"


def calculate_magnitude(metrics: dict) -> tuple[float, str]:
    paper_burst_score = metrics.get("paper_burst_score", 0.0)
    github_signal_score = metrics.get("github_signal_score", 0.0)
    institution_signal_score = metrics.get("institution_signal_score", 0.0)
    dataset_signal_score = metrics.get("dataset_signal_score", 0.0)
    method_signal_score = metrics.get("method_signal_score", 0.0)
    cross_source_confirmation_score = metrics.get("cross_source_confirmation_score", 0.0)
    cold_revival_score = metrics.get("cold_revival_score", 0.0)
    magnitude = min(
        6.0,
        1.0
        + 0.95 * math.log1p(max(0.0, paper_burst_score))
        + 0.80 * max(0.0, github_signal_score)
        + 0.60 * max(0.0, institution_signal_score)
        + 0.50 * max(0.0, dataset_signal_score)
        + 0.45 * max(0.0, method_signal_score)
        + 0.70 * max(0.0, cross_source_confirmation_score)
        + 0.50 * max(0.0, cold_revival_score),
    )
    rounded = round(magnitude, 2)
    return rounded, severity_label(rounded)
