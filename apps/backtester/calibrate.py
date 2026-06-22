"""``fdb-calibrate`` — recalibrate the projection floor/ceiling band from history.

The projection model's floor/ceiling band is a per-position coefficient of variation
(``_POSITION_COV`` in :mod:`apps.projections.model`) that the comments flag as "the
first thing to recalibrate from backtests". This does exactly that: it reruns the
*current* projection model across several past seasons — always in-memory, so no
snapshot needs to exist — measures how often each position's realized regular-season
total actually landed inside the band, and recommends the cov that would make the
band hit its nominal coverage. It prints a copy-pasteable ``_POSITION_COV`` block.

    uv run fdb-calibrate                       # last 4 projectable seasons, ppr
    uv run fdb-calibrate --seasons 2022,2023,2024 --format half_ppr
    uv run fdb-calibrate --min-games 8         # only players with a real sample

``--min-games`` sets the universe (default 0): ``0`` includes availability misses
(players projected for points who barely played — busts the band should still
cover); a higher value restricts to established samples. After applying a new block
to ``apps/projections/model.py``, re-run ``fdb-project`` to refresh snapshots.
"""

from __future__ import annotations

import argparse
import sys

from apps.backtester import evaluate
from apps.projections import model, scoring
from apps.query import _print_table
from db.connection import connect, query

_DEFAULT_NUM_SEASONS = 4
_MIN_LOOKBACK = 3  # project_player needs up to 3 prior seasons of history


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="fdb-calibrate", description="Recalibrate the projection floor/ceiling band."
    )
    p.add_argument(
        "--seasons",
        help="Comma-separated seasons to sweep (default: the last "
        f"{_DEFAULT_NUM_SEASONS} projectable seasons in the data).",
    )
    p.add_argument(
        "--format", dest="scoring_format", default="ppr", help="Scoring format (default: ppr)."
    )
    p.add_argument(
        "--min-games",
        type=int,
        default=0,
        help="Only sample players who played >= this many games "
        "(default: 0; includes availability misses).",
    )
    return p.parse_args(argv)


def _default_seasons(conn) -> list[int]:
    row = query(conn, "select min(season) lo, max(season) hi from fct_player_game_stats")[0]
    return _projectable_seasons(row["lo"], row["hi"])


def _projectable_seasons(lo: int | None, hi: int | None) -> list[int]:
    """The last ``_DEFAULT_NUM_SEASONS`` seasons that have enough prior history.

    A season is projectable once ``_MIN_LOOKBACK`` earlier seasons of data exist.
    """
    if lo is None or hi is None:
        return []
    projectable = list(range(lo + _MIN_LOOKBACK, hi + 1))
    return projectable[-_DEFAULT_NUM_SEASONS:]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    with connect(read_only=True) as conn:
        settings = scoring.load_scoring_settings(conn)
        if args.scoring_format not in settings:
            print(f"Unknown scoring format: {args.scoring_format}", file=sys.stderr)
            print(f"Available: {', '.join(sorted(settings))}", file=sys.stderr)
            return 2
        fmt_settings = settings[args.scoring_format]

        if args.seasons:
            seasons = [int(s) for s in args.seasons.split(",") if s.strip()]
        else:
            seasons = _default_seasons(conn)
        if not seasons:
            print("No projectable seasons found in fct_player_game_stats.", file=sys.stderr)
            return 1

        samples: list[tuple[str, float]] = []
        per_season: list[dict] = []
        for season in seasons:
            n = _collect_season(conn, season, fmt_settings, args.min_games, samples)
            per_season.append({"season": season, "samples": n})

    if not samples:
        print(
            "No (projection, actual) pairs collected — are the marts built for these seasons?",
            file=sys.stderr,
        )
        return 1

    recs = evaluate.recommend_covs(
        samples,
        z=model._BAND_Z,
        current_covs=model._POSITION_COV,
        default_cov=model._DEFAULT_COV,
    )
    _report(args, seasons, per_season, recs)
    return 0


def _collect_season(
    conn, season: int, fmt_settings: dict, min_games: int, samples: list[tuple[str, float]]
) -> int:
    """Project ``season`` with the current model and append normalized residuals.

    Returns the number of samples added for this season.
    """
    history = model.load_history(conn, season - 1)
    if not history:
        return 0
    baselines = model.position_baselines(history)
    lines = model.project_all(history, season, baselines)
    actuals = evaluate.load_actuals(conn, season, fmt_settings)

    added = 0
    for line in lines:
        projected = scoring.score_line(line.score_inputs(), fmt_settings, line.position)
        actual = actuals.get(line.player_id)
        games = actual.games if actual else 0
        if games < min_games:
            continue
        actual_points = actual.points if actual else 0.0
        position = actual.position if actual else line.position
        r = evaluate.normalized_residual(projected, actual_points, line.games, model._MAX_GAMES)
        if r is None:
            continue
        samples.append((position, r))
        added += 1
    return added


def _report(args, seasons, per_season, recs) -> None:
    target = recs[0].target_coverage if recs else 0.0
    print(
        f"Band calibration  format={args.scoring_format}  "
        f"seasons={','.join(str(s) for s in seasons)}  min_games={args.min_games}"
    )
    print(
        f"Target coverage for a +/-{model._BAND_Z:g} std band: {target * 100:.0f}%  "
        f"({sum(p['samples'] for p in per_season)} samples)\n"
    )

    _print_table(
        [
            {
                "pos": r.position,
                "n": r.n,
                "cur_cov": round(r.current_cov, 3),
                "cur_cover": f"{r.current_coverage * 100:.0f}%",
                "rec_cov": round(r.recommended_cov, 3),
                "target": f"{r.target_coverage * 100:.0f}%",
            }
            for r in recs
        ]
    )

    print("\nSuggested apps/projections/model.py block:\n")
    print(_cov_block(recs))


def _cov_block(recs) -> str:
    """A complete, drop-in ``_POSITION_COV`` literal for the model's positions.

    Every tracked position is emitted (in the model's own order); a position with
    no recommendation this run keeps its current value, so the block is always safe
    to paste whole — never silently dropping a position to the default.
    """
    rec_by_pos = {r.position: r.recommended_cov for r in recs}
    lines = ["_POSITION_COV = {"]
    for pos, current in model._POSITION_COV.items():
        cov = rec_by_pos.get(pos, current)
        lines.append(f'    "{pos}": {cov:.2f},')
    lines.append("}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
