"""The projections app: scoring math and the baseline projection model.

All DB-free — scoring takes a settings dict and the model takes PlayerSeason
dataclasses, so the projection logic is exercised without touching DuckDB.
"""

from apps.projections import model, scoring
from apps.projections.cli import _parse_args
from apps.projections.model import Baseline, PlayerSeason

# A representative PPR settings row (mirrors scoring_settings / config/scoring.yaml).
PPR = {
    "pass_yard_pts": 0.04,
    "pass_td_pts": 4.0,
    "pass_int_pts": -2.0,
    "rush_yard_pts": 0.1,
    "rush_td_pts": 6.0,
    "rec_pts": 1.0,
    "rec_yard_pts": 0.1,
    "rec_td_pts": 6.0,
    "fumble_lost_pts": -2.0,
    "two_pt_pts": 2.0,
    "te_premium": 0.5,
}


# --- scoring -------------------------------------------------------------


def test_score_line_prices_a_receiving_line():
    # 100 rec, 1200 yds, 10 TDs in PPR -> 100 + 120 + 60.
    stats = {"receptions": 100, "rec_yards": 1200, "rec_tds": 10}
    assert scoring.score_line(stats, PPR, position="WR") == 280.0


def test_score_line_applies_te_premium_only_to_tes():
    stats = {"receptions": 80, "rec_yards": 800, "rec_tds": 6}
    base = 80 + 80 + 36  # 196
    assert scoring.score_line(stats, PPR, position="WR") == base
    # TE gets +0.5 per reception.
    assert scoring.score_line(stats, PPR, position="TE") == base + 40.0


def test_score_line_includes_negative_plays():
    stats = {"pass_yards": 4000, "pass_tds": 30, "interceptions": 12, "fumbles_lost": 3}
    expected = 4000 * 0.04 + 30 * 4.0 + 12 * -2.0 + 3 * -2.0
    assert scoring.score_line(stats, PPR) == expected


def test_score_line_ignores_absent_stats():
    assert scoring.score_line({}, PPR) == 0.0


# --- model ---------------------------------------------------------------

WR_BASELINE = Baseline(
    catch_rate=0.65,
    yards_per_target=8.0,
    rec_td_per_target=0.05,
    rz_target_rate=0.08,
)


def _wr_season(season, *, targets, rec, rec_yards, rec_tds, games=17, rz_targets=8):
    return PlayerSeason(
        season=season,
        games=games,
        position="WR",
        targets=targets,
        receptions=rec,
        rec_yards=rec_yards,
        rec_tds=rec_tds,
        rz_targets=rz_targets,
    )


def test_project_player_regresses_extreme_efficiency_toward_baseline():
    # 14.0 raw yards/target, well above the 8.0 baseline -> projection lands between.
    seasons = [
        _wr_season(2025, targets=100, rec=70, rec_yards=1400, rec_tds=10),
        _wr_season(2024, targets=100, rec=70, rec_yards=1400, rec_tds=10),
    ]
    line = model.project_player(seasons, 2026, {"WR": WR_BASELINE})

    assert line is not None
    # Volume is sticky: ~100 targets carried forward, so yds/target is recoverable.
    ypt = line.proj_rec_yards / 100.0
    assert 8.0 < ypt < 14.0  # regressed down from 14 toward 8
    assert line.games == 17.0


def test_project_player_scales_totals_with_projected_games():
    # Identical per-game usage (10 targets/game); only games played differ.
    full = model.project_player(
        [_wr_season(2025, targets=170, rec=110, rec_yards=1530, rec_tds=10, rz_targets=14)],
        2026,
        {"WR": WR_BASELINE},
    )
    half = model.project_player(
        [_wr_season(2025, targets=80, rec=52, rec_yards=720, rec_tds=5, games=8, rz_targets=7)],
        2026,
        {"WR": WR_BASELINE},
    )
    assert full.games == 17.0
    assert half.games == 8.0
    # Same per-game usage, fewer projected games -> proportionally fewer receptions.
    assert half.proj_receptions < full.proj_receptions
    assert abs(half.proj_receptions / full.proj_receptions - 8 / 17) < 0.05


def test_project_player_returns_none_without_recent_history():
    # Only data from 4 seasons before the target -> outside the 3-year window.
    old = [_wr_season(2021, targets=100, rec=65, rec_yards=900, rec_tds=6)]
    assert model.project_player(old, 2026, {"WR": WR_BASELINE}) is None


def test_rz_factor_lifts_high_redzone_usage_and_clamps():
    # Player with double the baseline red-zone share scores above the per-touch rate.
    assert model._rz_factor(weighted_rz=16, weighted_opp=100, base_rz_rate=0.08) > 1.0
    # No opportunity or no baseline -> neutral factor.
    assert model._rz_factor(0, 0, 0.08) == 1.0
    assert model._rz_factor(8, 100, 0.0) == 1.0


def test_floor_ceiling_brackets_points_and_widens_with_missed_time():
    floor_full, ceil_full = model.floor_ceiling(200.0, "RB", games=17)
    assert floor_full < 200.0 < ceil_full
    # Fewer projected games -> wider band.
    floor_part, ceil_part = model.floor_ceiling(200.0, "RB", games=9)
    assert floor_part < floor_full
    assert ceil_part > ceil_full


# --- cli -----------------------------------------------------------------


def test_parse_args_defaults():
    args = _parse_args([])
    assert args.source == "my_model_v1"
    assert args.limit == 25
    assert args.dry_run is False
    assert args.season is None  # resolved against the DB at runtime


def test_parse_args_accepts_backtest_window():
    args = _parse_args(["--season", "2025", "--through-season", "2024", "--dry-run"])
    assert (args.season, args.through_season) == (2025, 2024)
    assert args.dry_run is True
