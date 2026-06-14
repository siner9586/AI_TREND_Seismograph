from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import urlparse


def enrich_signal_curation(signal: dict[str, Any]) -> dict[str, Any]:
    """Add deterministic, model-free, human-readable curation fields.

    This module deliberately does not call LLMs. It converts structured crawler
    outputs into natural Chinese summaries that are stable, explainable and easy
    to audit. The summary should read like a short editor-written briefing, but
    every sentence must be traceable to metrics, evidence, source URLs and the
    configured taxonomy.
    """

    enriched = dict(signal)
    metrics = enriched.get("metrics") or {}
    evidence = list(enriched.get("evidence") or [])
    source_urls = list(enriched.get("source_urls") or [])
    related_methods = list(enriched.get("related_methods") or [])
    related_datasets = list(enriched.get("related_datasets") or [])
    related_institutions = list(enriched.get("related_institutions") or [])
    watch_keywords = list(enriched.get("suggested_watch_keywords") or [])
    caveats = list(enriched.get("caveats") or [])
    tags = list(enriched.get("tags") or [])

    paper_count = int(metrics.get("paper_count") or metrics.get("current_paper_count") or 0)
    repo_count = int(metrics.get("repo_count") or metrics.get("current_repo_count") or 0)
    star_delta = int(metrics.get("github_star_delta") or 0)
    method_mentions = int(metrics.get("method_mentions") or 0)
    dataset_mentions = int(metrics.get("dataset_mentions") or 0)
    institution_mentions = int(metrics.get("institution_mentions") or 0)
    magnitude = enriched.get("magnitude") or metrics.get("magnitude") or 0
    severity = enriched.get("severity_label") or "趋势波动"
    topic = enriched.get("topic") or "该方向"
    confidence = enriched.get("confidence")

    dominant_source = _dominant_source(paper_count=paper_count, repo_count=repo_count)
    focus_terms = _compact_terms(related_methods + related_datasets + watch_keywords, limit=8)
    institution_terms = _compact_terms(related_institutions, limit=8)
    source_link_groups = build_source_link_groups(evidence=evidence, source_urls=source_urls)
    evidence_digest = build_evidence_digest(evidence)
    representative_titles = _representative_titles(evidence, limit=5)
    source_mix = _source_mix_text(paper_count=paper_count, repo_count=repo_count)
    evidence_mix = _evidence_mix_text(evidence)

    curated_summary = build_curated_summary(
        topic=topic,
        severity=severity,
        magnitude=magnitude,
        confidence=confidence,
        dominant_source=dominant_source,
        source_mix=source_mix,
        evidence_mix=evidence_mix,
        representative_titles=representative_titles,
        related_methods=related_methods,
        related_datasets=related_datasets,
        related_institutions=related_institutions,
        watch_keywords=watch_keywords,
        star_delta=star_delta,
        method_mentions=method_mentions,
        dataset_mentions=dataset_mentions,
        institution_mentions=institution_mentions,
        caveats=caveats,
        tags=tags,
    )

    signal_takeaways = build_overall_takeaways(
        topic=topic,
        severity=severity,
        magnitude=magnitude,
        paper_count=paper_count,
        repo_count=repo_count,
        star_delta=star_delta,
        method_mentions=method_mentions,
        dataset_mentions=dataset_mentions,
        institution_mentions=institution_mentions,
        evidence=evidence,
        related_methods=related_methods,
        related_datasets=related_datasets,
        related_institutions=related_institutions,
        watch_keywords=watch_keywords,
        caveats=caveats,
        tags=tags,
        confidence=confidence,
    )

    enriched["curated_summary"] = _clean_text(curated_summary)
    enriched["signal_takeaways"] = signal_takeaways[:7]
    enriched["source_link_groups"] = source_link_groups
    enriched["evidence_digest"] = evidence_digest
    enriched["signal_focus"] = {
        "dominant_source": dominant_source,
        "source_mix": source_mix,
        "focus_terms": focus_terms,
        "representative_titles": representative_titles,
        "related_institutions": institution_terms,
        "paper_count": paper_count,
        "repo_count": repo_count,
        "github_star_delta": star_delta,
        "method_mentions": method_mentions,
        "dataset_mentions": dataset_mentions,
        "institution_mentions": institution_mentions,
    }
    enriched["curation_method"] = "deterministic_natural_language_v2"
    return enriched


