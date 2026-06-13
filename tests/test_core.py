from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from trend_seismograph.analytics.anomaly import detect_anomalies
from trend_seismograph.analytics.cooccurrence import build_cooccurrence_graph
from trend_seismograph.analytics.github_growth import apply_star_deltas, save_repo_snapshots
from trend_seismograph.analytics.magnitude import calculate_magnitude, severity_label
from trend_seismograph.analytics.scoring import enrich_items
from trend_seismograph.analytics.watchlist import detect_watchlist_hits
from trend_seismograph.extractors.datasets import extract_datasets
from trend_seismograph.extractors.institutions import extract_institutions
from trend_seismograph.extractors.methods import extract_methods
from trend_seismograph.extractors.topics import match_topics
from trend_seismograph.push import push_hotspots
from trend_seismograph.storage.file_store import FileStore, write_json
from trend_seismograph.storage.neon_store import NeonStore
from trend_seismograph.storage.schema import validate_hotspot_schema, validate_report_schema


def mini_config(tmp_path):
    return SimpleNamespace(
        data_dir=tmp_path,
        sources={"sources": [{"source_name": "arxiv", "source_type": "paper", "enabled": True, "reliability_weight": 0.86}, {"source_name": "github", "source_type": "repo", "enabled": True, "reliability_weight": 0.82}]},
        taxonomy={
            "topics": [
                {
                    "canonical_name": "World Model",
                    "aliases": ["world model"],
                    "include_keywords": ["world model"],
                    "exclude_keywords": [],
                    "related_methods": ["World Model"],
                    "related_datasets": ["Open X-Embodiment"],
                    "related_tasks": ["robotics"],
                    "related_models": [],
                    "priority_weight": 1.0,
                },
                {
                    "canonical_name": "AI Coding",
                    "aliases": ["coding agent"],
                    "include_keywords": ["coding agent", "SWE-bench"],
                    "exclude_keywords": [],
                    "related_methods": ["Tool Use"],
                    "related_datasets": ["SWE-bench"],
                    "related_tasks": ["coding"],
                    "related_models": [],
                    "priority_weight": 1.0,
                },
            ]
        },
        methods={"methods": ["World Model", "Tool Use"]},
        datasets={"datasets": ["Open X-Embodiment", "SWE-bench"]},
        institutions={"institutions": [{"canonical_name": "OpenAI", "aliases": ["OpenAI"], "weight": 1.0}]},
        watchlist={
            "watchlists": [
                {
                    "name": "AI Coding 观察",
                    "topics": ["AI Coding"],
                    "keywords": ["SWE-bench"],
                    "threshold_magnitude": 2.0,
                    "threshold_growth_rate": 0.1,
                    "push_enabled": True,
                }
            ]
        },
        thresholds={"default_push_magnitude": 3.0},
    )


def sample_items():
    return [
        {
            "source_type": "paper",
            "source_name": "arxiv",
            "title": "World model for robotics with Open X-Embodiment",
            "abstract_or_description": "A world model improves robotics planning with OpenAI style evaluation.",
            "url": "https://arxiv.org/abs/1",
            "source_url": "https://arxiv.org/abs/1",
            "published_at": "2026-06-13T10:00:00Z",
        },
        {
            "source_type": "repo",
            "source_name": "github",
            "title": "org/coding-agent",
            "full_name": "org/coding-agent",
            "abstract_or_description": "A coding agent for SWE-bench with tool use.",
            "url": "https://github.com/org/coding-agent",
            "source_url": "https://github.com/org/coding-agent",
            "stars": 100,
            "topics": ["llm", "coding-agent"],
        },
    ]


def test_magnitude_calculation():
    magnitude, label = calculate_magnitude(
        {
            "paper_burst_score": 3,
            "github_signal_score": 1,
            "institution_signal_score": 0.5,
            "dataset_signal_score": 0.3,
            "method_signal_score": 0.2,
            "cross_source_confirmation_score": 1,
            "cold_revival_score": 0,
        }
    )
    assert magnitude >= 3
    assert label in {"明显异常", "疑似爆发", "强趋势震荡"}
    assert severity_label(1.5) == "微弱波动"


def test_taxonomy_and_extractors(tmp_path):
    config = mini_config(tmp_path)
    text = "A World Model for robotics using Open X-Embodiment from OpenAI"
    assert extract_methods(text, config.methods["methods"]) == ["World Model"]
    assert extract_datasets(text, config.datasets["datasets"]) == ["Open X-Embodiment"]
    assert extract_institutions(text, config.institutions["institutions"]) == ["OpenAI"]
    matches = match_topics(text, config.taxonomy["topics"], methods=["World Model"], datasets=["Open X-Embodiment"])
    assert matches[0].topic == "World Model"


