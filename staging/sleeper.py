"""sleeper raw -> staging.

Reads ``data/raw/sleeper/players/snapshot_date=YYYY-MM-DD/*.parquet`` and writes
a cleaned, typed table to ``data/staging/sleeper_players/`` partitioned by
snapshot_date. Every snapshot is kept (history), so the crosswalk can be rebuilt
as of any date; the dbt layer reads only the latest snapshot.

Cleaning here: keep the native + foreign IDs as VARCHAR (NULLing blanks/"0"),
type the bio columns, and drop rows without a full_name (team DSTs, placeholders)
since those can't anchor a real player_id.
"""

from __future__ import annotations

import argparse
import sys
import time

from config.settings import RAW_DIR
from scrapers.base import memory_duckdb
from staging.base import has_raw, write_partitioned

# Foreign IDs to carry through. NULLIF '' and '0' so junk values don't become
# crosswalk rows. (opta_id / pandascore_id are always empty for NFL — skipped.)
_ID_COLS = [
    "gsis_id",
    "espn_id",
    "yahoo_id",
    "rotowire_id",
    "rotoworld_id",
    "sportradar_id",
    "stats_id",
    "swish_id",
    "fantasy_data_id",
    "oddsjam_id",
]


def _select() -> str:
    glob = (RAW_DIR / "sleeper" / "players" / "**" / "*.parquet").as_posix()
    id_exprs = ",\n        ".join(
        f"nullif(nullif(cast({c} as varchar), ''), '0') as {c}" for c in _ID_COLS
    )
    return f"""
        select
        cast(player_id as varchar)                  as sleeper_id,
        {id_exprs},
        nullif(first_name, '')                      as first_name,
        nullif(last_name, '')                       as last_name,
        nullif(full_name, '')                       as full_name,
        nullif(position, '')                        as position,
        nullif(team, '')                            as team,
        try_cast(age as integer)                    as age,
        try_cast(nullif(birth_date, '') as date)    as birth_date,
        nullif(college, '')                         as college,
        try_cast(nullif(cast(height as varchar), '') as integer) as height_inches,
        try_cast(nullif(cast(weight as varchar), '') as integer) as weight_lbs,
        try_cast(years_exp as integer)              as years_exp,
        nullif(status, '')                          as status,
        cast(active as boolean)                     as active,
        try_cast(search_rank as integer)            as search_rank,
        nullif(depth_chart_position, '')            as depth_chart_position,
        try_cast(depth_chart_order as integer)      as depth_chart_order,
        try_cast(number as integer)                 as jersey_number,
        snapshot_date
        from read_parquet('{glob}', hive_partitioning = true, union_by_name = true)
        where nullif(full_name, '') is not null
    """


def stage() -> int:
    """Stage the sleeper players snapshots. Returns rows written."""
    if not has_raw("sleeper", "players"):
        raise FileNotFoundError("No raw sleeper data — run `fdb-ingest sleeper` first.")
    with memory_duckdb() as conn:
        return write_partitioned(conn, _select(), "sleeper_players", ["snapshot_date"])


def run(names: list[str] | None = None, *_a, **_k) -> int:
    """Stage sleeper players (the source has one dataset; `names` is ignored)."""
    print("-> sleeper_players ... ", end="", flush=True)
    started = time.monotonic()
    try:
        rows = stage()
        print(f"{rows:,} rows in {time.monotonic() - started:.1f}s")
        return 0
    except Exception as err:  # noqa: BLE001 - reported, surfaced as failure count
        print("FAILED")
        print(f"   {str(err).splitlines()[0]}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage sleeper raw -> data/staging/.")
    parser.parse_args()
    return run(None)


if __name__ == "__main__":
    sys.exit(main())
