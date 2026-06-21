"""Project configuration: filesystem paths (settings.py) and YAML rule files.

YAML files in this directory describe *league/business* config (scoring, leagues,
source rate limits). Load them with the helpers below; load paths and seasons
from `config.settings`.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

_DIR = Path(__file__).resolve().parent


@cache
def load_yaml(name: str) -> dict[str, Any]:
    """Load and cache a YAML config file by stem (e.g. "scoring", "leagues")."""
    path = _DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No config file: {path}")
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def scoring() -> dict[str, Any]:
    """League scoring formats (config/scoring.yaml)."""
    return load_yaml("scoring")


def leagues() -> dict[str, Any]:
    """Your specific leagues (config/leagues.yaml)."""
    return load_yaml("leagues")


def sources() -> dict[str, Any]:
    """Scraper config and rate limits (config/sources.yaml)."""
    return load_yaml("sources")
