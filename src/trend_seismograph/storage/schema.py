from __future__ import annotations

from typing import Final

VALID_SEVERITY_LABELS: Final[set[str]] = {
    "微弱波动",
    "局部升温",
    "明显异常",
    "疑似爆发",
    "强趋势震荡",
}

SOURCE_TYPES: Final[set[str]] = {"paper", "repo", "blog", "benchmark"}


def validate_hotspot_schema(snapshot: dict) -> list[str]:
    errors: list[str] = []
    required = [
        "snapshot_hour",
        "generated_at",
        "run_id",
        "mode",
        "top_hotspots",
        "source_status",
        "partial",
    ]
    for field in required:
        if field not in snapshot:
            errors.append(f"hourly missing {field}")
    for hotspot in snapshot.get("top_hotspots", []):
        if not isinstance(hotspot.get("magnitude"), int | float):
            errors.append(f"hotspot {hotspot.get('topic')} missing numeric magnitude")
        if hotspot.get("severity_label") not in VALID_SEVERITY_LABELS:
            errors.append(f"hotspot {hotspot.get('topic')} invalid severity_label")
        evidence = hotspot.get("evidence") or []
        if not evidence:
            errors.append(f"hotspot {hotspot.get('topic')} missing evidence")
        for entry in evidence:
            if not entry.get("source_url"):
                errors.append(f"hotspot {hotspot.get('topic')} evidence missing source_url")
    return errors


def validate_report_schema(report: dict) -> list[str]:
    errors: list[str] = []
    required = [
        "report_date",
        "generated_at",
        "run_id",
        "mode",
        "top_anomalies",
        "raw_sources_summary",
        "confidence_summary",
        "caveats",
    ]
    for field in required:
        if field not in report:
            errors.append(f"report missing {field}")
    for anomaly in report.get("top_anomalies", []):
        if not isinstance(anomaly.get("magnitude"), int | float):
            errors.append(f"anomaly {anomaly.get('topic')} missing numeric magnitude")
        if anomaly.get("severity_label") not in VALID_SEVERITY_LABELS:
            errors.append(f"anomaly {anomaly.get('topic')} invalid severity_label")
        evidence = anomaly.get("evidence") or []
        if not evidence:
            errors.append(f"anomaly {anomaly.get('topic')} missing evidence")
        for entry in evidence:
            if not entry.get("source_url"):
                errors.append(f"anomaly {anomaly.get('topic')} evidence missing source_url")
    return errors
