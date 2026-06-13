from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any


def build_cooccurrence_graph(items: list[dict[str, Any]], *, window_label: str) -> dict[str, Any]:
    node_counts: Counter[str] = Counter()
    node_types: dict[str, str] = {}
    edge_counts: Counter[tuple[str, str]] = Counter()
    for item in items:
        terms: list[tuple[str, str]] = []
        for topic in item.get("matched_topics", [])[:3]:
            terms.append((topic["topic"], "topic"))
        for method in item.get("extracted_methods", [])[:5]:
            terms.append((method, "method"))
        for dataset in item.get("extracted_datasets", [])[:5]:
            terms.append((dataset, "dataset"))
        for keyword in item.get("extracted_keywords", [])[:8]:
            terms.append((keyword, "keyword"))
        unique_terms = sorted(set(terms), key=lambda row: row[0].lower())[:14]
        for label, term_type in unique_terms:
            node_counts[label] += 1
            node_types[label] = term_type
        for left, right in combinations([label for label, _ in unique_terms], 2):
            edge_counts[tuple(sorted((left, right)))] += 1
    nodes = [
        {
            "id": safe_id(label),
            "label": label,
            "type": node_types.get(label, "keyword"),
            "count": count,
            "weight": round(min(1.0, 0.2 + count / max(1, max(node_counts.values(), default=1))), 3),
        }
        for label, count in node_counts.most_common(60)
    ]
    allowed = {node["label"] for node in nodes}
    edges = [
        {
            "source": safe_id(left),
            "target": safe_id(right),
            "cooccurrence_count": count,
            "weight": round(min(1.0, count / max(1, max(edge_counts.values(), default=1))), 3),
            "windows": [window_label],
        }
        for (left, right), count in edge_counts.most_common(100)
        if left in allowed and right in allowed and count > 1
    ]
    return {"window": window_label, "nodes": nodes, "edges": edges}


def safe_id(label: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in label).strip("-")
