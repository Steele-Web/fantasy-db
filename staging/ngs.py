"""ngs raw -> staging.

Reads ``data/raw/ngs/<type>/all.parquet`` and writes a cleaned, de-duplicated
table to ``data/staging/ngs_<type>/`` partitioned by season. The season-total
rows (week = 0) are dropped here so the dbt layer joins purely on weekly grain.
"""

from __future__ import annotations

import argparse
import sys
import time

from config.settings import RAW_DIR
from scrapers.base import memory_duckdb
from staging.base import has_raw, write_partitioned

TYPES = ["passing", "rushing", "receiving"]


def _select(ngs_type: str) -> str:
    glob = (RAW_DIR / "ngs" / ngs_type / "**" / "*.parquet").as_posix()
    return (
        f"SELECT DISTINCT * FROM read_parquet('{glob}', union_by_name = true) "
        f"WHERE season IS NOT NULL AND week >= 1"
    )


def stage_type(ngs_type: str) -> int:
    if ngs_type not in TYPES:
        raise ValueError(f"Unknown ngs type {ngs_type!r}")
    if not has_raw("ngs", ngs_type):
        raise FileNotFoundError(
            f"No raw ngs/{ngs_type} — run `fdb-ingest ngs:{ngs_type}` first."
        )
    with memory_duckdb() as conn:
        return write_partitioned(conn, _select(ngs_type), f"ngs_{ngs_type}", ["season"])


def run(names: list[str] | None = None, *_a, **_k) -> int:
    """Stage the named NGS types (or every one with raw present)."""
    targets = names or [t for t in TYPES if has_raw("ngs", t)]
    if not targets:
        print("  no raw ngs datasets found to stage.", file=sys.stderr)
        return 0

    failures = 0
    for ngs_type in targets:
        print(f"-> ngs_{ngs_type} ... ", end="", flush=True)
        started = time.monotonic()
        try:
            rows = stage_type(ngs_type)
            print(f"{rows:,} rows in {time.monotonic() - started:.1f}s")
        except Exception as err:  # noqa: BLE001 - reported, surfaced as failure count
            failures += 1
            print("FAILED")
            print(f"   {str(err).splitlines()[0]}", file=sys.stderr)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage ngs raw -> data/staging/.")
    parser.add_argument("types", nargs="*", help="NGS types (default: all present)")
    args = parser.parse_args()
    return 1 if run(args.types or None) else 0


if __name__ == "__main__":
    sys.exit(main())
