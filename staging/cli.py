"""Unified staging entrypoint (``fdb-stage``).

    fdb-stage                        # stage every source that has raw data
    fdb-stage nflverse               # stage one source
    fdb-stage nflverse:player_stats  # stage specific datasets

Mirrors scrapers/cli.py: each ``<source>`` maps to a staging module exposing
``run(names)``. Only nflverse is implemented.
"""

from __future__ import annotations

import argparse
import importlib
import sys

SOURCES = ["nflverse", "pfr"]


def _parse_target(target: str) -> tuple[str, list[str] | None]:
    if ":" in target:
        source, rest = target.split(":", 1)
        return source, [n for n in rest.split(",") if n]
    return target, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run raw -> staging transforms.")
    parser.add_argument("targets", nargs="*", help="e.g. 'nflverse' or 'nflverse:pbp'.")
    args = parser.parse_args()

    if args.targets:
        requested = [_parse_target(t) for t in args.targets]
    else:
        requested = [(s, None) for s in SOURCES]

    failures = 0
    for source, names in requested:
        if source not in SOURCES:
            print(f"! unknown source: {source}", file=sys.stderr)
            failures += 1
            continue
        print(f"\n=== {source} ===")
        try:
            mod = importlib.import_module(f"staging.{source}")
            failures += int(mod.run(names) or 0)
        except NotImplementedError as err:
            print(f"  (skipped) {err}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
