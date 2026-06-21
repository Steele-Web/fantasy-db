"""Unified scraper entrypoint (``fdb-ingest``).

    fdb-ingest                       # run every enabled source's scraper
    fdb-ingest nflverse              # run one source
    fdb-ingest nflverse:player_stats # run specific nflverse datasets
    fdb-ingest --list                # show sources and their status

Each ``<source>`` maps to a module in this package exposing ``run(names)``. Only
nflverse is implemented; the rest raise NotImplementedError until built.
"""

from __future__ import annotations

import argparse
import importlib
import sys

import config

SOURCES = ["nflverse", "pfr", "ngs", "vegas", "fantasypros", "sleeper"]


def _parse_target(target: str) -> tuple[str, list[str] | None]:
    """'nflverse:pbp,player_stats' -> ('nflverse', ['pbp', 'player_stats'])."""
    if ":" in target:
        source, rest = target.split(":", 1)
        return source, [n for n in rest.split(",") if n]
    return target, None


def _enabled(source: str) -> bool:
    return bool(config.sources().get("sources", {}).get(source, {}).get("enabled", False))


def run_source(source: str, names: list[str] | None) -> int:
    mod = importlib.import_module(f"scrapers.{source}")
    result = mod.run(names)
    return int(result or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run source scrapers into data/raw/.")
    parser.add_argument(
        "targets",
        nargs="*",
        help="Sources, e.g. 'nflverse' or 'nflverse:pbp,player_stats' (default: enabled).",
    )
    parser.add_argument("--list", action="store_true", help="List sources and enabled status.")
    args = parser.parse_args()

    if args.list:
        print("Sources (enable in config/sources.yaml):\n")
        for s in SOURCES:
            print(f"  [{'on ' if _enabled(s) else 'off'}] {s}")
        return 0

    if args.targets:
        requested = [_parse_target(t) for t in args.targets]
    else:
        requested = [(s, None) for s in SOURCES if _enabled(s)]
        if not requested:
            print("No sources enabled in config/sources.yaml. Pass a source name explicitly.")
            return 0

    failures = 0
    for source, names in requested:
        if source not in SOURCES:
            print(f"! unknown source: {source}", file=sys.stderr)
            failures += 1
            continue
        print(f"\n=== {source} ===")
        try:
            failures += run_source(source, names)
        except NotImplementedError as err:
            print(f"  (skipped) {err}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
