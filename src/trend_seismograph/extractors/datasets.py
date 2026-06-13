from __future__ import annotations

from .keywords import contains_phrase


def extract_datasets(text: str, datasets: list[str]) -> list[str]:
    return sorted({dataset for dataset in datasets if contains_phrase(text, dataset)})
