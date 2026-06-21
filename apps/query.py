"""Example read script (``fdb-query``) — confirms the pipeline is queryable.

Lists what's in the DB, then (if nflverse player_stats has been staged) prints the
top receivers for the latest staged season straight from the staging Parquet.
Adapt freely; real apps live in the sibling app packages.
"""

from __future__ import annotations

import sys

from config.settings import staging_path
from db.connection import connect, query


def _has_staged_player_stats() -> bool:
    return any(staging_path("nflverse_player_stats").glob("**/*.parquet"))


def main() -> int:
    with connect() as conn:
        tables = query(
            conn,
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY 1;",
        )
        names = [t["name"] for t in tables]
        print("Tables:", ", ".join(names) if names else "(none — run `fdb-migrate`)")

        if not _has_staged_player_stats():
            print(
                "\nNo staged player_stats yet. Run:\n"
                "  fdb-ingest nflverse:player_stats\n"
                "  fdb-stage  nflverse:player_stats"
            )
            return 0

        glob = (staging_path("nflverse_player_stats") / "**" / "*.parquet").as_posix()
        print("\nTop 10 receivers by receiving yards (latest staged season):\n")
        rows = query(
            conn,
            f"""
            with src as (
                select * from read_parquet('{glob}', hive_partitioning = true, union_by_name = true)
            ),
            latest as (select max(season) as s from src)
            select
                player_display_name as player,
                recent_team         as team,
                sum(receptions)     as rec,
                sum(receiving_yards) as rec_yds,
                sum(receiving_tds)  as rec_td
            from src, latest
            where src.season = latest.s
            group by 1, 2
            order by rec_yds desc
            limit 10;
            """,
        )
        _print_table(rows)
    return 0


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("(no rows)")
        return
    cols = list(rows[0].keys())
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    header = "  ".join(c.ljust(widths[c]) for c in cols)
    print(header)
    print("  ".join("-" * widths[c] for c in cols))
    for r in rows:
        print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))


if __name__ == "__main__":
    sys.exit(main())