def enrich_signals_curation(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_signal_curation(signal) for signal in signals]


def build_curated_summary(
    *,
    topic: str,
    severity: str,
    magnitude: Any,
    confidence: Any,
    dominant_source: str,
    source_mix: str,
    evidence_mix: str,
    representative_titles: list[str],
    related_methods: list[str],
    related_datasets: list[str],
    related_institutions: list[str],
    watch_keywords: list[str],
    star_delta: int,
    method_mentions: int,
    dataset_mentions: int,
    institution_mentions: int,
    caveats: list[str],
    tags: list[str],
) -> str:
    """Build a readable paragraph summarizing the full captured target set."""

    opening = (
        f"本次抓取围绕「{topic}」相关公开信号进行汇总，系统将其判定为“{severity}”（M{_format_number(magnitude)}）。"
        f"从抓取目标看，当前信号主要来自{dominant_source}，{source_mix}"
    )

    evidence_sentence = ""
    if representative_titles:
        evidence_sentence = (
            f"代表性目标包括{_join_terms(representative_titles, 5)}等，它们构成了本轮判断的主要证据链；"
            f"{evidence_mix}。"
        )
    elif evidence_mix:
        evidence_sentence = f"从证据结构看，{evidence_mix}。"

    star_sentence = ""
    if star_delta > 0:
        star_sentence = f"开源侧 24 小时 star 增量约为 {star_delta}，说明该方向至少在短期工程关注度上出现了可观察的聚集。"
    elif "开源" in dominant_source or "GitHub" in source_mix:
        star_sentence = "当前尚未形成显著 star 增量，但多个项目同时进入抓取窗口，仍说明工程侧正在出现同步试验或主题聚合。"

    method_sentence = ""
    if related_methods:
        method_sentence = f"方法层面，抓取内容集中关联到{_join_terms(related_methods, 6)}等线索，方法提及 {method_mentions} 次，反映出该热点并非单一项目噪声，而是与具体技术路径或工具范式相连。"
    elif method_mentions:
        method_sentence = f"方法相关词共出现 {method_mentions} 次，但尚未形成稳定的高频方法标签，需要继续观察后续快照。"

    dataset_sentence = ""
    if related_datasets:
        dataset_sentence = f"数据集或 Benchmark 层面出现{_join_terms(related_datasets, 6)}等信号，累计提及 {dataset_mentions} 次，可作为判断研究评测侧是否跟进的重要线索。"
    elif dataset_mentions:
        dataset_sentence = f"数据集或 Benchmark 相关信号出现 {dataset_mentions} 次，但目前还没有足够集中到某个明确对象。"

    institution_sentence = ""
    if related_institutions:
        institution_sentence = f"机构与账号层面，相关信号涉及{_join_terms(related_institutions, 8)}，累计提及 {institution_mentions} 次，提示该热点可能存在机构发布、开发者群体或生态账号的集中活动。"
    elif institution_mentions:
        institution_sentence = f"机构相关信号出现 {institution_mentions} 次，但目前尚未形成清晰的集中机构或核心账号。"

    watch_sentence = ""
    if watch_keywords:
        watch_sentence = f"后续应重点观察{_join_terms(watch_keywords, 8)}等词是否继续在论文、repo 和项目描述中同时出现。"

    confidence_sentence = ""
    if confidence is not None:
        confidence_sentence = f"当前置信度为 {_format_number(confidence)}。"
    if caveats:
        confidence_sentence += f"需要注意的是，{caveats[0]}"
    elif "低置信度" in tags or "历史不足" in tags:
        confidence_sentence += "需要注意的是，历史基线仍在积累，当前结论更适合作为短期预警，而不是长期趋势定论。"

    return "".join(
        part
        for part in [
            opening,
            evidence_sentence,
            star_sentence,
            method_sentence,
            dataset_sentence,
            institution_sentence,
            watch_sentence,
            confidence_sentence,
        ]
        if part
    )


