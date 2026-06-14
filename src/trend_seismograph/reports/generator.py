from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from trend_seismograph.analytics.anomaly import detect_anomalies
from trend_seismograph.analytics.cooccurrence import build_cooccurrence_graph
from trend_seismograph.analytics.github_growth import apply_star_deltas, save_repo_snapshots
from trend_seismograph.analytics.scoring import enrich_items
from trend_seismograph.analytics.watchlist import detect_watchlist_hits
from trend_seismograph.config import AppConfig
from trend_seismograph.reports.curation import enrich_signal_curation
from trend_seismograph.reports.hourly import fetch_sources
from trend_seismograph.reports.markdown import render_daily_markdown
from trend_seismograph.storage.file_store import FileStore
from trend_seismograph.storage.neon_store import NeonStore


def run_daily(
    *,
    config: AppConfig,
    date: str,
    lookback_hours: int = 72,
    storage: str = "file",
    source_filter: set[str] | None = None,
    force: bool = False,
    force_report: bool = False,
    no_push: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    store = FileStore(config.data_dir)
    if store.report_exists(date) and not force_report and not dry_run:
        return {"skipped": True, "reason": "daily report exists", "path": str(store.report_json_path(date))}
    end = datetime.fromisoformat(date).replace(tzinfo=UTC) + timedelta(days=1)
    start = end - timedelta(hours=lookback_hours)
    analysis_time = end - timedelta(seconds=1)
    run_id = f"daily-{date.replace('-', '')}-{uuid.uuid4().hex[:8]}"
    fetched = fetch_sources(config=config, start=start, end=end, source_filter=source_filter)
    items = [item for result in fetched for item in result.items]
    repo_items = [item for item in items if item.get("source_type") == "repo"]
    apply_star_deltas(config.data_dir, repo_items, end)
    enriched = enrich_items(items, config)
    history = store.list_hourly_snapshots()
    signals = detect_anomalies(
        enriched,
        config=config,
        history_snapshots=history,
        now=analysis_time,
        window_hours=lookback_hours,
    )
    watchlist_hits = detect_watchlist_hits(signals, config.watchlist)
    graph = build_cooccurrence_graph(enriched, window_label=date)
    report = {
        "report_date": date,
        "source_window": {"start": start.isoformat(), "end": end.isoformat(), "lookback_hours": lookback_hours},
        "baseline_window": {"days": 30, "low_history_confidence": len(history) < 24 * 7},
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "mode": "daily",
        "status": "generated",
        "total_items_scanned": len(enriched),
        "total_papers_scanned": sum(1 for item in enriched if item.get("source_type") == "paper"),
        "total_repos_scanned": sum(1 for item in enriched if item.get("source_type") == "repo"),
        "total_topics_tracked": len(config.taxonomy.get("topics", [])),
        "max_magnitude": max((signal["magnitude"] for signal in signals), default=0),
        "top_anomalies": enrich_daily_anomalies(signals, history),
        "emerging_topics": [enrich_signal_curation(signal) for signal in signals if signal["magnitude"] >= 3.0][:10],
        "revived_topics": [enrich_signal_curation(signal) for signal in signals if signal.get("metrics", {}).get("cold_revival_score")][:10],
        "institution_clusters": institution_clusters(signals),
        "github_surges": github_surges(enriched),
        "dataset_bursts": term_bursts(signals, "related_datasets"),
        "method_bursts": term_bursts(signals, "related_methods"),
        "watchlist": {"hits": watchlist_hits, "configured": config.watchlist.get("watchlists", [])},
        "cooccurrence_summary": {
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
            "top_nodes": graph["nodes"][:12],
        },
        "trend_charts": build_trend_charts(signals, history),
        "raw_sources_summary": {
            "source_status": [result.status() for result in fetched],
            "partial": any(result.partial or not result.ok for result in fetched),
        },
        "confidence_summary": confidence_summary(signals),
        "caveats": caveats_for_daily(fetched, enriched, history),
    }
    markdown = render_daily_markdown(report)
    if dry_run:
        report["dry_run"] = True
        return report

    for result in fetched:
        store.save_raw_items(run_id, result.source_name, result.items)
    saved, path = store.save_report(report, markdown, force_report=force_report or force)
    store.save_cooccurrence(date, graph)
    store.publish_config_snapshots(config)
    save_repo_snapshots(config.data_dir, repo_items, datetime.now(UTC).isoformat())
    if storage in {"neon", "both"}:
        neon_result = NeonStore().sync(enriched, report=report)
        report.setdefault("storage_status", {})["neon"] = neon_result.__dict__
        store.save_report(report, markdown, force_report=True)
    report["saved"] = saved
    report["path"] = str(path)
    report["push_status"] = {"skipped": no_push, "reason": "no-push flag" if no_push else "optional push module"}
    return report


def enrich_daily_anomalies(signals: list[dict[str, Any]], history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for signal in signals[:20]:
        copied = enrich_signal_curation(signal)
        copied["why_it_matters"] = why_it_matters(copied)
        copied["representative_papers"] = [e for e in copied.get("evidence", []) if e.get("source_type") == "paper"][:5]
        copied["related_repos"] = [e for e in copied.get("evidence", []) if e.get("source_type") == "repo"][:5]
        copied["trend_30d"] = topic_history(copied["topic"], history, days=30)
        copied["trend_90d"] = topic_history(copied["topic"], history, days=90)
        copied["trend_180d"] = topic_history(copied["topic"], history, days=180)
        enriched.append(copied)
    return enriched


def why_it_matters(signal: dict[str, Any]) -> str:
    drivers = signal.get("key_drivers", [])
    if "跨源共振" in signal.get("tags", []):
        return "论文、代码或词典信号同时出现，说明这不是孤立事件，值得在未来 3 到 7 天继续观察。"
    if any("GitHub" in driver for driver in drivers):
        return "开源项目出现同步信号，可能意味着工程生态正在加速试验。"
    return "当前信号主要来自研究侧，仍需观察后续代码、数据集或机构连续发布情况。"


def topic_history(topic: str, history: list[dict[str, Any]], *, days: int) -> list[dict[str, Any]]:
    rows = []
    cutoff = datetime.now(UTC) - timedelta(days=days)
    for snapshot in history:
        try:
            ts = datetime.fromisoformat(snapshot.get("snapshot_hour", "").replace("Z", "+00:00")).astimezone(UTC)
        except Exception:  # noqa: BLE001
            continue
        if ts < cutoff:
            continue
        for hotspot in snapshot.get("top_hotspots", []):
            if hotspot.get("topic") == topic:
                rows.append(
                    {
                        "ts": snapshot.get("snapshot_hour"),
                        "magnitude": hotspot.get("magnitude", 0),
                        "paper_count": hotspot.get("metrics", {}).get("paper_count", 0),
                        "repo_count": hotspot.get("metrics", {}).get("repo_count", 0),
                        "github_star_delta": hotspot.get("metrics", {}).get("github_star_delta", 0),
                    }
                )
    return rows[-240:]


def build_trend_charts(signals: list[dict[str, Any]], history: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        signal["topic"]: {
            "30d": topic_history(signal["topic"], history, days=30),
            "90d": topic_history(signal["topic"], history, days=90),
            "180d": topic_history(signal["topic"], history, days=180),
        }
        for signal in signals[:20]
    }


def institution_clusters(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, str]] = Counter()
    representatives: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        for institution in signal.get("related_institutions", []):
            key = (institution, signal["topic"])
            counter[key] += 1
            representatives[key].extend(signal.get("evidence", [])[:2])
    return [
        {
            "institution_name": institution,
            "topic": topic,
            "matched_papers": sum(1 for e in representatives[(institution, topic)] if e.get("source_type") == "paper"),
            "matched_repos": sum(1 for e in representatives[(institution, topic)] if e.get("source_type") == "repo"),
            "concentration_score": count,
            "representative_items": representatives[(institution, topic)][:5],
        }
        for (institution, topic), count in counter.most_common(20)
    ]


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
                "forks": item.get("forks", 0),
                "watchers": item.get("watchers", 0),
                "open_issues": item.get("open_issues", 0),
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
    return sorted(repos, key=lambda row: (row["star_delta_24h"], row["stars"]), reverse=True)[:20]


def term_bursts(signals: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    rows = []
    for signal in signals:
        for term in signal.get(field, [])[:8]:
            rows.append({"topic": signal["topic"], "term": term, "magnitude": signal["magnitude"]})
    return sorted(rows, key=lambda row: row["magnitude"], reverse=True)[:30]


def confidence_summary(signals: list[dict[str, Any]]) -> dict[str, Any]:
    if not signals:
        return {"average_confidence": 0, "low_history_topics": 0, "note": "无趋势信号。"}
    return {
        "average_confidence": round(sum(signal.get("confidence", 0) for signal in signals) / len(signals), 3),
        "low_history_topics": sum(1 for signal in signals if signal.get("metrics", {}).get("low_history_confidence")),
        "note": "低历史置信度不代表趋势无效，只代表需要继续积累基线。",
    }


def caveats_for_daily(results, items: list[dict[str, Any]], history: list[dict[str, Any]]) -> list[str]:
    notes = []
    failed = [result.source_name for result in results if not result.ok]
    if failed:
        notes.append(f"以下来源失败或部分失败：{', '.join(failed)}。")
    if len(history) < 24 * 7:
        notes.append("历史快照少于 7 天，30/90/180 天趋势页会显示可用历史而非完整基线。")
    if not items:
        notes.append("当前窗口未抓取到可匹配信号；日报不生成趋势判断。")
    notes.append("生产报告仅使用真实抓取数据；没有 API Key 时增强源会自动降级。")
    return notes
