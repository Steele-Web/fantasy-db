"""nflverse scraper — the one fully-wired source.

nflverse publishes parquet/csv assets on GitHub releases
(https://github.com/nflverse/nflverse-data/releases). DuckDB's httpfs extension
reads those URLs directly, so "scraping" is just a remote read copied into the
raw layer — no manual download/parse step.

Raw layout written here:
    data/raw/nflverse/<dataset>/season=<YYYY>/data.parquet   (per-season sets)
    data/raw/nflverse/<dataset>/all.parquet                  (single-file sets)

To add a dataset: confirm the asset URL exists on the releases page, then add a
DATASETS entry. Per-season sets supply one URL per configured season.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from config.settings import raw_path, seasons
from scrapers.base import memory_duckdb, source_config, write_parquet

_RELEASE = source_config("nflverse").get(
    "release_base",
    "https://github.com/nflverse/nflverse-data/releases/download",
)


@dataclass(frozen=True)
class Dataset:
    name: str
    description: str
    fmt: str                       # "parquet" | "csv"
    per_season: bool
    url: Callable[[int | None], str]


def _release(path: str) -> str:
    return f"{_RELEASE}/{path}"


DATASETS: list[Dataset] = [
    Dataset(
        "players",
        "Master player table (ids, bio, positions) across all eras",
        "parquet",
        False,
        lambda _y: _release("players/players.parquet"),
    ),
    Dataset(
        "schedules",
        "Game/schedule results, lines and metadata (all seasons)",
        "csv",
        False,
        lambda _y: "https://github.com/nflverse/nfldata/raw/master/data/games.csv",
    ),
    Dataset(
        "player_stats",
        "Weekly player stats (offense + kicking + defense), per season",
        "parquet",
        True,
        # nflverse migrated weekly stats from the legacy `player_stats/player_stats_<y>`
        # asset (offense-only, 53 cols, no 2025) to the combined `stats_player`
        # release (115 cols incl. game_id, kicking, IDP) covering 2018+.
        lambda y: _release(f"stats_player/stats_player_week_{y}.parquet"),
    ),
    Dataset(
        "pbp",
        "Play-by-play (nflfastR), per season — large",
        "parquet",
        True,
        lambda y: _release(f"pbp/play_by_play_{y}.parquet"),
    ),
    Dataset(
        "rosters",
        "Season rosters, per season",
        "parquet",
        True,
        lambda y: _release(f"rosters/roster_{y}.parquet"),
    ),
    Dataset(
        "weekly_rosters",
        "Week-by-week rosters, per season",
        "parquet",
        True,
        lambda y: _release(f"weekly_rosters/roster_weekly_{y}.parquet"),
    ),
    Dataset(
        "snap_counts",
        "Player snap counts, per season",
        "parquet",
        True,
        lambda y: _release(f"snap_counts/snap_counts_{y}.parquet"),
    ),
    Dataset(
        "depth_charts",
        "Team depth charts, per season",
        "parquet",
        True,
        lambda y: _release(f"depth_charts/depth_charts_{y}.parquet"),
    ),
    Dataset(
        "injuries",
        "Injury reports, per season",
        "parquet",
        True,
        lambda y: _release(f"injuries/injuries_{y}.parquet"),
    ),
]

_BY_NAME = {d.name: d for d in DATASETS}


def _read_expr(ds: Dataset, url: str) -> str:
    if ds.fmt == "csv":
        return f"SELECT * FROM read_csv_auto('{url}', union_by_name = true)"
    return f"SELECT * FROM read_parquet('{url}', union_by_name = true)"


def scrape_dataset(ds: Dataset, season_list: list[int]) -> tuple[int, int]:
    """Download a dataset into the raw layer. Returns (total_rows, files_written)."""
    rows = 0
    files = 0
    with memory_duckdb() as conn:
        if ds.per_season:
            for year in season_list:
                out = raw_path("nflverse", ds.name, f"season={year}", "data.parquet")
                rows += write_parquet(conn, _read_expr(ds, ds.url(year)), out)
                files += 1
        else:
            out = raw_path("nflverse", ds.name, "all.parquet")
            rows += write_parquet(conn, _read_expr(ds, ds.url(None)), out)
            files += 1
    return rows, files


def run(names: list[str] | None, season_list: list[int] | None = None) -> int:
    """Scrape the named datasets (or all). Returns the number of failures."""
    season_list = season_list or seasons()
    targets = DATASETS if not names else [_BY_NAME[n] for n in names if n in _BY_NAME]
    unknown = [n for n in (names or []) if n not in _BY_NAME]
    for n in unknown:
        print(f"  ! unknown nflverse dataset: {n}", file=sys.stderr)

    print(f"Seasons: {', '.join(map(str, season_list))}")
    failures = 0
    for ds in targets:
        label = f"{ds.name} ({len(season_list)} seasons)" if ds.per_season else ds.name
        print(f"-> {label} ... ", end="", flush=True)
        started = time.monotonic()
        try:
            rows, files = scrape_dataset(ds, season_list)
            secs = time.monotonic() - started
            print(f"{rows:,} rows -> {files} file(s) in {secs:.1f}s")
        except Exception as err:
            failures += 1
            print("FAILED")
            print(f"   {str(err).splitlines()[0]}", file=sys.stderr)
    return failures


def list_datasets() -> None:
    print("Available nflverse datasets:\n")
    for ds in DATASETS:
        tag = "[per-season]" if ds.per_season else "[single]   "
        print(f"  {tag} {ds.name:<16} {ds.description}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape nflverse datasets into data/raw/.")
    parser.add_argument("datasets", nargs="*", help="Dataset names (default: all).")
    parser.add_argument("--list", action="store_true", help="List datasets and exit.")
    args = parser.parse_args()
    if args.list:
        list_datasets()
        return 0
    return 1 if run(args.datasets or None) else 0


if __name__ == "__main__":
    sys.exit(main())
