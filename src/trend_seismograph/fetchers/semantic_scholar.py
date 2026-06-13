from __future__ import annotations

from datetime import datetime

from .base import FetchResult


class SemanticScholarFetcher:
    source_name = "semantic_scholar"
    source_type = "paper"

    def fetch(self, *, start: datetime, end: datetime) -> FetchResult:
        return FetchResult(
            self.source_name,
            self.source_type,
            [],
            ok=True,
            error="Semantic Scholar enhancement is disabled in MVP config unless SEMANTIC_SCHOLAR_API_KEY is configured.",
        )
