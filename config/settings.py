"""Filesystem paths and run-wide settings.

This module is the single source of truth for *where things live* on disk. Every
other package imports paths from here rather than recomputing them, so moving the
data root is a one-line change.

Environment overrides:
  DB_PATH   absolute path to the DuckDB file (default: data/fantasy.duckdb)
  SEASONS   comma-separated seasons for per-season datasets (e.g. "2022,2023")
  DATA_DIR  absolute path to the data root (default: <repo>/data)
"""

from __future__ import annotations

import os
from pathlib import Path

# config/settings.py -> repo root is one level up from this file's package dir.
REPO_ROOT: Path = Path(__file__).resolve().parent.parent

DATA_DIR: Path = Path(os.environ.get("DATA_DIR", REPO_ROOT / "data")).resolve()
RAW_DIR: Path = DATA_DIR / "raw"
STAGING_DIR: Path = DATA_DIR / "staging"
DB_PATH: Path = Path(os.environ.get("DB_PATH", DATA_DIR / "fantasy.duckdb")).resolve()

MIGRATIONS_DIR: Path = REPO_ROOT / "db" / "migrations"
CONFIG_DIR: Path = REPO_ROOT / "config"


def _default_seasons() -> list[int]:
    """Last five seasons. Bump `end` as new seasons complete."""
    end = 2025
    start = end - 4
    return list(range(start, end + 1))


def seasons() -> list[int]:
    """Seasons to ingest for per-season datasets, honoring the SEASONS env var."""
    raw = os.environ.get("SEASONS")
    if not raw:
        return _default_seasons()
    parsed = [int(s.strip()) for s in raw.split(",") if s.strip()]
    return [s for s in parsed if s >= 1999]


def raw_path(source: str, *parts: str) -> Path:
    """Path under data/raw/<source>/... — the untouched source-of-truth layer."""
    return RAW_DIR.joinpath(source, *parts)


def staging_path(table: str, *parts: str) -> Path:
    """Path under data/staging/<table>/... — the cleaned/typed/validated layer."""
    return STAGING_DIR.joinpath(table, *parts)
