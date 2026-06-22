"""``fdb-backtest`` — grade a projection snapshot against realized results.

Loads a season-long projection snapshot from ``fct_projections`` and the matching
realized season from ``fct_player_game_stats``, scores both through the same
``scoring_settings`` format, and reports accuracy: overall and per position
(MAE / RMSE / bias / Pearson / Spearman / floor-ceiling coverage), plus the
biggest individual misses.

    uv run fdb-backtest --season 2024                     # my_model_v1, ppr, latest snapshot
    uv run fdb-backtest --season 2024 --format half_ppr
    uv run fdb-backtest --season 2024 --min-games 4 --misses 20

The snapshot must already exist. Reproduce a past one first with, e.g.:

    uv run fdb-project --season 2024 --through-season 2023
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from apps.backtester import evaluate
from apps.projections import scoring
from apps.query import _print_table
from db.connection import connect, query


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="fdb-backtest", description="Grade projections vs. actuals.")
    p.add_argument("--season", type=int, required=True, help="Season to grade (must have actuals).")
    p.add_argument(
        "--source", default="my_model_v1", help="Projection source (default: my_model_v1)."
    )
    p.add_argument(
        "--format",
        dest="scoring_format",
        default="ppr",
        help="Scoring format (default: ppr).",
    )
    p.add_argument(
        "--snapshot-date",
        type=date.fromisoformat,
        help="Snapshot to grade (default: latest snapshot for this season/source/format).",
    )
    p.add_argument(
        "--min-games",
        type=int,
        default=1,
        help="Only grade players who played >= this many games "
        "(default: 1; 0 includes availability misses).",
    )
    p.add_argument(
        "--misses", type=int, default=15, help="How many biggest misses to list (default: 15)."
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    with connect(read_only=True) as conn:
        settings = scoring.load_scoring_settings(conn)
        if args.scoring_format not in settings:
            print(f"Unknown scoring format: {args.scoring_format}", file=sys.stderr)
            print(f"Available: {', '.join(sorted(settings))}", file=sys.stderr)
            return 2

        snapshot = args.snapshot_date or evaluate.latest_snapshot(
            conn, args.season, args.source, args.scoring_format
        )
        if snapshot is None:
            print(
                f"No '{args.source}' projections for season {args.season} "
                f"({args.scoring_format}). Build them first:\n"
                f"  uv run fdb-project --season {args.season} "
                f"--through-season {args.season - 1}",
                file=sys.stderr,
            )
            return 1

        projections = evaluate.load_projections(
            conn, args.season, args.source, args.scoring_format, snapshot
        )
        actuals = evaluate.load_actuals(conn, args.season, settings[args.scoring_format])
        if not actuals:
            print(
                f"No realized stats for season {args.season} in fct_player_game_stats.",
                file=sys.stderr,
            )
            return 1

        evals = evaluate.build_evals(projections, actuals, min_games=args.min_games)
        names = _player_meta(conn)

    _report(args, snapshot, projections, evals, names)
    return 0


def _player_meta(conn) -> dict[int, str]:
    rows = query(conn, "select player_id, full_name from dim_players")
    return {r["player_id"]: r["full_name"] for r in rows}


def _report(args, snapshot, projections, evals, names) -> None:
    n_proj = len(projections)
    n_eval = len(evals)

    print(
        f"Backtest: season {args.season}  source={args.source}  "
        f"format={args.scoring_format}  snapshot={snapshot}"
    )
    print(
        f"{n_proj} players projected; grading {n_eval} with >= {args.min_games} game(s) "
        f"({n_proj - n_eval} excluded).\n"
    )

    if not evals:
        print("Nothing to grade.")
        return

    overall = evaluate.metrics(evals, "ALL")
    by_pos = evaluate.metrics_by_position(evals)
    print("Accuracy (points; bias > 0 == over-projecting):\n")
    _print_table([_metrics_row(m) for m in [overall, *by_pos]])

    print(f"\nBiggest misses (|projected - actual|), top {args.misses}:\n")
    _print_table(
        [
            {
                "player": names.get(e.player_id, f"#{e.player_id}"),
                "pos": e.position,
                "g": e.games,
                "proj": round(e.projected, 1),
                "actual": round(e.actual, 1),
                "error": round(e.error, 1),
                "band": "in" if e.in_band else "out",
            }
            for e in evaluate.biggest_misses(evals, args.misses)
        ]
    )


def _metrics_row(m: evaluate.Metrics) -> dict:
    return {
        "group": m.label,
        "n": m.n,
        "mae": round(m.mae, 1),
        "rmse": round(m.rmse, 1),
        "bias": round(m.bias, 1),
        "pearson": round(m.pearson, 3),
        "spearman": round(m.spearman, 3),
        "in_band": f"{m.band_pct * 100:.0f}%",
    }


if __name__ == "__main__":
    sys.exit(main())
