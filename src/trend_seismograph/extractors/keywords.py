from __future__ import annotations

import re
from collections import Counter

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "using",
    "via",
    "into",
    "over",
    "under",
    "based",
    "model",
    "models",
    "learning",
    "neural",
    "large",
    "language",
    "paper",
    "github",
}


def normalize_for_match(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def contains_phrase(text: str, phrase: str) -> bool:
    lowered = normalize_for_match(text)
    phrase_lower = normalize_for_match(phrase)
    if not phrase_lower:
        return False
    if re.search(r"[^\w\s-]", phrase_lower):
        return phrase_lower in lowered
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase_lower)}(?![a-z0-9])", lowered) is not None


def extract_keywords(text: str, *, limit: int = 18) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text)
    counter = Counter(word.lower() for word in words if word.lower() not in STOPWORDS)
    phrases: Counter[str] = Counter()
    tokens = [word.lower() for word in words if word.lower() not in STOPWORDS]
    for i in range(len(tokens) - 1):
        phrase = f"{tokens[i]} {tokens[i + 1]}"
        if len(phrase) >= 8:
            phrases[phrase] += 1
    combined = counter + phrases
    return [term for term, _ in combined.most_common(limit)]
