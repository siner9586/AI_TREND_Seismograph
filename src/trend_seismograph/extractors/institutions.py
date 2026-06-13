from __future__ import annotations

from .keywords import contains_phrase


def extract_institutions(text: str, institutions: list[dict]) -> list[str]:
    matches: set[str] = set()
    for institution in institutions:
        aliases = institution.get("aliases") or [institution.get("canonical_name")]
        if any(contains_phrase(text, alias) for alias in aliases if alias):
            matches.add(institution["canonical_name"])
    return sorted(matches)
