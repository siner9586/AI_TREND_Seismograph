from __future__ import annotations

from dataclasses import dataclass

from .keywords import contains_phrase


@dataclass(frozen=True)
class TopicMatch:
    topic: str
    score: float
    matched_keywords: list[str]
    matched_methods: list[str]
    matched_datasets: list[str]
    matched_models: list[str]
    matched_tasks: list[str]


def match_topics(
    text: str,
    topics: list[dict],
    *,
    methods: list[str] | None = None,
    datasets: list[str] | None = None,
) -> list[TopicMatch]:
    method_set = set(methods or [])
    dataset_set = set(datasets or [])
    matches: list[TopicMatch] = []
    for topic in topics:
        include_keywords = topic.get("include_keywords") or []
        aliases = topic.get("aliases") or []
        exclude_keywords = topic.get("exclude_keywords") or []
        if any(contains_phrase(text, keyword) for keyword in exclude_keywords):
            continue
        keyword_hits = sorted({kw for kw in [*include_keywords, *aliases] if contains_phrase(text, kw)})
        method_hits = sorted(set(topic.get("related_methods") or []) & method_set)
        dataset_hits = sorted(set(topic.get("related_datasets") or []) & dataset_set)
        model_hits = sorted({m for m in topic.get("related_models") or [] if contains_phrase(text, m)})
        task_hits = sorted({task for task in topic.get("related_tasks") or [] if contains_phrase(text, task)})
        raw_score = (
            len(keyword_hits) * 1.0
            + len(method_hits) * 0.5
            + len(dataset_hits) * 0.55
            + len(model_hits) * 0.45
            + len(task_hits) * 0.25
        )
        if raw_score <= 0:
            continue
        score = min(1.0, raw_score / 3.0) * float(topic.get("priority_weight", 1.0))
        matches.append(
            TopicMatch(
                topic=topic["canonical_name"],
                score=round(score, 3),
                matched_keywords=keyword_hits,
                matched_methods=method_hits,
                matched_datasets=dataset_hits,
                matched_models=model_hits,
                matched_tasks=task_hits,
            )
        )
    return sorted(matches, key=lambda item: item.score, reverse=True)
