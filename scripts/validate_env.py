from __future__ import annotations

import os

OPTIONAL = [
    "DATABASE_URL",
    "NEON_DATABASE_URL",
    "GITHUB_TOKEN",
    "SEMANTIC_SCHOLAR_API_KEY",
    "OPENALEX_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASS",
    "PUSH_WEBHOOK_URL",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "PUBLIC_SITE_URL",
]


def main() -> int:
    for name in OPTIONAL:
        status = "set" if os.getenv(name) else "not set"
        print(f"{name}: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
