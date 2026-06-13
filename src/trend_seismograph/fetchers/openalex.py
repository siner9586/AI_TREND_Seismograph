from __future__ import annotations

from datetime import datetime

from .base import FetchResult


class OpenAlexFetcher:
    source_name = "openalex"
    source_type = "paper"

    def fetch(self, *, start: datetime, end: datetime) -> FetchResult:
        return FetchResult(
            self.source_name,
            self.source_type,
            [],
            ok=True,
            error="OpenAlex enhancement is disabled in MVP config unless explicitly enabled.",
        )
