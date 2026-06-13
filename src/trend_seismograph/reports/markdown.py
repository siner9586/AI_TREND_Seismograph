from __future__ import annotations

from typing import Any


def render_daily_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# AI 趋势地震仪日报 {report['report_date']}",
        "",
        f"- 生成时间：{report.get('generated_at')}",
        f"- 扫描论文：{report.get('total_papers_scanned', 0)}",
        f"- 扫描 GitHub 项目：{report.get('total_repos_scanned', 0)}",
        f"- 跟踪方向：{report.get('total_topics_tracked', 0)}",
        f"- 最高震级：M{report.get('max_magnitude', 0)}",
        "",
        "## Top 趋势异常",
        "",
    ]
    if not report.get("top_anomalies"):
        lines.extend(["当前窗口没有形成可解释趋势异常。", ""])
    for anomaly in report.get("top_anomalies", []):
        lines.extend(
            [
                f"### M{anomaly['magnitude']} {anomaly['topic']}：{anomaly['severity_label']}",
                "",
                anomaly.get("summary", ""),
                "",
                f"- 解释：{anomaly.get('calculation_summary', '')}",
                f"- 关键驱动：{'；'.join(anomaly.get('key_drivers', [])) or '暂无'}",
                f"- 建议观察：{', '.join(anomaly.get('suggested_watch_keywords', [])) or '暂无'}",
                "",
                "证据链：",
            ]
        )
        for evidence in anomaly.get("evidence", [])[:5]:
            lines.append(f"- [{evidence.get('title')}]({evidence.get('source_url')}) · {evidence.get('source_name')} · match={evidence.get('match_score')}")
        if anomaly.get("caveats"):
            lines.extend(["", "注意："])
            for caveat in anomaly.get("caveats", []):
                lines.append(f"- {caveat}")
        lines.append("")
    lines.extend(["## Watchlist", ""])
    for hit in report.get("watchlist", {}).get("hits", []):
        lines.append(f"- {hit['watchlist_name']} / {hit['topic']}：M{hit['magnitude']}，{hit['reason']}")
    if not report.get("watchlist", {}).get("hits"):
        lines.append("- 当前没有 Watchlist 命中。")
    lines.extend(["", "## 数据源状态", ""])
    for status in report.get("raw_sources_summary", {}).get("source_status", []):
        ok = "ok" if status.get("ok") else "failed"
        lines.append(f"- {status.get('source_name')}: {ok}, items={status.get('items', 0)}, partial={status.get('partial', False)}")
    lines.extend(["", "## Caveats", ""])
    for caveat in report.get("caveats", []):
        lines.append(f"- {caveat}")
    return "\n".join(lines).strip() + "\n"
