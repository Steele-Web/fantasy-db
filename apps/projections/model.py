"""Transparent season-long projection baseline.

The idea in one line: **project opportunity, then price it at a regressed,
opportunity-anchored efficiency** — never carry a player's noisy raw totals
forward. For each player we:

1. aggregate per-season per-game rates from ``fct_player_game_stats``,
2. blend the last up to three seasons with recency weights,
3. shrink efficiency (yards/att, TD rates, catch rate) toward the position
   baseline by effective sample size — so one fluky season can't dominate, and
4. project TDs from *volume × a league-like rate nudged by red-zone usage*,
   rather than from the player's own (high-variance) touchdown count.

Everything here is a pure function over plain dataclasses: ``load_history`` is the
only DB touch, and the projection math is unit-testable without a database.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

SKILL_POSITIONS = ("QB", "RB", "WR", "TE")

# Recency weights for the last up to 3 seasons (most-recent first), renormalized
# when fewer seasons exist. Games-played uses a shorter, flatter window.
_RECENCY = (0.6, 0.3, 0.1)
_GAMES_RECENCY = (0.7, 0.3)
_MAX_GAMES = 17

# Shrinkage constants: a rate is blended alpha*player + (1-alpha)*baseline where
# alpha = effective_opportunity / (effective_opportunity + K). Bigger K => shrinks
# harder toward the league/position baseline. TD rates use a larger K than yardage
# rates because per-touch scoring is far noisier than per-touch yards.
_K = {
    "pass_yards": 250.0,
    "pass_td": 450.0,
    "pass_int": 350.0,
    "rush_yards": 120.0,
    "rush_td": 260.0,
    "rec_catch": 70.0,
    "rec_yards": 70.0,
    "rec_td": 200.0,
}

# Per-position season scoring volatility (coefficient of variation) for the
# floor/ceiling band. Calibrated by `fdb-calibrate --min-games 8` (the ±1σ band
# covers ~68% of established-role players' realized seasons). Re-run after model
# changes; the prior heuristic guess was QB .18 / RB .32 / WR .34 / TE .38.
_POSITION_COV = {"QB": 0.43, "RB": 0.57, "WR": 0.56, "TE": 0.54}
_DEFAULT_COV = 0.33  # fallback for positions outside _POSITION_COV
_BAND_Z = 1.0  # ~1 std dev each way


@dataclass
class PlayerSeason:
    """One player's summed totals + games for a single season."""

    season: int
    games: int
    position: str
    pass_att: float = 0.0
    pass_yards: float = 0.0
    pass_tds: float = 0.0
    interceptions: float = 0.0
    rush_att: float = 0.0
    rush_yards: float = 0.0
    rush_tds: float = 0.0
    rz_carries: float = 0.0
    targets: float = 0.0
    receptions: float = 0.0
    rec_yards: float = 0.0
    rec_tds: float = 0.0
    rz_targets: float = 0.0
    fumbles_lost: float = 0.0
    two_pt: float = 0.0


@dataclass
class ProjectedLine:
    """A projected season stat line (component projections + scoring inputs)."""

    player_id: int
    position: str
    games: float
    proj_pass_yards: float = 0.0
    proj_pass_tds: float = 0.0
    proj_rush_yards: float = 0.0
    proj_rush_tds: float = 0.0
    proj_receptions: float = 0.0
    proj_rec_yards: float = 0.0
    proj_rec_tds: float = 0.0
    # Modeled but with no column in fct_projections; folded into projected_points.
    interceptions: float = 0.0
    fumbles_lost: float = 0.0
    two_pt: float = 0.0

    def score_inputs(self) -> dict[str, float]:
        """Canonical stat-name -> value mapping for ``scoring.score_line``."""
        return {
            "pass_yards": self.proj_pass_yards,
            "pass_tds": self.proj_pass_tds,
            "interceptions": self.interceptions,
            "rush_yards": self.proj_rush_yards,
            "rush_tds": self.proj_rush_tds,
            "receptions": self.proj_receptions,
            "rec_yards": self.proj_rec_yards,
            "rec_tds": self.proj_rec_tds,
            "fumbles_lost": self.fumbles_lost,
            "two_pt": self.two_pt,
        }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

