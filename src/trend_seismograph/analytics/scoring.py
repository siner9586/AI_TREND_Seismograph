from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from trend_seismograph.analytics.magnitude import calculate_magnitude
from trend_seismograph.extractors.datasets import extract_datasets
from trend_seismograph.extractors.institutions import extract_institutions
from trend_seismograph.extractors.keywords import extract_keywords
from trend_seismograph.extractors.methods import extract_methods
from trend_seismograph.extractors.topics import TopicMatch, match_topics


def enrich_items(items: list[dict[str, Any]], config) -> list[dict[str, Any]]:
    topics = config.taxonomy.get("topics", [])
    methods = config.methods.get("methods", [])
    datasets = config.datasets.get("datasets", [])
    institutions = config.institutions.get("institutions", [])
    enriched = []
    for item in items:
        text = " ".join(
            [
                item.get("title") or "",
                item.get("abstract_or_description") or "",
                " ".join(item.get("topics") or []),
                " ".join(item.get("categories") or []),
            ]
        )
        method_hits = extract_methods(text, methods)
        dataset_hits = extract_datasets(text, datasets)
        institution_hits = sorted(
            set(item.get("institutions") or []) | set(extract_institutions(text, institutions))
        )
        topic_matches = match_topics(text, topics, methods=method_hits, datasets=dataset_hits)
        keywords = extract_keywords(text)
        copied = dict(item)
        copied.update(
            {
                "extracted_keywords": keywords,
                "extracted_methods": method_hits,
                "extracted_datasets": dataset_hits,
                "extracted_tasks": sorted({task for match in topic_matches for task in match.matched_tasks}),
                "mentioned_models": sorted({model for match in topic_matches for model in match.matched_models}),
                "matched_topics": [match.__dict__ for match in topic_matches],
                "institutions": institution_hits,
                "institutions_json": json.dumps(institution_hits, ensure_ascii=False),
            }
        )
        enriched.append(copied)
    return enriched