def build_overall_takeaways(
    *,
    topic: str,
    severity: str,
    magnitude: Any,
    paper_count: int,
    repo_count: int,
    star_delta: int,
    method_mentions: int,
    dataset_mentions: int,
    institution_mentions: int,
    evidence: list[dict[str, Any]],
    related_methods: list[str],
    related_datasets: list[str],
    related_institutions: list[str],
    watch_keywords: list[str],
    caveats: list[str],
    tags: list[str],
    confidence: Any,
) -> list[str]:
    """Summarize multiple captured targets into overall conclusions."""

    conclusions: list[str | None] = [
        (
            f"总体判断：{topic} 本轮由论文 {paper_count} 条、GitHub 项目 {repo_count} 个共同构成观测基础，"
            f"当前强度为“{severity}”（M{_format_number(magnitude)}）。这说明系统捕获到的不是孤立条目，而是一组围绕同一方向聚合的公开信号。"
        ),
        _conclusion_content_focus(evidence=evidence, related_methods=related_methods, related_datasets=related_datasets, watch_keywords=watch_keywords),
        _conclusion_engineering(repo_count=repo_count, star_delta=star_delta, related_methods=related_methods),
        _conclusion_research(paper_count=paper_count, related_datasets=related_datasets, method_mentions=method_mentions, dataset_mentions=dataset_mentions),
        _conclusion_institution(related_institutions=related_institutions, institution_mentions=institution_mentions),
        _conclusion_evidence(evidence=evidence),
        _conclusion_next_step(watch_keywords=watch_keywords, caveats=caveats, tags=tags, confidence=confidence),
    ]
    return _dedupe_keep_order(conclusions)


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

    return {key: value[:10] for key, value in groups.items() if value}


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


def _conclusion_content_focus(
    *, evidence: list[dict[str, Any]], related_methods: list[str], related_datasets: list[str], watch_keywords: list[str]
) -> str | None:
    titles = _representative_titles(evidence, limit=4)
    focus_terms = _compact_terms(related_methods + related_datasets + watch_keywords, limit=6)
    if titles and focus_terms:
        return f"内容重点：抓取到的多个目标集中指向{_join_terms(focus_terms, 6)}等线索，代表条目包括{_join_terms(titles, 4)}，说明该热点已经从关键词命中延伸到具体项目、论文或工具对象。"
    if titles:
        return f"内容重点：代表条目包括{_join_terms(titles, 4)}，这些目标共同构成当前热点的主要观察对象。"
    if focus_terms:
        return f"内容重点：当前抓取内容主要围绕{_join_terms(focus_terms, 6)}等词展开，后续需要观察这些词是否持续共现。"
    return None


def _conclusion_engineering(*, repo_count: int, star_delta: int, related_methods: list[str]) -> str | None:
    if repo_count <= 0:
        return None
    if star_delta > 0:
        return f"工程侧归纳：本轮包含 {repo_count} 个 GitHub 项目，24 小时 star 增量约 {star_delta}，说明该方向在开源生态中已出现可量化的短期关注度。"
    method_tail = f"，并与{_join_terms(related_methods, 4)}等方法线索相连" if related_methods else ""
    return f"工程侧归纳：本轮包含 {repo_count} 个 GitHub 项目{method_tail}。即便 star 增量尚不明显，多个项目同时出现也说明该方向正在发生工程侧试验或工具化探索。"


