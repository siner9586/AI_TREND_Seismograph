from __future__ import annotations

import os
from typing import Any

import requests


def push_webhook(payload: dict[str, Any], url: str | None = None) -> dict[str, Any]:
    target = url or os.getenv("PUSH_WEBHOOK_URL")
    if not target:
        return {"channel": "webhook", "skipped": True, "reason": "PUSH_WEBHOOK_URL not configured"}
    response = requests.post(target, json=payload, timeout=15)
    return {"channel": "webhook", "skipped": False, "status_code": response.status_code, "ok": response.ok}