def compute_topic_signals(
    items: list[dict[str, Any]],
    *,
    config,
    history_snapshots: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    window_hours: int = 24,
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    history_snapshots = history_snapshots or []
    topic_items: dict[str, list[tuple[dict[str, Any], TopicMatch | dict[str, Any]]]] = defaultdict(list)
    for item in items:
        for match in item.get("matched_topics", []):
            topic_items[match["topic"]].append((item, match))

    baseline = build_baseline(history_snapshots, now=now, exclude_recent_hours=window_hours)
    total_possible_sources = max(2, len([s for s in config.sources.get("sources", []) if s.get("enabled", True)]))
    signals: list[dict[str, Any]] = []
    for topic in [topic["canonical_name"] for topic in config.taxonomy.get("topics", [])]:
        pairs = topic_items.get(topic, [])
        if not pairs:
            continue
        paper_count = sum(1 for item, _ in pairs if item.get("source_type") == "paper")
        repo_count = sum(1 for item, _ in pairs if item.get("source_type") == "repo")
        github_star_delta = sum(int(item.get("star_delta_24h") or 0) for item, _ in pairs if item.get("source_type") == "repo")
        methods = Counter(method for item, _ in pairs for method in item.get("extracted_methods", []))
        datasets = Counter(dataset for item, _ in pairs for dataset in item.get("extracted_datasets", []))
        institutions = Counter(inst for item, _ in pairs for inst in item.get("institutions", []) if inst)
        sources = {item.get("source_name") for item, _ in pairs if item.get("source_name")}
        source_types = {item.get("source_type") for item, _ in pairs if item.get("source_type")}
        match_score = max(float(match.get("score", 0.1)) for _, match in pairs)

        base = baseline.get(topic, {})
        baseline_daily_avg = float(base.get("daily_avg", 0.0))
        baseline_daily_std = float(base.get("daily_std", 0.0))
        baseline_count = baseline_daily_avg * max(1.0, window_hours / 24)
        current_count = len(pairs)
        growth_rate = (current_count + 1) / (baseline_count + 1) - 1
        z_score = (current_count - baseline_count) / (baseline_daily_std + 1)
        paper_source_weight = source_weight(config, "arxiv", "paper")
        paper_burst_score = math.log1p(paper_count) * max(0.0, growth_rate) * paper_source_weight
        github_signal_score = math.log1p(github_star_delta + 2 * sum(int(item.get("star_delta_72h") or 0) for item, _ in pairs) + 3 * sum(int(item.get("star_delta_7d") or 0) for item, _ in pairs)) * match_score
        if github_star_delta == 0:
            github_signal_score += min(0.7, repo_count * 0.12)
        cross_source_confirmation_score = len(source_types) / total_possible_sources
        top_institution_count = institutions.most_common(1)[0][1] if institutions else 0
        institution_concentration_score = top_institution_count / max(1, current_count)
        institution_signal_score = min(1.5, institution_concentration_score * math.log1p(len(institutions) + top_institution_count))
        dataset_signal_score = math.log1p(sum(datasets.values())) * 0.6
        method_signal_score = math.log1p(sum(methods.values())) * 0.55
        cold_revival_score = 1.0 if baseline_daily_avg < 1 and current_count >= 3 and growth_rate >= 2 else 0.0
        low_history = int(base.get("samples", 0)) < 24
        confidence = confidence_score(
            evidence_count=current_count,
            source_type_count=len(source_types),
            low_history=low_history,
            partial_sources=0,
        )
        metrics = {
            "current_1h_count": current_count if window_hours <= 1 else 0,
            "current_24h_count": current_count if window_hours <= 24 else 0,
            "current_72h_count": current_count if window_hours <= 72 else 0,
            "current_7d_count": current_count if window_hours <= 168 else 0,
            "baseline_daily_avg_30d": round(baseline_daily_avg, 3),
            "baseline_daily_std_30d": round(baseline_daily_std, 3),
            "baseline_72h_avg_30d": round(baseline_daily_avg * 3, 3),
            "growth_rate": round(growth_rate, 3),
            "z_score": round(z_score, 3),
            "paper_burst_score": round(paper_burst_score, 3),
            "github_signal_score": round(github_signal_score, 3),
            "source_diversity_score": round(len(sources) / total_possible_sources, 3),
            "cross_source_confirmation_score": round(cross_source_confirmation_score, 3),
            "institution_concentration_score": round(institution_concentration_score, 3),
            "institution_signal_score": round(institution_signal_score, 3),
            "dataset_signal_score": round(dataset_signal_score, 3),
            "method_signal_score": round(method_signal_score, 3),
            "cold_revival_score": cold_revival_score,
            "paper_count": paper_count,
            "repo_count": repo_count,
            "github_star_delta": github_star_delta,
            "method_mentions": sum(methods.values()),
            "dataset_mentions": sum(datasets.values()),
            "institution_mentions": sum(institutions.values()),
            "burst_score": round(paper_burst_score + github_signal_score + dataset_signal_score + method_signal_score, 3),
            "low_history_confidence": low_history,
        }
        magnitude, label = calculate_magnitude(metrics)
        signals.append(
            {
                "topic": topic,
                "title": f"{topic} 出现{label}",
                "magnitude": magnitude,
                "severity_label": label,
                "summary": build_summary(topic, metrics, label, source_types),
                "calculation_summary": build_calculation_summary(metrics, magnitude),
                "key_drivers": key_drivers(metrics, methods, datasets, institutions),
                "metrics": metrics,
                "evidence": build_evidence(pairs),
                "source_urls": sorted({item.get("source_url") or item.get("url") for item, _ in pairs if item.get("source_url") or item.get("url")}),
                "related_methods": [name for name, _ in methods.most_common(8)],
                "related_datasets": [name for name, _ in datasets.most_common(8)],
                "related_institutions": [name for name, _ in institutions.most_common(8)],
                "suggested_watch_keywords": suggested_keywords(pairs),
                "confidence": confidence,
                "caveats": caveats(low_history, pairs),
                "tags": tags(metrics, source_types, low_history),
                "push_recommended": magnitude >= float(config.thresholds.get("default_push_magnitude", 3.8)),
                "dedupe_key": f"trend:{topic}:{now.date().isoformat()}:{label}",
                "evidence_json_string": json.dumps(build_evidence(pairs), ensure_ascii=False),
            }
        )
    return sorted(signals, key=lambda row: row["magnitude"], reverse=True)


def build_baseline(
    history_snapshots: list[dict[str, Any]],
    *,
    now: datetime,
    exclude_recent_hours: int = 0,
) -> dict[str, dict[str, Any]]:
    by_topic: dict[str, list[int]] = defaultdict(list)
    cutoff = now - timedelta(days=30)
    cutoff_end = now - timedelta(hours=exclude_recent_hours)
    for snapshot in history_snapshots:
        try:
            ts = datetime.fromisoformat(snapshot.get("snapshot_hour", "").replace("Z", "+00:00")).astimezone(UTC)
        except Exception:  # noqa: BLE001
            continue
        if ts < cutoff or ts >= cutoff_end:
            continue
        for hotspot in snapshot.get("top_hotspots", []):
            metrics = hotspot.get("metrics", {})
            by_topic[hotspot.get("topic")].append(int(metrics.get("paper_count", 0)) + int(metrics.get("repo_count", 0)))
    result: dict[str, dict[str, Any]] = {}
    for topic, counts in by_topic.items():
        avg_per_hour = sum(counts) / max(1, len(counts))
        daily_avg = avg_per_hour * 24
        variance = sum((value - avg_per_hour) ** 2 for value in counts) / max(1, len(counts))
        result[topic] = {
            "daily_avg": daily_avg,
            "daily_std": math.sqrt(variance) * 24,
            "samples": len(counts),
        }
    return result


def source_weight(config, source_name: str, source_type: str) -> float:
    for source in config.sources.get("sources", []):
        if source.get("source_name") == source_name or source.get("source_type") == source_type:
            return float(source.get("reliability_weight", 0.75))
    return 0.75


def confidence_score(*, evidence_count: int, source_type_count: int, low_history: bool, partial_sources: int) -> float:
    score = 0.25 + min(0.35, evidence_count * 0.06) + min(0.25, source_type_count * 0.12)
    if low_history:
        score -= 0.15
    score -= min(0.2, partial_sources * 0.08)
    return round(max(0.15, min(0.95, score)), 2)


def build_evidence(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[dict[str, Any]]:
    evidence = []
    for item, match in sorted(pairs, key=lambda pair: pair[1].get("score", 0), reverse=True)[:8]:
        evidence.append(
            {
                "source_type": item.get("source_type"),
                "source_name": item.get("source_name"),
                "title": item.get("title"),
                "source_url": item.get("source_url") or item.get("url"),
                "published_at": item.get("published_at"),
                "match_score": match.get("score"),
                "matched_keywords": match.get("matched_keywords", []),
                "matched_methods": match.get("matched_methods", []),
                "matched_datasets": match.get("matched_datasets", []),
            }
        )
    return evidence


def suggested_keywords(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[str]:
    counter = Counter(keyword for item, _ in pairs for keyword in item.get("extracted_keywords", []))
    return [keyword for keyword, _ in counter.most_common(8)]


def key_drivers(metrics: dict[str, Any], methods: Counter[str], datasets: Counter[str], institutions: Counter[str]) -> list[str]:
    drivers = []
    if metrics["paper_count"]:
        drivers.append(f"论文信号 {metrics['paper_count']} 条")
    if metrics["repo_count"]:
        drivers.append(f"GitHub 项目 {metrics['repo_count']} 个")
    if metrics["github_star_delta"]:
        drivers.append(f"24h star 增量 {metrics['github_star_delta']}")
    if methods:
        drivers.append(f"方法提及：{', '.join(name for name, _ in methods.most_common(3))}")
    if datasets:
        drivers.append(f"数据集/Benchmark：{', '.join(name for name, _ in datasets.most_common(3))}")
    if institutions:
        drivers.append(f"机构集中：{', '.join(name for name, _ in institutions.most_common(3))}")
    if metrics["cold_revival_score"]:
        drivers.append("低基线方向出现冷门复活信号")
    return drivers or ["当前证据较少，建议继续观察"]


def tags(metrics: dict[str, Any], source_types: set[str], low_history: bool) -> list[str]:
    result = []
    if metrics["paper_count"] >= 2:
        result.append("论文暴增")
    if metrics["github_star_delta"] > 0:
        result.append("GitHub 暴涨")
    if metrics["method_mentions"] > 0:
        result.append("方法扩散")
    if metrics["dataset_mentions"] > 0:
        result.append("Benchmark 爆发")
        result.append("数据集升温")
    if metrics["institution_mentions"] > 0:
        result.append("机构集中")
    if metrics["cold_revival_score"]:
        result.append("冷门复活")
    if len(source_types) >= 2:
        result.append("跨源共振")
    if "repo" in source_types:
        result.append("开源驱动")
    if "paper" in source_types:
        result.append("学术推动")
    if low_history:
        result.extend(["低置信度", "历史不足"])
    return result


def caveats(low_history: bool, pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[str]:
    notes = []
    if low_history:
        notes.append("历史样本不足 30 天，基线置信度较低。")
    if not any((item.get("star_history_available") for item, _ in pairs if item.get("source_type") == "repo")):
        notes.append("GitHub star 增量仅在积累 snapshot 后计算，首次运行不会判定 star 暴涨。")
    return notes


def build_summary(topic: str, metrics: dict[str, Any], label: str, source_types: set[str]) -> str:
    sources = "、".join(sorted(source_types)) or "单一来源"
    return (
        f"{topic} 在当前窗口内出现 {metrics['paper_count']} 条论文信号和 "
        f"{metrics['repo_count']} 个 GitHub 项目信号，来源覆盖 {sources}，系统判定为{label}。"
    )


def build_calculation_summary(metrics: dict[str, Any], magnitude: float) -> str:
    return (
        f"magnitude={magnitude}，burst={metrics['burst_score']}，growth_rate={metrics['growth_rate']}，"
        f"z_score={metrics['z_score']}，cross_source={metrics['cross_source_confirmation_score']}。"
    )
