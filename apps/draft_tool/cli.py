"""``fdb-draft`` — a value-based draft board for one of your leagues.

Reads a season-long projection snapshot from ``fct_projections`` (joined to
``dim_players`` for position/name), prices every player by **value over
replacement** for the league's roster construction (:mod:`apps.draft_tool.board`),
groups them into tiers, and prints the board. Pass ``--drafted`` a file of names
already off the board to use it live during a draft.

    uv run fdb-draft                              # first league, latest snapshot
    uv run fdb-draft --league home_league --pos RB
    uv run fdb-draft --season 2025 --format half_ppr --limit 80
    uv run fdb-draft --drafted gone.txt           # hide already-drafted players
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from apps.draft_tool import board
from apps.query import _print_table
from config import leagues as load_leagues
from db.connection import connect, query

_DEFAULT_SOURCE = "my_model_v1"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="fdb-draft", description="Value-based draft board.")
    p.add_argument("--league", help="League id from config/leagues.yaml (default: the first).")
    p.add_argument("--season", type=int, help="Projection season (default: latest snapshotted).")
    p.add_argument(
        "--format",
        dest="scoring_format",
        help="Scoring format (default: the league's scoring_format).",
    )
    p.add_argument("--source", default=_DEFAULT_SOURCE, help="Projection source (my_model_v1).")
    p.add_argument(
        "--snapshot-date",
        type=date.fromisoformat,
        help="Snapshot to use (default: latest for this season/source/format).",
    )
    p.add_argument(
        "--pos",
        dest="position",
        help="Filter the board to one position (QB/RB/WR/TE) or FLEX (RB/WR/TE).",
    )
    p.add_argument("--teams", type=int, help="Override the league's team count.")
    p.add_argument(
        "--tier-factor",
        type=float,
        default=2.0,
        help="VOR-drop multiple that starts a new tier (default: 2.0).",
    )
    p.add_argument(
        "--drafted",
        type=Path,
        help="File of already-drafted player names (one per line) to exclude.",
    )
    p.add_argument("--limit", type=int, default=50, help="Rows to print (default: 50).")
    return p.parse_args(argv)


def _pick_league(league_id: str | None) -> dict | None:
    leagues = load_leagues().get("leagues", [])
    if not leagues:
        return None
    if league_id is None:
        return leagues[0]
    return next((lg for lg in leagues if lg.get("id") == league_id), None)


def _player_meta(conn) -> dict[int, str]:
    rows = query(conn, "select player_id, full_name from dim_players")
    return {r["player_id"]: r["full_name"] for r in rows}


def _load_drafted(path: Path) -> set[str]:
    """Lower-cased player names from a drafted-list file (blank lines ignored)."""
    return {
        line.strip().lower()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    league = _pick_league(args.league)
    if league is None:
        where = f"id '{args.league}'" if args.league else "any league"
        print(f"No {where} in config/leagues.yaml.", file=sys.stderr)
        return 2

    roster = league.get("roster", {})
    teams = args.teams or int(league.get("teams", 12))
    scoring_format = args.scoring_format or league.get("scoring_format", "ppr")

    with connect(read_only=True) as conn:
        season = args.season or board.latest_projection_season(conn, args.source)
        if season is None:
            print(
                f"No '{args.source}' projections in fct_projections. "
                "Build them first:  uv run fdb-project",
                file=sys.stderr,
            )
            return 1

        snapshot = args.snapshot_date or board.latest_snapshot(
            conn, season, args.source, scoring_format
        )
        if snapshot is None:
            print(
                f"No '{args.source}' projections for season {season} ({scoring_format}). "
                f"Build them first:  uv run fdb-project --season {season}",
                file=sys.stderr,
            )
            return 1

        projections = board.load_projections(conn, season, args.source, scoring_format, snapshot)
        names = _player_meta(conn)

    if not projections:
        print("No projected players matched that snapshot.", file=sys.stderr)
        return 1

    if args.drafted:
        drafted = _load_drafted(args.drafted)
        projections = [p for p in projections if names.get(p.player_id, "").lower() not in drafted]

    entries = board.build_board(projections, roster, teams, tier_factor=args.tier_factor)
    _report(args, league, season, scoring_format, snapshot, teams, entries, names)
    return 0


def _filter_position(entries: list[board.BoardEntry], position: str) -> list[board.BoardEntry]:
    pos = position.upper()
    allowed = set(board.FLEX_POSITIONS) if pos == "FLEX" else {pos}
    return [e for e in entries if e.position in allowed]


def _report(args, league, season, scoring_format, snapshot, teams, entries, names) -> None:
    shown = _filter_position(entries, args.position) if args.position else entries
    print(
        f"Draft board: {league.get('name', league.get('id'))}  "
        f"{teams}-team {scoring_format}  season {season}  "
        f"(source={args.source}, snapshot={snapshot})"
    )
    showing = (
        f"; showing {min(args.limit, len(shown))} {args.position.upper()}" if args.position else ""
    )
    print(
        f"{len(entries)} players ranked by value over replacement "
        f"(tier = within-position tier; S = leaguewide starter){showing}.\n"
    )
    table = [
        {
            "rank": e.overall_rank,
            "tier": f"{e.position}-{e.tier}",
            "player": names.get(e.player_id, f"#{e.player_id}"),
            "pos": f"{e.position}{e.position_rank}",
            "pts": round(e.points, 1),
            "vor": round(e.vor, 1),
            "floor": round(e.floor, 1),
            "ceil": round(e.ceiling, 1),
            "start": "S" if e.starter else "",
        }
        for e in shown[: args.limit]
    ]
    _print_table(table)


if __name__ == "__main__":
    sys.exit(main())
