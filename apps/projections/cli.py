"""``fdb-project`` — build season-long projections and snapshot them.

Reads ``fct_player_game_stats`` + ``scoring_settings``, runs the baseline model
(:mod:`apps.projections.model`), scores each player's projected line for every
scoring format, and ``INSERT OR REPLACE``-s the rows into ``fct_projections`` with
``week = 0`` and a ``snapshot_date`` — so re-running a snapshot is idempotent and
the backtester only ever sees what was known at that date.

    uv run fdb-project                       # project (latest season + 1)
    uv run fdb-project --dry-run --limit 20  # preview, write nothing
    uv run fdb-project --season 2025 --through-season 2024   # backtest a past year
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from apps.projections import model, scoring
from apps.query import _print_table
from db.connection import connect, query

_DISPLAY_FORMAT = "ppr"  # which format the on-screen top-N is ranked by

_INSERT = """
insert or replace into fct_projections (
    snapshot_date, source, player_id, season, week, scoring_format,
    projected_points, floor, ceiling,
    proj_pass_yards, proj_pass_tds, proj_rush_yards, proj_rush_tds,
    proj_receptions, proj_rec_yards, proj_rec_tds
) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="fdb-project", description="Build season-long projections.")
    p.add_argument("--season", type=int, help="Season to project (default: latest data + 1).")
    p.add_argument(
        "--through-season",
        type=int,
        help="Last season of data to use (default: --season minus 1).",
    )
    p.add_argument(
        "--snapshot-date",
        type=date.fromisoformat,
        default=date.today(),
        help="Snapshot date stamped on every row (default: today).",
    )
    p.add_argument(
        "--formats",
        help="Comma-separated scoring formats (default: every format in scoring_settings).",
    )
    p.add_argument("--source", default="my_model_v1", help="source label (default: my_model_v1).")
    p.add_argument("--limit", type=int, default=25, help="Rows in the printed summary.")
    p.add_argument("--dry-run", action="store_true", help="Project and print, but write nothing.")
    return p.parse_args(argv)


def _latest_data_season(conn) -> int:
    return query(conn, "select max(season) as s from fct_player_game_stats")[0]["s"]


def _player_meta(conn) -> dict[int, str]:
    rows = query(conn, "select player_id, full_name from dim_players")
    return {r["player_id"]: r["full_name"] for r in rows}


def _round(value: float, places: int = 2) -> float:
    return round(float(value), places)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    # Writable connection: we append to fct_projections.
    with connect() as conn:
        season = args.season or _latest_data_season(conn) + 1
        through = args.through_season if args.through_season is not None else season - 1

        settings = scoring.load_scoring_settings(conn)
        formats = (
            [f.strip() for f in args.formats.split(",") if f.strip()]
            if args.formats
            else sorted(settings)
        )
        missing = [f for f in formats if f not in settings]
        if missing:
            print(f"Unknown scoring format(s): {', '.join(missing)}", file=sys.stderr)
            print(f"Available: {', '.join(sorted(settings))}", file=sys.stderr)
            return 2

        history = model.load_history(conn, through)
        if not history:
            print(
                f"No player history found through season {through}. "
                "Build the marts first (see README → Building marts).",
                file=sys.stderr,
            )
            return 1
        baselines = model.position_baselines(history)
        names = _player_meta(conn)

        # Project every in-scope player once; the line is format-independent.
        lines: list[model.ProjectedLine] = []
        for pid, seasons in history.items():
            line = model.project_player(seasons, season, baselines)
            if line is None:
                continue
            line.player_id = pid
            lines.append(line)

        rows = _build_rows(lines, settings, formats, args, season)

        if args.dry_run:
            print(
                f"[dry-run] {len(lines)} players projected for {season} "
                f"(data through {through}); {len(rows)} rows NOT written.\n"
            )
        else:
            conn.executemany(_INSERT, rows)
            print(
                f"Wrote {len(rows)} projection rows: {len(lines)} players x "
                f"{len(formats)} format(s) for season {season} "
                f"(source={args.source}, snapshot={args.snapshot_date}).\n"
            )

        _print_summary(lines, settings, names, args.limit, season)
    return 0


def _build_rows(
    lines: list[model.ProjectedLine],
    settings: dict[str, dict[str, float]],
    formats: list[str],
    args: argparse.Namespace,
    season: int,
) -> list[tuple]:
    rows: list[tuple] = []
    for line in lines:
        for fmt in formats:
            points = scoring.score_line(line.score_inputs(), settings[fmt], line.position)
            floor, ceiling = model.floor_ceiling(points, line.position, line.games)
            rows.append(
                (
                    args.snapshot_date,
                    args.source,
                    line.player_id,
                    season,
                    0,  # week 0 == season-long
                    fmt,
                    _round(points),
                    _round(floor),
                    _round(ceiling),
                    _round(line.proj_pass_yards),
                    _round(line.proj_pass_tds),
                    _round(line.proj_rush_yards),
                    _round(line.proj_rush_tds),
                    _round(line.proj_receptions),
                    _round(line.proj_rec_yards),
                    _round(line.proj_rec_tds),
                )
            )
    return rows


def _print_summary(
    lines: list[model.ProjectedLine],
    settings: dict[str, dict[str, float]],
    names: dict[int, str],
    limit: int,
    season: int,
) -> None:
    fmt = _DISPLAY_FORMAT if _DISPLAY_FORMAT in settings else sorted(settings)[0]
    scored = sorted(
        (
            (scoring.score_line(line.score_inputs(), settings[fmt], line.position), line)
            for line in lines
        ),
        key=lambda t: t[0],
        reverse=True,
    )
    print(f"Top {min(limit, len(scored))} for {season} by {fmt} points:\n")
    table = [
        {
            "player": names.get(line.player_id, f"#{line.player_id}"),
            "pos": line.position,
            "g": line.games,
            "pts": _round(points, 1),
            "pass_yd": _round(line.proj_pass_yards, 0),
            "rush_yd": _round(line.proj_rush_yards, 0),
            "rec": _round(line.proj_receptions, 1),
            "rec_yd": _round(line.proj_rec_yards, 0),
            "tds": _round(
                line.proj_pass_tds + line.proj_rush_tds + line.proj_rec_tds, 1
            ),
        }
        for points, line in scored[:limit]
    ]
    _print_table(table)


if __name__ == "__main__":
    sys.exit(main())
