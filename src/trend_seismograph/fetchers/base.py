from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import requests

DEFAULT_USER_AGENT = "AI-Trend-Seismograph/0.1 (research trend monitor; contact: repo owner)"


@dataclass
class FetchResult:
    source_name: str
    source_type: str
    items: list[dict[str, Any]] = field(default_factory=list)
    ok: bool = True
    error: str | None = None
    partial: bool = False
    fetched_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def status(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_type": self.source_type,
            "ok": self.ok,
            "error": self.error,
            "items": len(self.items),
            "partial": self.partial,
            "fetched_at": self.fetched_at,
        }


class BaseFetcher:
    source_name = "base"
    source_type = "unknown"

    def __init__(self, user_agent: str | None = None, timeout_seconds: int = 20):
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def get_json(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, retries: int = 3) -> Any:
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout_seconds)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(f"{response.status_code}: {response.text[:200]}", response=response)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(min(8, 2**attempt))
        raise RuntimeError(f"GET {url} failed after retries: {last_error}") from last_error

    def get_text(self, url: str, *, params: dict[str, Any] | None = None, retries: int = 3) -> str:
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout_seconds)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(f"{response.status_code}: {response.text[:200]}", response=response)
                response.raise_for_status()
                return response.text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(min(8, 2**attempt))
        raise RuntimeError(f"GET {url} failed after retries: {last_error}") from last_error


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").replace("\n", " ").split())