_HISTORY_SQL = """
select
    player_id,
    season,
    mode(position)                  as position,
    count(*)                        as games,
    sum(coalesce(pass_attempts, 0))      as pass_att,
    sum(coalesce(pass_yards, 0))         as pass_yards,
    sum(coalesce(pass_tds, 0))           as pass_tds,
    sum(coalesce(interceptions, 0))      as interceptions,
    sum(coalesce(rush_attempts, 0))      as rush_att,
    sum(coalesce(rush_yards, 0))         as rush_yards,
    sum(coalesce(rush_tds, 0))           as rush_tds,
    sum(coalesce(rz_carries, 0))         as rz_carries,
    sum(coalesce(targets, 0))            as targets,
    sum(coalesce(receptions, 0))         as receptions,
    sum(coalesce(rec_yards, 0))          as rec_yards,
    sum(coalesce(rec_tds, 0))            as rec_tds,
    sum(coalesce(rz_targets, 0))         as rz_targets,
    sum(coalesce(fumbles_lost, 0))       as fumbles_lost,
    sum(coalesce(two_pt_conversions, 0)) as two_pt
from fct_player_game_stats
where season between ? and ?
  and position in ('QB', 'RB', 'WR', 'TE')
group by player_id, season
"""


def load_history(conn, through_season: int, lookback: int = 3) -> dict[int, list[PlayerSeason]]:
    """Per-player season aggregates for ``[through_season - lookback + 1, through_season]``.

    Returns ``{player_id: [PlayerSeason, ...]}`` sorted most-recent first.
    """
    start = through_season - lookback + 1
    cur = conn.execute(_HISTORY_SQL, [start, through_season])
    cols = [d[0] for d in cur.description]
    by_player: dict[int, list[PlayerSeason]] = defaultdict(list)
    for row in cur.fetchall():
        rec = dict(zip(cols, row, strict=True))
        pid = rec.pop("player_id")
        by_player[pid].append(PlayerSeason(**{k: _num(v) for k, v in rec.items()}))
    for seasons in by_player.values():
        seasons.sort(key=lambda s: s.season, reverse=True)
    return dict(by_player)


def _num(v):
    """Coerce DuckDB Decimals/None to float, leave strings (position) alone."""
    if v is None:
        return 0.0
    if isinstance(v, str):
        return v
    return float(v)


# ---------------------------------------------------------------------------
# Baselines (shrinkage targets)
# ---------------------------------------------------------------------------


@dataclass
class Baseline:
    yards_per_att: float = 0.0
    td_per_att: float = 0.0
    int_per_att: float = 0.0
    yards_per_carry: float = 0.0
    rush_td_per_carry: float = 0.0
    catch_rate: float = 0.0
    yards_per_target: float = 0.0
    rec_td_per_target: float = 0.0
    rz_carry_rate: float = 0.0  # rz_carries per carry
    rz_target_rate: float = 0.0  # rz_targets per target


