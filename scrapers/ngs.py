"""NFL Next Gen Stats scraper.

NGS is distributed via nflverse releases as one Parquet asset per stat type
(passing/rushing/receiving) covering every season, so — like scrapers.nflverse —
"scraping" is a remote read copied into the raw layer over httpfs.

Raw layout written here:
    data/raw/ngs/<type>/all.parquet    (one file per type, all seasons)

The files carry a season-total row (week = 0) alongside the weekly rows; that's
kept as-is in raw and filtered out in staging.
"""

from __future__ import annotations

import argparse
import sys
import time

from config.settings import raw_path
from scrapers.base import memory_duckdb, source_config, write_parquet

_RELEASE = source_config("ngs").get(
    "release_base",
    "https://github.com/nflverse/nflverse-data/releases/download",
)

TYPES = ["passing", "rushing", "receiving"]


def _url(ngs_type: str) -> str:
    return f"{_RELEASE}/nextgen_stats/ngs_{ngs_type}.parquet"


def run(names: list[str] | None, *_a, **_k) -> int:
    """Scrape the named NGS types (or all). Returns the number of failures."""
    targets = names or TYPES
    unknown = [n for n in targets if n not in TYPES]
    for n in unknown:
        print(f"  ! unknown ngs type: {n}", file=sys.stderr)
    targets = [n for n in targets if n in TYPES]

    failures = 0
    for ngs_type in targets:
        print(f"-> {ngs_type} ... ", end="", flush=True)
        started = time.monotonic()
        try:
            out = raw_path("ngs", ngs_type, "all.parquet")
            with memory_duckdb() as conn:
                rows = write_parquet(
                    conn, f"SELECT * FROM read_parquet('{_url(ngs_type)}')", out
                )
            print(f"{rows:,} rows in {time.monotonic() - started:.1f}s")
        except Exception as err:
            failures += 1
            print("FAILED")
            print(f"   {str(err).splitlines()[0]}", file=sys.stderr)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape NGS datasets into data/raw/ngs/.")
    parser.add_argument("types", nargs="*", help="NGS types (default: all)")
    args = parser.parse_args()
    return 1 if run(args.types or None) else 0


if __name__ == "__main__":
    sys.exit(main())
