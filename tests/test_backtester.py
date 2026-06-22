"""Backtester evaluation math — all DB-free.

The loaders touch DuckDB; everything graded here (joining projections to actuals,
error/correlation metrics, the biggest-miss ranking) is pure over dataclasses.
"""

import math

from apps.backtester import evaluate
from apps.backtester.cli import _parse_args
from apps.backtester.evaluate import Actual, Eval, Projection


def _proj(pid, points, *, floor=None, ceiling=None):
    # Default to a +/-20% band so in_band has something to test.
    floor = points * 0.8 if floor is None else floor
    ceiling = points * 1.2 if ceiling is None else ceiling
    return Projection(pid, points, floor, ceiling)


def _eval(projected, actual, *, position="WR", games=17, floor=0.0, ceiling=1e9):
    return Eval(
        player_id=0,
        position=position,
        projected=projected,
        actual=actual,
        floor=floor,
        ceiling=ceiling,
        games=games,
    )


# --- build_evals ---------------------------------------------------------


def test_build_evals_pairs_projection_with_actual():
    projections = {1: _proj(1, 200.0)}
    actuals = {1: Actual(1, "RB", games=16, points=180.0)}
    evals = evaluate.build_evals(projections, actuals)
    assert len(evals) == 1
    e = evals[0]
    assert e.position == "RB"
    assert e.projected == 200.0
    assert e.actual == 180.0
    assert math.isclose(e.error, 20.0)  # over-projected


def test_build_evals_drops_players_who_did_not_play_by_default():
    # Projected but no actuals row -> 0 games -> excluded at default min_games=1.
    projections = {1: _proj(1, 150.0), 2: _proj(2, 90.0)}
    actuals = {1: Actual(1, "WR", games=12, points=140.0)}
    evals = evaluate.build_evals(projections, actuals)
    assert [e.player_id for e in evals] == [1]


def test_build_evals_min_games_zero_counts_availability_misses():
    # min_games=0 keeps the no-show as a full-credit miss (projected pts, actual 0).
    projections = {2: _proj(2, 90.0)}
    evals = evaluate.build_evals(projections, {}, min_games=0)
    assert len(evals) == 1
    assert evals[0].actual == 0.0
    assert evals[0].games == 0
    assert evals[0].error == 90.0


def test_build_evals_min_games_filters_low_sample():
    projections = {1: _proj(1, 100.0)}
    actuals = {1: Actual(1, "TE", games=3, points=40.0)}
    assert evaluate.build_evals(projections, actuals, min_games=4) == []
    assert len(evaluate.build_evals(projections, actuals, min_games=3)) == 1


# --- metrics -------------------------------------------------------------


def test_metrics_error_aggregates():
    evals = [_eval(100.0, 80.0), _eval(100.0, 130.0)]  # errors +20, -30
    m = evaluate.metrics(evals)
    assert m.n == 2
    assert math.isclose(m.mae, 25.0)  # (20 + 30) / 2
    assert math.isclose(m.bias, -5.0)  # (20 - 30) / 2; net under-projected
    assert math.isclose(m.rmse, math.sqrt((400 + 900) / 2))


def test_metrics_empty_is_zeroed():
    m = evaluate.metrics([])
    assert m.n == 0
    assert (m.mae, m.rmse, m.bias, m.pearson, m.spearman, m.band_pct) == (0, 0, 0, 0, 0, 0)


def test_metrics_perfect_projection_correlates_one():
    evals = [_eval(p, p) for p in (50.0, 120.0, 200.0, 300.0)]
    m = evaluate.metrics(evals)
    assert math.isclose(m.pearson, 1.0)
    assert math.isclose(m.spearman, 1.0)
    assert math.isclose(m.mae, 0.0)


def test_metrics_band_coverage():
    # Two of three actuals fall inside the floor/ceiling band.
    evals = [
        _eval(100.0, 95.0, floor=80.0, ceiling=120.0),  # in
        _eval(100.0, 130.0, floor=80.0, ceiling=120.0),  # out (above ceiling)
        _eval(100.0, 110.0, floor=80.0, ceiling=120.0),  # in
    ]
    m = evaluate.metrics(evals)
    assert math.isclose(m.band_pct, 2 / 3)


def test_spearman_rewards_rank_order_despite_nonlinearity():
    # Monotonic but non-linear: perfect rank agreement, imperfect Pearson.
    evals = [_eval(1.0, 1.0), _eval(2.0, 4.0), _eval(3.0, 9.0), _eval(4.0, 16.0)]
    m = evaluate.metrics(evals)
    assert math.isclose(m.spearman, 1.0)
    assert m.pearson < 1.0


def test_ranks_average_ties():
    # Values [10, 10, 20] -> the two tied 10s share rank (1+2)/2 = 1.5; 20 -> 3.
    assert evaluate._ranks([10.0, 10.0, 20.0]) == [1.5, 1.5, 3.0]


# --- metrics_by_position + biggest_misses --------------------------------


def test_metrics_by_position_orders_and_splits():
    evals = [
        _eval(100.0, 90.0, position="WR"),
        _eval(300.0, 280.0, position="QB"),
        _eval(120.0, 100.0, position="RB"),
    ]
    rows = evaluate.metrics_by_position(evals)
    assert [m.label for m in rows] == ["QB", "RB", "WR"]
    assert all(m.n == 1 for m in rows)


def test_biggest_misses_sorts_by_abs_error():
    evals = [_eval(100.0, 95.0), _eval(100.0, 40.0), _eval(100.0, 120.0)]
    worst = evaluate.biggest_misses(evals, 2)
    assert [round(e.abs_error) for e in worst] == [60, 20]


# --- cli -----------------------------------------------------------------


def test_parse_args_defaults():
    args = _parse_args(["--season", "2024"])
    assert args.season == 2024
    assert args.source == "my_model_v1"
    assert args.scoring_format == "ppr"
    assert args.min_games == 1
    assert args.snapshot_date is None


def test_parse_args_overrides():
    args = _parse_args(
        ["--season", "2023", "--format", "half_ppr", "--min-games", "4", "--misses", "5"]
    )
    actual = (args.season, args.scoring_format, args.min_games, args.misses)
    assert actual == (2023, "half_ppr", 4, 5)
