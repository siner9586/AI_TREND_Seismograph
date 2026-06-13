from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trend_seismograph.storage.file_store import FileStore, read_json
from trend_seismograph.storage.schema import validate_hotspot_schema, validate_report_schema


@dataclass
class QAResult:
    ok: bool
    errors: list[str]
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def qa_daily(data_dir: Path, date: str) -> QAResult:
    store = FileStore(data_dir)
    errors: list[str] = []
    warnings: list[str] = []
    json_path = store.report_json_path(date)
    md_path = store.report_md_path(date)
    if not json_path.exists():
        errors.append(f"missing {json_path}")
        return QAResult(False, errors, warnings)
    if not md_path.exists():
        errors.append(f"missing {md_path}")
    report = read_json(json_path, {})
    errors.extend(validate_report_schema(report))
    latest = read_json(data_dir / "latest.json", {})
    if latest.get("latest_report_date") != date:
        errors.append("data/latest.json does not point to requested report")
    hourly_latest = data_dir / "hotspots" / "latest.json"
    if not hourly_latest.exists():
        warnings.append("hourly latest snapshot is missing")
    source_status = report.get("raw_sources_summary", {}).get("source_status", [])
    if not source_status:
        errors.append("source_status is missing")
    if contains_mock(report):
        errors.append("report appears to contain mock/test data marker")
    return QAResult(not errors, errors, warnings)


def qa_hourly(data_dir: Path, hour: str) -> QAResult:
    store = FileStore(data_dir)
    errors: list[str] = []
    warnings: list[str] = []
    path = store.hourly_path(hour)
    if not path.exists():
        errors.append(f"missing {path}")
        return QAResult(False, errors, warnings)
    snapshot = read_json(path, {})
    errors.extend(validate_hotspot_schema(snapshot))
    latest = read_json(data_dir / "hotspots" / "latest.json", {})
    if latest.get("snapshot_hour") != hour:
        warnings.append("hotspots/latest.json does not point to requested hour")
    if not snapshot.get("source_status"):
        errors.append("source_status is missing")
    if contains_mock(snapshot):
        errors.append("hourly snapshot appears to contain mock/test data marker")
    return QAResult(not errors, errors, warnings)


def contains_mock(payload: Any) -> bool:
    if isinstance(payload, dict):
        return any(contains_mock(value) for value in payload.values())
    if isinstance(payload, list):
        return any(contains_mock(value) for value in payload)
    if isinstance(payload, str):
        lowered = payload.lower()
        return "mock data" in lowered or "lorem ipsum" in lowered
    return False
