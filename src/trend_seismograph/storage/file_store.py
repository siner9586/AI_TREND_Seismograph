from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=json_default)
        handle.write("\n")
    tmp.replace(path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(content)
    tmp.replace(path)


@dataclass
class FileStore:
    data_dir: Path

    def hourly_path(self, hour: datetime | str) -> Path:
        hour_text = hour if isinstance(hour, str) else hour.strftime("%Y-%m-%dT%H")
        date_part, hour_part = hour_text.split("T")
        return self.data_dir / "hotspots" / date_part / f"{hour_part}.json"

    def report_json_path(self, date: str) -> Path:
        return self.data_dir / "reports" / f"{date}.json"

    def report_md_path(self, date: str) -> Path:
        return self.data_dir / "reports" / f"{date}.md"

    def hourly_exists(self, hour: datetime | str) -> bool:
        return self.hourly_path(hour).exists()

    def report_exists(self, date: str) -> bool:
        return self.report_json_path(date).exists() and self.report_md_path(date).exists()

    def save_raw_items(self, run_id: str, source_name: str, items: list[dict[str, Any]]) -> Path:
        path = self.data_dir / "raw" / f"{run_id}-{source_name}.json"
        write_json(path, {"run_id": run_id, "source_name": source_name, "items": items})
        return path

    def save_hourly(self, snapshot: dict[str, Any], force: bool = False) -> tuple[bool, Path]:
        path = self.hourly_path(snapshot["snapshot_hour"])
        if path.exists() and not force:
            return False, path
        write_json(path, snapshot)
        write_json(self.data_dir / "hotspots" / "latest.json", snapshot)
        self._update_hotspot_index()
        return True, path

    def save_report(self, report: dict[str, Any], markdown: str, force_report: bool = False) -> tuple[bool, Path]:
        date = report["report_date"]
        json_path = self.report_json_path(date)
        md_path = self.report_md_path(date)
        if (json_path.exists() or md_path.exists()) and not force_report:
            return False, json_path
        write_json(json_path, report)
        write_text(md_path, markdown)
        latest = {
            "updated_at": datetime.now(UTC).isoformat(),
            "latest_report_date": date,
            "report_json_path": f"data/reports/{date}.json",
            "report_md_path": f"data/reports/{date}.md",
            "max_magnitude": report.get("max_magnitude", 0),
            "top_anomalies": report.get("top_anomalies", [])[:5],
            "hourly_latest_path": "data/hotspots/latest.json",
        }
        write_json(self.data_dir / "latest.json", latest)
        self._update_history_index()
        return True, json_path

    def save_cooccurrence(self, date: str, graph: dict[str, Any]) -> None:
        write_json(self.data_dir / "graphs" / "cooccurrence" / f"{date}.json", graph)
        write_json(self.data_dir / "graphs" / "cooccurrence" / "latest.json", graph)

    def publish_config_snapshots(self, config: Any) -> None:
        write_json(self.data_dir / "topics.json", {"topics": config.taxonomy.get("topics", [])})
        write_json(self.data_dir / "watchlist.json", config.watchlist)
        write_json(self.data_dir / "institutions.json", config.institutions)
        write_json(self.data_dir / "sources.json", config.sources)

    def load_hourly_latest(self) -> dict[str, Any] | None:
        return read_json(self.data_dir / "hotspots" / "latest.json")

    def load_latest(self) -> dict[str, Any] | None:
        return read_json(self.data_dir / "latest.json")

    def load_report(self, date: str) -> dict[str, Any] | None:
        return read_json(self.report_json_path(date))

    def list_hourly_snapshots(self) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for path in sorted((self.data_dir / "hotspots").glob("*/*.json")):
            loaded = read_json(path)
            if loaded:
                snapshots.append(loaded)
        return snapshots

    def list_reports(self) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        for path in sorted((self.data_dir / "reports").glob("*.json")):
            loaded = read_json(path)
            if loaded:
                reports.append(loaded)
        return reports

    def load_push_index(self) -> dict[str, Any]:
        return read_json(self.data_dir / "push_events.json", {"events": []})

    def save_push_index(self, index: dict[str, Any]) -> None:
        write_json(self.data_dir / "push_events.json", index)

    def _update_hotspot_index(self) -> None:
        items = []
        for path in sorted((self.data_dir / "hotspots").glob("*/*.json")):
            rel = path.relative_to(self.data_dir.parent)
            loaded = read_json(path, {})
            items.append(
                {
                    "snapshot_hour": loaded.get("snapshot_hour"),
                    "path": str(rel),
                    "max_magnitude": loaded.get("max_magnitude", 0),
                    "total_items_scanned": loaded.get("total_items_scanned", 0),
                    "partial": loaded.get("partial", False),
                }
            )
        write_json(self.data_dir / "hotspots" / "index.json", {"items": items})

    def _update_history_index(self) -> None:
        reports = []
        for path in sorted((self.data_dir / "reports").glob("*.json")):
            loaded = read_json(path, {})
            reports.append(
                {
                    "report_date": loaded.get("report_date", path.stem),
                    "path": f"data/reports/{path.name}",
                    "max_magnitude": loaded.get("max_magnitude", 0),
                    "generated_at": loaded.get("generated_at"),
                    "status": loaded.get("status", "generated"),
                }
            )
        write_json(self.data_dir / "history" / "index.json", {"reports": reports})
