from __future__ import annotations

from trend_seismograph.reports.curation import enrich_signal_curation


def test_enrich_signal_curation_adds_stable_summary_fields() -> None:
    signal = {
        "topic": "Agents",
        "magnitude": 5.2,
        "severity_label": "强趋势震荡",
        "metrics": {
            "paper_count": 1,
            "repo_count": 3,
            "github_star_delta": 120,
            "method_mentions": 2,
            "dataset_mentions": 0,
            "institution_mentions": 4,
            "low_history_confidence": True,
        },
        "related_methods": ["MCP"],
        "related_datasets": [],
        "related_institutions": ["Anthropic", "OpenAI"],
        "suggested_watch_keywords": ["agent", "workflow"],
        "evidence": [
            {
                "source_type": "repo",
                "source_name": "github",
                "title": "example/agent-repo",
                "source_url": "https://github.com/example/agent-repo",
                "match_score": 0.91,
                "matched_keywords": ["agent"],
                "matched_methods": ["MCP"],
            },
            {
                "source_type": "paper",
                "source_name": "arxiv",
                "title": "Agent Paper",
                "source_url": "https://arxiv.org/abs/2606.00001",
                "match_score": 0.82,
                "matched_keywords": ["agent"],
            },
        ],
        "source_urls": ["https://github.com/example/agent-repo", "https://arxiv.org/abs/2606.00001"],
        "caveats": ["历史样本不足 30 天，基线置信度较低。"],
    }

    enriched = enrich_signal_curation(signal)

    assert enriched["curation_method"] == "deterministic_natural_language_v2"
    assert "本次抓取围绕「Agents」" in enriched["curated_summary"]
    assert "example/agent-repo" in enriched["curated_summary"]
    assert "GitHub 项目 3 个" in enriched["signal_takeaways"][0]
    assert enriched["signal_takeaways"][0].startswith("总体判断")
    assert "代表项目" in enriched["source_link_groups"]
    assert "论文来源" in enriched["source_link_groups"]
    assert enriched["source_link_groups"]["代表项目"][0]["url"] == "https://github.com/example/agent-repo"
    assert enriched["evidence_digest"][0]["matched_terms"] == ["agent", "MCP"]
    assert enriched["signal_focus"]["representative_titles"] == ["example/agent-repo", "Agent Paper"]