def _conclusion_research(
    *, paper_count: int, related_datasets: list[str], method_mentions: int, dataset_mentions: int
) -> str | None:
    if paper_count <= 0 and not related_datasets and not method_mentions and not dataset_mentions:
        return None
    if paper_count > 0:
        dataset_part = f"，并出现{_join_terms(related_datasets, 4)}等数据集/Benchmark 线索" if related_datasets else ""
        return f"研究侧归纳：本轮包含 {paper_count} 条论文信号{dataset_part}，可用于判断该热点是否从工程讨论进入研究问题、实验设计或评测基准层面。"
    return f"研究侧归纳：虽然论文条目不足，但方法相关提及 {method_mentions} 次、数据集/Benchmark 相关提及 {dataset_mentions} 次，说明仍有研究线索值得跟踪。"


def _conclusion_institution(*, related_institutions: list[str], institution_mentions: int) -> str | None:
    if not related_institutions and not institution_mentions:
        return None
    if related_institutions:
        return f"机构与账号归纳：相关信号涉及{_join_terms(related_institutions, 6)}，累计提及 {institution_mentions} 次。该信息更适合作为生态活跃度线索，不宜直接解释为机构正式战略判断。"
    return f"机构与账号归纳：机构相关信号出现 {institution_mentions} 次，但目前还没有形成稳定的集中对象。"


def _conclusion_evidence(evidence: list[dict[str, Any]]) -> str | None:
    if not evidence:
        return None
    counter = Counter(item.get("source_type") or "source" for item in evidence)
    mix = "、".join(f"{name} {count} 条" for name, count in counter.most_common())
    return f"证据链归纳：代表性证据覆盖 {mix}。下方信号链接保留原始来源，便于回看每个判断所依据的项目、论文或网页。"


def _conclusion_next_step(*, watch_keywords: list[str], caveats: list[str], tags: list[str], confidence: Any) -> str | None:
    watch = f"后续重点观察{_join_terms(watch_keywords, 8)}是否继续出现" if watch_keywords else "后续重点观察该方向是否继续出现跨窗口重复信号"
    confidence_part = f"当前置信度为 {_format_number(confidence)}，" if confidence is not None else ""
    if caveats:
        return f"观察建议：{watch}。{confidence_part}同时需要注意：{caveats[0]}"
    if "低置信度" in tags or "历史不足" in tags:
        return f"观察建议：{watch}。{confidence_part}由于历史样本仍在积累，当前更适合作为短期预警，而不是长期趋势定论。"
    return f"观察建议：{watch}。如果后续 3-7 天仍能同时看到项目、论文、方法词或机构账号信号，该热点的趋势可信度才会进一步提高。"


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


def _source_mix_text(*, paper_count: int, repo_count: int) -> str:
    parts = []
    if paper_count:
        parts.append(f"论文 {paper_count} 条")
    if repo_count:
        parts.append(f"GitHub 项目 {repo_count} 个")
    if not parts:
        return "当前窗口内缺少可拆分的论文或项目计数。"
    return "当前窗口内捕获到" + "、".join(parts) + "。"


def _evidence_mix_text(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return ""
    counter = Counter(item.get("source_type") or "source" for item in evidence)
    return "代表性证据覆盖" + "、".join(f"{name} {count} 条" for name, count in counter.most_common())


def _representative_titles(evidence: list[dict[str, Any]], *, limit: int) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        title = str(item.get("title") or _link_label(str(item.get("source_url") or ""))).strip()
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        titles.append(title)
        if len(titles) >= limit:
            break
    return titles


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
        return f"命中 {'、'.join(terms)}，匹配分 {score}，因此被纳入本轮代表性证据。"
    if terms:
        return f"命中 {'、'.join(terms)}，因此被纳入本轮代表性证据。"
    if score is not None:
        return f"匹配分 {score}，因此被纳入本轮代表性证据。"
    return "被纳入本轮代表性证据。"


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
        text = _clean_text(str(value))
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
    return rows


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.1f}"
