from __future__ import annotations

from .keywords import contains_phrase


def extract_methods(text: str, methods: list[str]) -> list[str]:
    return sorted({method for method in methods if contains_phrase(text, method)})
