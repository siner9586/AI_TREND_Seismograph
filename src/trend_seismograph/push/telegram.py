from __future__ import annotations

import os
from typing import Any

import requests


def push_telegram(text: str, *, token: str | None = None, chat_id: str | None = None) -> dict[str, Any]:
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"channel": "telegram", "skipped": True, "reason": "Telegram env not configured"}
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=15,
    )
    return {"channel": "telegram", "skipped": False, "status_code": response.status_code, "ok": response.ok}
