from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any


def render_rss(hotspots: list[dict[str, Any]], *, site_url: str, title: str = "AI 趋势地震仪热点") -> str:
    items = []
    for hotspot in hotspots[:30]:
        link = f"{site_url.rstrip('/')}/trends/{hotspot.get('topic', '').replace(' ', '%20')}"
        description = escape(hotspot.get("summary", ""))
        items.append(
            f"""
    <item>
      <title>{escape('M' + str(hotspot.get('magnitude', 0)) + ' ' + hotspot.get('topic', ''))}</title>
      <link>{escape(link)}</link>
      <guid>{escape(hotspot.get('dedupe_key', link))}</guid>
      <pubDate>{datetime.now(UTC).strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>
      <description>{description}</description>
    </item>""".strip()
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{escape(title)}</title>
    <link>{escape(site_url)}</link>
    <description>AI research and engineering trend anomaly signals</description>
    <lastBuildDate>{datetime.now(UTC).strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
    {chr(10).join(items)}
  </channel>
</rss>
"""


def write_rss(path: Path, hotspots: list[dict[str, Any]], *, site_url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_rss(hotspots, site_url=site_url), encoding="utf-8")