def test_anomaly_score_with_evidence(tmp_path):
    config = mini_config(tmp_path)
    enriched = enrich_items(sample_items(), config)
    signals = detect_anomalies(enriched, config=config, history_snapshots=[], now=datetime(2026, 6, 13, 10, tzinfo=UTC), window_hours=24)
    assert signals
    assert all(signal["evidence"][0]["source_url"] for signal in signals)
    assert any(signal["topic"] == "AI Coding" for signal in signals)


def test_github_star_delta(tmp_path):
    old = [{"source_type": "repo", "full_name": "org/repo", "stars": 10, "forks": 1, "watchers": 2, "open_issues": 0}]
    save_repo_snapshots(tmp_path, old, "2026-06-12T10:00:00+00:00")
    current = [{"source_type": "repo", "full_name": "org/repo", "stars": 25}]
    apply_star_deltas(tmp_path, current, datetime(2026, 6, 13, 10, tzinfo=UTC))
    assert current[0]["star_delta_24h"] == 15


def test_cooccurrence_graph(tmp_path):
    config = mini_config(tmp_path)
    enriched = enrich_items(sample_items(), config)
    graph = build_cooccurrence_graph(enriched, window_label="2026-06-13")
    assert graph["nodes"]
    assert any(node["label"] == "World Model" for node in graph["nodes"])


def test_watchlist_hit(tmp_path):
    config = mini_config(tmp_path)
    enriched = enrich_items(sample_items(), config)
    signals = detect_anomalies(enriched, config=config, history_snapshots=[], now=datetime(2026, 6, 13, 10, tzinfo=UTC))
    hits = detect_watchlist_hits(signals, config.watchlist)
    assert hits
    assert hits[0]["push_enabled"] is True


def test_report_and_hourly_schema():
    evidence = [{"source_url": "https://example.com", "title": "x"}]
    hotspot = {
        "snapshot_hour": "2026-06-13T10",
        "generated_at": "2026-06-13T10:01:00Z",
        "run_id": "r",
        "mode": "hourly",
        "top_hotspots": [{"topic": "AI Coding", "magnitude": 3.2, "severity_label": "明显异常", "evidence": evidence}],
        "source_status": [{"source_name": "test", "ok": True}],
        "partial": False,
    }
    assert validate_hotspot_schema(hotspot) == []
    report = {
        "report_date": "2026-06-13",
        "generated_at": "2026-06-13T10:01:00Z",
        "run_id": "r",
        "mode": "daily",
        "top_anomalies": [{"topic": "AI Coding", "magnitude": 3.2, "severity_label": "明显异常", "evidence": evidence}],
        "raw_sources_summary": {"source_status": []},
        "confidence_summary": {},
        "caveats": [],
    }
    assert validate_report_schema(report) == []


def test_file_idempotent_skip(tmp_path):
    store = FileStore(tmp_path)
    snapshot = {
        "snapshot_hour": "2026-06-13T10",
        "generated_at": "x",
        "run_id": "r",
        "mode": "hourly",
        "top_hotspots": [],
        "source_status": [],
        "partial": False,
    }
    assert store.save_hourly(snapshot)[0] is True
    assert store.save_hourly(snapshot)[0] is False


def test_push_dedupe(tmp_path, monkeypatch):
    store = FileStore(tmp_path)
    hotspot = {
        "topic": "AI Coding",
        "magnitude": 3.2,
        "severity_label": "明显异常",
        "summary": "出现异常波动",
        "key_drivers": [],
        "source_urls": ["https://example.com"],
        "dedupe_key": "hotspot:ai-coding",
        "push_recommended": True,
    }
    store.save_hourly(
        {
            "snapshot_hour": "2026-06-13T10",
            "generated_at": "x",
            "run_id": "r",
            "mode": "hourly",
            "top_hotspots": [hotspot],
            "source_status": [],
            "partial": False,
        },
        force=True,
    )
    write_json(
        tmp_path / "push_events.json",
        {"events": [{"dedupe_key": "hotspot:ai-coding", "pushed_at": datetime.now(UTC).isoformat()}]},
    )
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    result = push_hotspots(store)
    assert result["skipped"][0]["reason"] == "deduped within 24h"


def test_neon_fallback_without_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
    result = NeonStore().sync([])
    assert result.enabled is False
    assert result.ok is False