def position_baselines(history: dict[int, list[PlayerSeason]]) -> dict[str, Baseline]:
    """League per-position efficiency rates, volume-weighted across all seasons.

    These are the shrinkage targets every player's noisy rates are pulled toward.
    """
    acc: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for seasons in history.values():
        for s in seasons:
            a = acc[s.position]
            a["pass_att"] += s.pass_att
            a["pass_yards"] += s.pass_yards
            a["pass_tds"] += s.pass_tds
            a["interceptions"] += s.interceptions
            a["rush_att"] += s.rush_att
            a["rush_yards"] += s.rush_yards
            a["rush_tds"] += s.rush_tds
            a["rz_carries"] += s.rz_carries
            a["targets"] += s.targets
            a["receptions"] += s.receptions
            a["rec_yards"] += s.rec_yards
            a["rec_tds"] += s.rec_tds
            a["rz_targets"] += s.rz_targets

    out: dict[str, Baseline] = {}
    for pos, a in acc.items():
        out[pos] = Baseline(
            yards_per_att=_safe(a["pass_yards"], a["pass_att"]),
            td_per_att=_safe(a["pass_tds"], a["pass_att"]),
            int_per_att=_safe(a["interceptions"], a["pass_att"]),
            yards_per_carry=_safe(a["rush_yards"], a["rush_att"]),
            rush_td_per_carry=_safe(a["rush_tds"], a["rush_att"]),
            catch_rate=_safe(a["receptions"], a["targets"]),
            yards_per_target=_safe(a["rec_yards"], a["targets"]),
            rec_td_per_target=_safe(a["rec_tds"], a["targets"]),
            rz_carry_rate=_safe(a["rz_carries"], a["rush_att"]),
            rz_target_rate=_safe(a["rz_targets"], a["targets"]),
        )
    return out


def _safe(num: float, den: float) -> float:
    return num / den if den else 0.0


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


@dataclass
class _Blend:
    """Recency-weighted accumulators across a player's blended seasons."""

    weight_games: float = 0.0  # Σ w  (for per-game volumes)
    fields: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    def add(self, w: float, s: PlayerSeason) -> None:
        if s.games <= 0:
            return
        self.weight_games += w
        f = self.fields
        # per-game volume contributions (weight * total/games)
        for name, total in (
            ("pass_att", s.pass_att),
            ("rush_att", s.rush_att),
            ("targets", s.targets),
            ("fumbles_lost", s.fumbles_lost),
            ("two_pt", s.two_pt),
        ):
            f[name + "_pg"] += w * total / s.games
        # weighted totals (for ratio numerators/denominators)
        for name, total in (
            ("pass_att", s.pass_att),
            ("pass_yards", s.pass_yards),
            ("pass_tds", s.pass_tds),
            ("interceptions", s.interceptions),
            ("rush_att", s.rush_att),
            ("rush_yards", s.rush_yards),
            ("rush_tds", s.rush_tds),
            ("rz_carries", s.rz_carries),
            ("targets", s.targets),
            ("receptions", s.receptions),
            ("rec_yards", s.rec_yards),
            ("rec_tds", s.rec_tds),
            ("rz_targets", s.rz_targets),
        ):
            f[name] += w * total


def project_player(
    seasons: list[PlayerSeason], target_season: int, baselines: dict[str, Baseline]
) -> ProjectedLine | None:
    """Project one player's season totals for ``target_season``.

    Uses seasons in ``[target_season - 3, target_season - 1]``. Returns ``None`` if
    the player has no usable games in that window (e.g. rookies — out of scope for v1).
    """
    window = [s for s in seasons if target_season - 3 <= s.season <= target_season - 1]
    window.sort(key=lambda s: s.season, reverse=True)
    window = [s for s in window if s.games > 0][:3]
    if not window:
        return None

    position = window[0].position
    base = baselines.get(position, Baseline())

    # Recency weights over the seasons actually present, renormalized.
    weights = _normalize(_RECENCY[: len(window)])
    blend = _Blend()
    for w, s in zip(weights, window, strict=False):
        blend.add(w, s)
    f = blend.fields
    wg = blend.weight_games or 1.0

    games = _project_games(window)

    # --- Passing (QB-ish) ---
    pass_att = (f["pass_att_pg"] / wg) * games
    ypa = _shrink(f["pass_yards"], f["pass_att"], base.yards_per_att, _K["pass_yards"])
    td_att = _shrink(f["pass_tds"], f["pass_att"], base.td_per_att, _K["pass_td"])
    int_att = _shrink(f["interceptions"], f["pass_att"], base.int_per_att, _K["pass_int"])

    # --- Rushing ---
    rush_att = (f["rush_att_pg"] / wg) * games
    ypc = _shrink(f["rush_yards"], f["rush_att"], base.yards_per_carry, _K["rush_yards"])
    rush_td_rate = _shrink(f["rush_tds"], f["rush_att"], base.rush_td_per_carry, _K["rush_td"])
    rush_td_rate *= _rz_factor(f["rz_carries"], f["rush_att"], base.rz_carry_rate)

    # --- Receiving ---
    targets = (f["targets_pg"] / wg) * games
    catch = _shrink(f["receptions"], f["targets"], base.catch_rate, _K["rec_catch"])
    ypt = _shrink(f["rec_yards"], f["targets"], base.yards_per_target, _K["rec_yards"])
    rec_td_rate = _shrink(f["rec_tds"], f["targets"], base.rec_td_per_target, _K["rec_td"])
    rec_td_rate *= _rz_factor(f["rz_targets"], f["targets"], base.rz_target_rate)

    return ProjectedLine(
        player_id=0,  # set by caller
        position=position,
        games=round(games, 1),
        proj_pass_yards=pass_att * ypa,
        proj_pass_tds=pass_att * td_att,
        proj_rush_yards=rush_att * ypc,
        proj_rush_tds=rush_att * rush_td_rate,
        proj_receptions=targets * catch,
        proj_rec_yards=targets * ypt,
        proj_rec_tds=targets * rec_td_rate,
        interceptions=pass_att * int_att,
        fumbles_lost=(f["fumbles_lost_pg"] / wg) * games,
        two_pt=(f["two_pt_pg"] / wg) * games,
    )


