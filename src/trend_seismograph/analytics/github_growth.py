from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trend_seismograph.storage.file_store import read_json, write_json


def load_repo_history(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    return read_json(data_dir / "snapshots" / "repo_snapshots.json", {"repos": {}}).get("repos", {})


def save_repo_snapshots(data_dir: Path, repo_items: list[dict[str, Any]], snapshot_at: str) -> None:
    path = data_dir / "snapshots" / "repo_snapshots.json"
    existing = read_json(path, {"repos": {}})
    repos = existing.setdefault("repos", {})
    for item in repo_items:
        full_name = item.get("full_name") or item.get("title")
        if not full_name:
            continue
        entries = repos.setdefault(full_name, [])
        entries.append(
            {
                "snapshot_at": snapshot_at,
                "stars": int(item.get("stars") or 0),
                "forks": int(item.get("forks") or 0),
                "watchers": int(item.get("watchers") or 0),
                "open_issues": int(item.get("open_issues") or 0),
                "url": item.get("url"),
                "topics": item.get("topics", []),
                "language": item.get("language"),
                "description": item.get("abstract_or_description"),
            }
        )
        repos[full_name] = sorted(entries, key=lambda row: row["snapshot_at"])[-240:]
    write_json(path, existing)


def apply_star_deltas(data_dir: Path, repo_items: list[dict[str, Any]], now: datetime) -> None:
    history = load_repo_history(data_dir)
    for item in repo_items:
        full_name = item.get("full_name") or item.get("title")
        current = int(item.get("stars") or 0)
        entries = history.get(full_name, [])
        item["star_delta_1h"] = delta_since(entries, current, now - timedelta(hours=1))
        item["star_delta_24h"] = delta_since(entries, current, now - timedelta(hours=24))
        item["star_delta_72h"] = delta_since(entries, current, now - timedelta(hours=72))
        item["star_delta_7d"] = delta_since(entries, current, now - timedelta(days=7))
        item["star_history_available"] = bool(entries)


def delta_since(entries: list[dict[str, Any]], current_stars: int, since: datetime) -> int:
    if not entries:
        return 0
    candidates = []
    for entry in entries:
        try:
            ts = datetime.fromisoformat(entry["snapshot_at"].replace("Z", "+00:00")).astimezone(UTC)
        except Exception:  # noqa: BLE001
            continue
        if ts <= since:
            candidates.append((ts, entry))
    baseline = candidates[-1][1] if candidates else entries[0]
    return max(0, current_stars - int(baseline.get("stars") or 0))
