from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import urlparse


def enrich_signal_curation(signal: dict[str, Any]) -> dict[str, Any]:
    """Add deterministic, model-free summaries for UI and downstream reports.

    The goal is not to rewrite the trend signal with generative AI. Instead, it
    turns existing structured fields into stable, explainable reading aids:
    - curated_summary: one concise paragraph for the hotspot card.
    - signal_takeaways: 3-6 bullet points explaining what was captured.
    - source_link_groups: grouped links for papers, repos, method/data evidence.
    - signal_focus: compact metadata for UI filtering and future APIs.
    """

    enriched = dict(signal)
    metrics = enriched.get("metrics") or {}
    evidence = list(enriched.get("evidence") or [])
    source_urls = list(enriched.get("source_urls") or [])
    key_drivers = list(enriched.get("key_drivers") or [])
    related_methods = list(enriched.get("related_methods") or [])
    related_datasets = list(enriched.get("related_datasets") or [])
    related_institutions = list(enriched.get("related_institutions") or [])
    watch_keywords = list(enriched.get("suggested_watch_keywords") or [])
    caveats = list(enriched.get("caveats") or [])

    paper_count = int(metrics.get("paper_count") or metrics.get("current_paper_count") or 0)
    repo_count = int(metrics.get("repo_count") or metrics.get("current_repo_count") or 0)
    star_delta = int(metrics.get("github_star_delta") or 0)
    method_mentions = int(metrics.get("method_mentions") or 0)
    dataset_mentions = int(metrics.get("dataset_mentions") or 0)
    institution_mentions = int(metrics.get("institution_mentions") or 0)
    magnitude = enriched.get("magnitude") or metrics.get("magnitude") or 0
    severity = enriched.get("severity_label") or "趋势波动"
    topic = enriched.get("topic") or "该方向"

    dominant_source = _dominant_source(paper_count=paper_count, repo_count=repo_count)
    focus_terms = _compact_terms(related_methods + related_datasets + watch_keywords, limit=6)
    institution_terms = _compact_terms(related_institutions, limit=6)
    source_mix = _source_mix_sentence(paper_count=paper_count, repo_count=repo_count)
    method_dataset_sentence = _method_dataset_sentence(
        related_methods=related_methods,
        related_datasets=related_datasets,
        method_mentions=method_mentions,
        dataset_mentions=dataset_mentions,
    )
    institution_sentence = _institution_sentence(
        related_institutions=related_institutions,
        institution_mentions=institution_mentions,
    )

    curated_summary = (
        f"{topic} 当前被判定为“{severity}”（M{_format_number(magnitude)}）。"
        f"本轮信号主要来自{dominant_source}，{source_mix}"
        f"{_star_sentence(star_delta)}"
        f"{method_dataset_sentence}"
        f"{institution_sentence}"
        f"该结论由结构化抓取字段自动生成，适合用于判断短期关注度变化、工程生态试验强度和后续观察优先级。"
    )

    signal_takeaways = _dedupe_keep_order(
        [
            _takeaway_source_mix(paper_count=paper_count, repo_count=repo_count),
            _takeaway_star_delta(star_delta),
            _takeaway_methods(related_methods, method_mentions),
            _takeaway_datasets(related_datasets, dataset_mentions),
            _takeaway_institutions(related_institutions, institution_mentions),
            _takeaway_evidence(evidence),
            _takeaway_confidence(metrics, caveats),
            _takeaway_watch_keywords(watch_keywords),
        ]
    )

    source_link_groups = build_source_link_groups(evidence=evidence, source_urls=source_urls)
    evidence_digest = build_evidence_digest(evidence)

    enriched["curated_summary"] = " ".join(curated_summary.split())
    enriched["signal_takeaways"] = signal_takeaways[:6]
    enriched["source_link_groups"] = source_link_groups
    enriched["evidence_digest"] = evidence_digest
    enriched["signal_focus"] = {
        "dominant_source": dominant_source,
        "focus_terms": focus_terms,
        "related_institutions": institution_terms,
        "paper_count": paper_count,
        "repo_count": repo_count,
        "github_star_delta": star_delta,
        "method_mentions": method_mentions,
        "dataset_mentions": dataset_mentions,
        "institution_mentions": institution_mentions,
    }
    enriched["curation_method"] = "deterministic_rules_v1"
    return enriched


