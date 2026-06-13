from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"


@dataclass(frozen=True)
class AppConfig:
    repo_root: Path
    config_dir: Path
    data_dir: Path
    sources: dict[str, Any]
    taxonomy: dict[str, Any]
    institutions: dict[str, Any]
    methods: dict[str, Any]
    datasets: dict[str, Any]
    watchlist: dict[str, Any]
    thresholds: dict[str, Any]


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in {path}")
    return loaded


def load_config(repo_root: Path | None = None) -> AppConfig:
    root = repo_root or REPO_ROOT
    config_dir = root / "config"
    data_dir = root / "data"
    return AppConfig(
        repo_root=root,
        config_dir=config_dir,
        data_dir=data_dir,
        sources=load_yaml(config_dir / "sources.yml"),
        taxonomy=load_yaml(config_dir / "trend_taxonomy.yml"),
        institutions=load_yaml(config_dir / "institutions.yml"),
        methods=load_yaml(config_dir / "methods.yml"),
        datasets=load_yaml(config_dir / "datasets.yml"),
        watchlist=load_yaml(config_dir / "watchlist.yml"),
        thresholds=load_yaml(config_dir / "thresholds.yml"),
    )


def ensure_data_dirs(data_dir: Path) -> None:
    for relative in [
        "raw",
        "snapshots",
        "hotspots",
        "reports",
        "graphs/cooccurrence",
        "history",
    ]:
        (data_dir / relative).mkdir(parents=True, exist_ok=True)
