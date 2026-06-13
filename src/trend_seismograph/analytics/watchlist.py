from __future__ import annotations

from typing import Any

from trend_seismograph.extractors.keywords import contains_phrase


def detect_watchlist_hits(signals: list[dict[str, Any]], watchlist_config: dict[str, Any]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for watchlist in watchlist_config.get("watchlists", []):
        topics = set(watchlist.get("topics", []))
        keywords = watchlist.get("keywords", [])
        threshold_magnitude = float(watchlist.get("threshold_magnitude", 3.5))
        threshold_growth = float(watchlist.get("threshold_growth_rate", 0))
        for signal in signals:
            topic_match = signal["topic"] in topics
            keyword_text = " ".join(signal.get("suggested_watch_keywords", []) + signal.get("key_drivers", []))
            keyword_match = any(contains_phrase(keyword_text, keyword) for keyword in keywords)
            growth_match = signal.get("metrics", {}).get("growth_rate", 0) >= threshold_growth
            magnitude_match = signal.get("magnitude", 0) >= threshold_magnitude
            if topic_match and (magnitude_match or keyword_match or growth_match):
                hit = {
                    "watchlist_name": watchlist["name"],
                    "topic": signal["topic"],
                    "magnitude": signal["magnitude"],
                    "severity_label": signal["severity_label"],
                    "threshold_magnitude": threshold_magnitude,
                    "threshold_growth_rate": threshold_growth,
                    "push_enabled": bool(watchlist.get("push_enabled", False)),
                    "reason": reason(magnitude_match, keyword_match, growth_match),
                    "evidence": signal.get("evidence", [])[:3],
                    "dedupe_key": f"watchlist:{watchlist['name']}:{signal['topic']}:{signal['severity_label']}",
                }
                hits.append(hit)
                signal.setdefault("tags", []).append("Watchlist 命中")
                if hit["push_enabled"]:
                    signal["push_recommended"] = True
    return hits


def reason(magnitude_match: bool, keyword_match: bool, growth_match: bool) -> str:
    parts = []
    if magnitude_match:
        parts.append("震级超过阈值")
    if keyword_match:
        parts.append("关键词命中")
    if growth_match:
        parts.append("增长率超过阈值")
    return "、".join(parts) or "topic 命中"