def enrich_signals_curation(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_signal_curation(signal) for signal in signals]


def build_source_link_groups(*, evidence: list[dict[str, Any]], source_urls: list[str]) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = {
        "代表项目": [],
        "论文来源": [],
        "方法与数据集信号": [],
        "其他信号": [],
    }

    seen: set[str] = set()
    for item in evidence:
        url = item.get("source_url")
        if not url or url in seen:
            continue
        seen.add(url)
        group = _group_for_evidence(item)
        groups[group].append(
            {
                "title": str(item.get("title") or _link_label(url)),
                "url": str(url),
                "source": str(item.get("source_name") or item.get("source_type") or "source"),
                "reason": _reason_for_evidence(item),
            }
        )

    for url in source_urls:
        if not url or url in seen:
            continue
        seen.add(url)
        group = _group_for_url(url)
        groups[group].append(
            {
                "title": _link_label(url),
                "url": str(url),
                "source": _source_name_from_url(url),
                "reason": "关联到该热点的原始信号链接。",
            }
        )

    return {key: value[:8] for key, value in groups.items() if value}


def build_evidence_digest(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    digest = []
    for item in evidence[:8]:
        keywords = _compact_terms(
            list(item.get("matched_keywords") or [])
            + list(item.get("matched_methods") or [])
            + list(item.get("matched_datasets") or []),
            limit=8,
        )
        digest.append(
            {
                "title": item.get("title") or item.get("source_url"),
                "source_url": item.get("source_url"),
                "source_type": item.get("source_type"),
                "source_name": item.get("source_name"),
                "match_score": item.get("match_score"),
                "matched_terms": keywords,
                "why_included": _reason_for_evidence(item),
            }
        )
    return digest


def _dominant_source(*, paper_count: int, repo_count: int) -> str:
    if repo_count and paper_count:
        if repo_count > paper_count * 2:
            return "开源项目，并伴随少量论文信号"
        if paper_count > repo_count * 2:
            return "论文发布，并伴随少量开源项目信号"
        return "论文与开源项目的共同信号"
    if repo_count:
        return "开源项目"
    if paper_count:
        return "论文发布"
    return "公开抓取信号"


def _source_mix_sentence(*, paper_count: int, repo_count: int) -> str:
    parts = []
    if paper_count:
        parts.append(f"论文 {paper_count} 条")
    if repo_count:
        parts.append(f"GitHub 项目 {repo_count} 个")
    if not parts:
        return "当前窗口内缺少可拆分的论文或项目计数。"
    return "当前窗口内捕获到" + "、".join(parts) + "。"


def _star_sentence(star_delta: int) -> str:
    if star_delta > 0:
        return f"相关项目 24 小时 star 增量合计约 {star_delta}，说明短期工程关注度出现集中变化。"
    return "当前未观察到显著 24 小时 star 增量，仍需结合后续小时快照判断持续性。"


def _method_dataset_sentence(*, related_methods: list[str], related_datasets: list[str], method_mentions: int, dataset_mentions: int) -> str:
    sentences = []
    if related_methods:
        sentences.append(f"方法侧集中在{_join_terms(related_methods, 5)}等关键词，累计方法提及 {method_mentions} 次。")
    elif method_mentions:
        sentences.append(f"方法相关词出现 {method_mentions} 次，但当前未形成稳定方法标签。")
    if related_datasets:
        sentences.append(f"数据集/Benchmark 侧出现{_join_terms(related_datasets, 5)}等信号，累计提及 {dataset_mentions} 次。")
    elif dataset_mentions:
        sentences.append(f"数据集/Benchmark 相关词出现 {dataset_mentions} 次，但暂未形成高频标签。")
    return "".join(sentences)


def _institution_sentence(*, related_institutions: list[str], institution_mentions: int) -> str:
    if related_institutions:
        return f"机构或账号信号主要涉及{_join_terms(related_institutions, 5)}，相关提及 {institution_mentions} 次。"
    if institution_mentions:
        return f"机构相关信号出现 {institution_mentions} 次，但当前未形成明确集中对象。"
    return ""


def _takeaway_source_mix(*, paper_count: int, repo_count: int) -> str | None:
    if paper_count or repo_count:
        return f"信号来源结构：论文 {paper_count} 条，GitHub 项目 {repo_count} 个。"
    return "当前热点主要来自结构化匹配结果，但缺少可拆分的论文/项目计数。"


def _takeaway_star_delta(star_delta: int) -> str | None:
    if star_delta > 0:
        return f"开源热度：相关项目 24 小时 star 增量约 {star_delta}，可作为工程生态升温的短期指标。"
    return None


def _takeaway_methods(related_methods: list[str], method_mentions: int) -> str | None:
    if related_methods:
        return f"方法线索：{_join_terms(related_methods, 6)}；方法提及 {method_mentions} 次。"
    return None


def _takeaway_datasets(related_datasets: list[str], dataset_mentions: int) -> str | None:
    if related_datasets:
        return f"数据集/Benchmark 线索：{_join_terms(related_datasets, 6)}；相关提及 {dataset_mentions} 次。"
    return None


def _takeaway_institutions(related_institutions: list[str], institution_mentions: int) -> str | None:
    if related_institutions:
        return f"机构/账号线索：{_join_terms(related_institutions, 6)}；相关提及 {institution_mentions} 次。"
    return None


def _takeaway_evidence(evidence: list[dict[str, Any]]) -> str | None:
    if not evidence:
        return None
    counter = Counter(item.get("source_type") or "source" for item in evidence)
    mix = "、".join(f"{name} {count} 条" for name, count in counter.most_common())
    return f"证据链：代表性信号覆盖 {mix}，可点击下方链接回看原始来源。"


def _takeaway_confidence(metrics: dict[str, Any], caveats: list[str]) -> str | None:
    if metrics.get("low_history_confidence"):
        return "置信度提示：历史样本不足，当前判断更适合作为短期预警，需连续观察 3-7 天。"
    if caveats:
        return f"边界提示：{caveats[0]}"
    return None


def _takeaway_watch_keywords(watch_keywords: list[str]) -> str | None:
    if watch_keywords:
        return f"后续观察词：{_join_terms(watch_keywords, 8)}。"
    return None


def _group_for_evidence(item: dict[str, Any]) -> str:
    source_type = item.get("source_type")
    if source_type == "repo":
        return "代表项目"
    if source_type == "paper":
        return "论文来源"
    if item.get("matched_methods") or item.get("matched_datasets"):
        return "方法与数据集信号"
    return _group_for_url(str(item.get("source_url") or ""))


def _group_for_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "github.com" in host:
        return "代表项目"
    if "arxiv.org" in host or "doi.org" in host:
        return "论文来源"
    return "其他信号"


def _reason_for_evidence(item: dict[str, Any]) -> str:
    terms = _compact_terms(
        list(item.get("matched_keywords") or [])
        + list(item.get("matched_methods") or [])
        + list(item.get("matched_datasets") or []),
        limit=6,
    )
    score = item.get("match_score")
    if terms and score is not None:
        return f"命中 {'、'.join(terms)}，匹配分 {score}。"
    if terms:
        return f"命中 {'、'.join(terms)}。"
    if score is not None:
        return f"纳入代表性证据，匹配分 {score}。"
    return "纳入代表性证据。"


def _source_name_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    if "github.com" in host:
        return "github"
    if "arxiv.org" in host:
        return "arxiv"
    return host or "source"


def _link_label(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.strip("/")
    if "github.com" in host and path:
        parts = path.split("/")
        if len(parts) >= 2:
            return "/".join(parts[:2])
    if "arxiv.org" in host and path:
        return "arXiv " + path.split("/")[-1]
    return path or host or url


def _compact_terms(values: list[Any], *, limit: int) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        terms.append(text)
        if len(terms) >= limit:
            break
    return terms


def _join_terms(values: list[Any], limit: int) -> str:
    return "、".join(_compact_terms(values, limit=limit))


def _dedupe_keep_order(values: list[str | None]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        text = " ".join(str(value).split())
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
    return rows


def _format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.1f}"
