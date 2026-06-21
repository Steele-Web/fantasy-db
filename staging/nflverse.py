"""nflverse raw -> staging.

Reads ``data/raw/nflverse/<dataset>/...`` and writes cleaned, de-duplicated
output to ``data/staging/nflverse_<dataset>/`` partitioned by season (and week
when the dataset is weekly). dbt models then read these staging tables.

Implemented for the weekly datasets that feed the headline marts. Datasets
without a `week` column fall back to season-only partitioning.
"""

from __future__ import annotations

import argparse
import sys
import time

from scrapers.base import memory_duckdb
from staging.base import has_raw, raw_glob, write_partitioned

# Datasets we know how to stage and how they partition. "week" datasets get
# season=YYYY/week=WW; the rest get season=YYYY.
WEEKLY = ["player_stats", "pbp", "snap_counts", "weekly_rosters", "injuries", "depth_charts"]
SEASONAL = ["rosters"]
STAGEABLE = WEEKLY + SEASONAL

# Datasets whose rows are already unique on a natural key, so the de-dupe pass is
# skipped. pbp in particular is ~370 columns wide; a full-row DISTINCT hashes every
# column and exhausts memory, while play rows are already unique on (game_id, play_id).
_SKIP_DEDUP = {"pbp"}


def _select(source_glob: str, partition_cols: list[str], *, distinct: bool = True) -> str:
    """Clean read: optionally drop exact-duplicate rows and require partition keys to
    be non-null (rows we can't place in a partition are dropped)."""
    not_null = " AND ".join(f"{c} IS NOT NULL" for c in partition_cols)
    dedup = "DISTINCT " if distinct else ""
    return (
        f"SELECT {dedup}* FROM read_parquet('{source_glob}', union_by_name = true) "
        f"WHERE {not_null}"
    )


def stage_dataset(dataset: str) -> int:
    """Stage one nflverse dataset. Returns rows written."""
    if dataset not in STAGEABLE:
        raise ValueError(f"Don't know how to stage nflverse dataset {dataset!r}")
    if not has_raw("nflverse", dataset):
        raise FileNotFoundError(
            f"No raw data for {dataset} — run `fdb-ingest nflverse:{dataset}` first."
        )
    partition_cols = ["season", "week"] if dataset in WEEKLY else ["season"]
    table = f"nflverse_{dataset}"
    with memory_duckdb() as conn:
        select_sql = _select(
            raw_glob("nflverse", dataset), partition_cols, distinct=dataset not in _SKIP_DEDUP
        )
        rows = write_partitioned(conn, select_sql, table, partition_cols)
    if dataset == "pbp":
        # Re-attach the v_pbp view now that staged files exist.
        from db.connection import refresh_pbp_view

        refresh_pbp_view()
    return rows


def run(names: list[str] | None, *_a, **_k) -> int:
    """Stage the named datasets (or every stageable one with raw present)."""
    if names:
        targets = names
    else:
        targets = [d for d in STAGEABLE if has_raw("nflverse", d)]
        if not targets:
            print("  no raw nflverse datasets found to stage.", file=sys.stderr)
            return 0

    failures = 0
    for dataset in targets:
        print(f"-> nflverse_{dataset} ... ", end="", flush=True)
        started = time.monotonic()
        try:
            rows = stage_dataset(dataset)
            print(f"{rows:,} rows in {time.monotonic() - started:.1f}s")
        except Exception as err:
            failures += 1
            print("FAILED")
            print(f"   {str(err).splitlines()[0]}", file=sys.stderr)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage nflverse raw -> data/staging/.")
    parser.add_argument(
        "datasets",
        nargs="*",
        help=f"Datasets (default: all present). Stageable: {', '.join(STAGEABLE)}",
    )
    args = parser.parse_args()
    return 1 if run(args.datasets or None) else 0


if __name__ == "__main__":
    sys.exit(main())
