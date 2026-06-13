from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from trend_seismograph.analytics.anomaly import detect_anomalies
from trend_seismograph.analytics.cooccurrence import build_cooccurrence_graph
from trend_seismograph.analytics.github_growth import apply_star_deltas, save_repo_snapshots
from trend_seismograph.analytics.scoring import enrich_items
from trend_seismograph.analytics.watchlist import detect_watchlist_hits
from trend_seismograph.config import AppConfig
from trend_seismograph.fetchers.arxiv import ArxivFetcher
from trend_seismograph.fetchers.github import GitHubFetcher
from trend_seismograph.storage.file_store import FileStore
from trend_seismograph.storage.neon_store import NeonStore


def parse_hour(hour: str) -> datetime:
    if len(hour) == 13:
        return datetime.fromisoformat(hour).replace(tzinfo=UTC)
    return datetime.fromisoformat(hour.replace("Z", "+00:00")).astimezone(UTC)


def run_hourly(
    *,
    config: AppConfig,
    hour: str,
    storage: str = "file",
    source_filter: set[str] | None = None,
    force: bool = False,
    no_push: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    store = FileStore(config.data_dir)
    if store.hourly_exists(hour) and not force and not dry_run:
        return {"skipped": True, "reason": "hourly snapshot exists", "path": str(store.hourly_path(hour))}

    hour_dt = parse_hour(hour)
    start = hour_dt
    end = hour_dt + timedelta(hours=1)
    run_id = f"hourly-{hour.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
    fetched = fetch_sources(config=config, start=start, end=end, source_filter=source_filter)
    items = [item for result in fetched for item in result.items]
    repo_items = [item for item in items if item.get("source_type") == "repo"]
    apply_star_deltas(config.data_dir, repo_items, hour_dt)
    enriched = enrich_items(items, config)
    history = store.list_hourly_snapshots()
    signals = detect_anomalies(enriched, config=config, history_snapshots=history, now=hour_dt, window_hours=1)
    watchlist_hits = detect_watchlist_hits(signals, config.watchlist)
    top_hotspots = signals[:10]
    snapshot = {
        "snapshot_hour": hour,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "mode": "hourly",
        "total_items_scanned": len(enriched),
        "total_papers_scanned": sum(1 for item in enriched if item.get("source_type") == "paper"),
        "total_repos_scanned": sum(1 for item in enriched if item.get("source_type") == "repo"),
        "total_topics_tracked": len(config.taxonomy.get("topics", [])),
        "max_magnitude": max((signal["magnitude"] for signal in signals), default=0),
        "top_hotspots": top_hotspots,
        "watchlist_hits": watchlist_hits,
        "github_surges": github_surges(enriched),
        "dataset_bursts": burst_terms(signals, "related_datasets"),
        "method_bursts": burst_terms(signals, "related_methods"),
        "institution_signals": burst_terms(signals, "related_institutions"),
        "source_status": [result.status() for result in fetched],
        "partial": any(result.partial or not result.ok for result in fetched),
        "push_recommended": any(signal.get("push_recommended") for signal in signals) or any(hit.get("push_enabled") for hit in watchlist_hits),
        "caveats": caveats_for_run(fetched, enriched),
    }
    graph = build_cooccurrence_graph(enriched, window_label=hour)

    if dry_run:
        snapshot["dry_run"] = True
        return snapshot

    for result in fetched:
        store.save_raw_items(run_id, result.source_name, result.items)
    saved, path = store.save_hourly(snapshot, force=force)
    store.save_cooccurrence(hour[:10], graph)
    store.publish_config_snapshots(config)
    save_repo_snapshots(config.data_dir, repo_items, datetime.now(UTC).isoformat())

    neon_result = None
    if storage in {"neon", "both"}:
        neon_result = NeonStore().sync(enriched, hourly=snapshot)
        snapshot.setdefault("storage_status", {})["neon"] = neon_result.__dict__
        store.save_hourly(snapshot, force=True)
    snapshot["saved"] = saved
    snapshot["path"] = str(path)
    snapshot["push_status"] = {"skipped": no_push, "reason": "no-push flag" if no_push else "run push-hotspots to deliver channels"}
    return snapshot


def fetch_sources(*, config: AppConfig, start: datetime, end: datetime, source_filter: set[str] | None = None):
    results = []
    for source in config.sources.get("sources", []):
        name = source.get("source_name")
        if source_filter and name not in source_filter:
            continue
        if not source.get("enabled", True):
            continue
        if name == "arxiv":
            categories = source.get("categories") or ["cs.AI", "cs.LG"]
            results.append(ArxivFetcher().fetch(start=start, end=end, categories=categories))
        elif name == "github":
            queries = source.get("queries") or ["machine learning", "llm"]
            results.append(GitHubFetcher().fetch(start=start, end=end, queries=queries))
    return results


def github_surges(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repos = []
    for item in items:
        if item.get("source_type") != "repo":
            continue
        repos.append(
            {
                "repo_full_name": item.get("full_name") or item.get("title"),
                "url": item.get("url"),
                "stars": item.get("stars", 0),
                "star_delta_1h": item.get("star_delta_1h", 0),
                "star_delta_24h": item.get("star_delta_24h", 0),
                "star_delta_72h": item.get("star_delta_72h", 0),
                "star_delta_7d": item.get("star_delta_7d", 0),
                "matched_topics": [match["topic"] for match in item.get("matched_topics", [])[:5]],
                "language": item.get("language"),
                "description": item.get("abstract_or_description"),
                "source_url": item.get("source_url"),
            }
        )
    return sorted(repos, key=lambda row: (row["star_delta_24h"], row["stars"]), reverse=True)[:10]


def burst_terms(signals: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    rows = []
    for signal in signals:
        for term in signal.get(field, [])[:5]:
            rows.append({"topic": signal["topic"], "term": term, "magnitude": signal["magnitude"]})
    return sorted(rows, key=lambda row: row["magnitude"], reverse=True)[:20]


def caveats_for_run(results, items: list[dict[str, Any]]) -> list[str]:
    notes = []
    failed = [result.source_name for result in results if not result.ok]
    if failed:
        notes.append(f"以下来源失败或部分失败：{', '.join(failed)}。")
    if not items:
        notes.append("当前窗口未抓取到可匹配信号；系统没有生成趋势判断。")
    notes.append("生产报告仅使用真实抓取数据；没有 API Key 时增强源会自动降级。")
    return notes