def project_all(
    history: dict[int, list[PlayerSeason]],
    target_season: int,
    baselines: dict[str, Baseline],
) -> list[ProjectedLine]:
    """Project every player in ``history`` for ``target_season``.

    Convenience over :func:`project_player`: drops players with no usable recent
    history and stamps each returned line with its ``player_id``.
    """
    lines: list[ProjectedLine] = []
    for pid, seasons in history.items():
        line = project_player(seasons, target_season, baselines)
        if line is None:
            continue
        line.player_id = pid
        lines.append(line)
    return lines


def _project_games(window: list[PlayerSeason]) -> float:
    """Recency-weighted recent games played, clamped to [1, 17]."""
    recent = window[:2]
    weights = _normalize(_GAMES_RECENCY[: len(recent)])
    g = sum(w * s.games for w, s in zip(weights, recent, strict=False))
    return max(1.0, min(float(_MAX_GAMES), g))


def _normalize(weights) -> list[float]:
    total = sum(weights)
    return [w / total for w in weights] if total else list(weights)


def _shrink(weighted_num: float, weighted_den: float, base_rate: float, k: float) -> float:
    """Blend the player's rate toward ``base_rate`` by effective sample size."""
    if weighted_den <= 0:
        return base_rate
    alpha = weighted_den / (weighted_den + k)
    return alpha * (weighted_num / weighted_den) + (1 - alpha) * base_rate


def _rz_factor(weighted_rz: float, weighted_opp: float, base_rz_rate: float) -> float:
    """Scale a TD rate by how a player's red-zone share compares to the baseline.

    A back who hogs goal-line carries scores above his per-carry baseline; a
    perimeter receiver below it. Clamped so the nudge stays modest.
    """
    if weighted_opp <= 0 or base_rz_rate <= 0:
        return 1.0
    player_rate = weighted_rz / weighted_opp
    return max(0.5, min(1.8, player_rate / base_rz_rate))


def floor_ceiling(points: float, position: str, games: float) -> tuple[float, float]:
    """Heuristic season floor/ceiling band around ``points`` (v1).

    Position coefficient of variation widened when projected games are below a
    full season (more missed-time risk => wider band). Recalibrate from backtests.
    """
    cov = _POSITION_COV.get(position, _DEFAULT_COV)
    cov *= math.sqrt(_MAX_GAMES / max(1.0, games))
    spread = _BAND_Z * cov
    return max(0.0, points * (1 - spread)), points * (1 + spread)
