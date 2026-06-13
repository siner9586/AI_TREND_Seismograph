from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from .base import BaseFetcher, FetchResult, normalize_text, stable_hash


class GitHubFetcher(BaseFetcher):
    source_name = "github"
    source_type = "repo"

    def __init__(self, token: str | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.token = token or os.getenv("GITHUB_TOKEN")
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.session.headers.update({"Accept": "application/vnd.github+json"})

    def fetch(self, *, start: datetime, end: datetime, queries: list[str], max_per_query: int = 8) -> FetchResult:
        fetched_at = datetime.now(UTC).isoformat()
        since = (end - timedelta(days=7)).date().isoformat()
        seen: set[str] = set()
        items: list[dict[str, Any]] = []
        errors: list[str] = []
        for query in queries:
            q = f"{query} created:>={since} pushed:>={since}"
            params = {"q": q, "sort": "stars", "order": "desc", "per_page": max_per_query}
            try:
                payload = self.get_json("https://api.github.com/search/repositories", params=params)
                for repo in payload.get("items", []):
                    full_name = repo.get("full_name")
                    if not full_name or full_name in seen:
                        continue
                    seen.add(full_name)
                    items.append(self._repo_to_item(repo, fetched_at=fetched_at))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{query}: {exc}")
        return FetchResult(
            self.source_name,
            self.source_type,
            items,
            ok=not errors,
            error="; ".join(errors) if errors else None,
            partial=bool(errors),
            fetched_at=fetched_at,
        )

    def _repo_to_item(self, repo: dict[str, Any], *, fetched_at: str) -> dict[str, Any]:
        description = normalize_text(repo.get("description"))
        topics = repo.get("topics") or []
        full_name = repo["full_name"]
        raw = {
            "id": repo.get("id"),
            "full_name": full_name,
            "description": description,
            "topics": topics,
            "language": repo.get("language"),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "watchers": repo.get("watchers_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
            "pushed_at": repo.get("pushed_at"),
            "url": repo.get("html_url"),
        }
        return {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "external_id": str(repo.get("id")),
            "title": full_name,
            "repo_name": repo.get("name"),
            "full_name": full_name,
            "owner": (repo.get("owner") or {}).get("login"),
            "abstract_or_description": description,
            "authors": [(repo.get("owner") or {}).get("login")],
            "authors_json": json.dumps([(repo.get("owner") or {}).get("login")], ensure_ascii=False),
            "institutions": [(repo.get("owner") or {}).get("login")],
            "institutions_json": json.dumps([(repo.get("owner") or {}).get("login")], ensure_ascii=False),
            "url": repo.get("html_url"),
            "source_url": repo.get("html_url"),
            "published_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
            "pushed_at": repo.get("pushed_at"),
            "fetched_at": fetched_at,
            "raw_json": raw,
            "raw_json_string": json.dumps(raw, ensure_ascii=False),
            "content_hash": stable_hash(raw),
            "dedupe_key": f"github:{full_name}",
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "watchers": repo.get("watchers_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "topics": topics,
            "language": repo.get("language"),
            "source_reliability_weight": 0.82,
        }
