from __future__ import annotations

import html
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from typing import Any

from .base import BaseFetcher, FetchResult, normalize_text, stable_hash

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


class ArxivFetcher(BaseFetcher):
    source_name = "arxiv"
    source_type = "paper"

    def fetch(self, *, start: datetime, end: datetime, categories: list[str], max_results: int = 80) -> FetchResult:
        fetched_at = datetime.now(UTC).isoformat()
        try:
            parts = [f"cat:{category}" for category in categories]
            search_query = "+OR+".join(parts)
            params = {
                "search_query": search_query,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "start": 0,
                "max_results": max_results,
            }
            text = self.get_text("https://export.arxiv.org/api/query", params=params)
            root = ET.fromstring(text)
            items: list[dict[str, Any]] = []
            for entry in root.findall(f"{ATOM}entry"):
                item = self._entry_to_item(entry, fetched_at=fetched_at)
                published = parse_datetime(item.get("published_at"))
                updated = parse_datetime(item.get("updated_at"))
                if published and published > end + timedelta(days=1):
                    continue
                # arXiv can be sparse on weekends; keep recent API results but flag actual time in metadata.
                if published and updated and max(published, updated) < start - timedelta(days=7):
                    continue
                items.append(item)
            time.sleep(3.1)
            return FetchResult(self.source_name, self.source_type, items, ok=True, fetched_at=fetched_at)
        except Exception as exc:  # noqa: BLE001
            return FetchResult(self.source_name, self.source_type, [], ok=False, error=str(exc), partial=True, fetched_at=fetched_at)

    def _entry_to_item(self, entry: ET.Element, *, fetched_at: str) -> dict[str, Any]:
        arxiv_id_url = text_of(entry, f"{ATOM}id")
        external_id = arxiv_id_url.rsplit("/", 1)[-1]
        title = normalize_text(html.unescape(text_of(entry, f"{ATOM}title")))
        summary = normalize_text(html.unescape(text_of(entry, f"{ATOM}summary")))
        authors = [normalize_text(text_of(author, f"{ATOM}name")) for author in entry.findall(f"{ATOM}author")]
        categories = [category.attrib.get("term") for category in entry.findall(f"{ATOM}category") if category.attrib.get("term")]
        url = arxiv_id_url
        pdf = entry.find(f"{ATOM}link[@title='pdf']")
        if pdf is not None and pdf.attrib.get("href"):
            url = pdf.attrib["href"].replace("/pdf/", "/abs/").removesuffix(".pdf")
        raw = {
            "id": arxiv_id_url,
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "published": text_of(entry, f"{ATOM}published"),
            "updated": text_of(entry, f"{ATOM}updated"),
            "url": url,
        }
        content_hash = stable_hash({"title": title, "summary": summary, "authors": authors})
        return {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "external_id": external_id,
            "title": title,
            "abstract_or_description": summary,
            "authors": authors,
            "authors_json": json.dumps(authors, ensure_ascii=False),
            "institutions": [],
            "institutions_json": "[]",
            "url": url,
            "source_url": url,
            "published_at": text_of(entry, f"{ATOM}published"),
            "updated_at": text_of(entry, f"{ATOM}updated"),
            "fetched_at": fetched_at,
            "raw_json": raw,
            "raw_json_string": json.dumps(raw, ensure_ascii=False),
            "content_hash": content_hash,
            "dedupe_key": f"arxiv:{external_id}",
            "categories": categories,
            "source_reliability_weight": 0.86,
        }


def text_of(node: ET.Element, path: str) -> str:
    child = node.find(path)
    return child.text.strip() if child is not None and child.text else ""


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def arxiv_enabled_from_env() -> bool:
    return os.getenv("DISABLE_ARXIV", "").lower() not in {"1", "true", "yes"}
