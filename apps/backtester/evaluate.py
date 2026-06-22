"""Grade snapshotted projections against what actually happened.

The contract that makes a backtest honest: a projection snapshot for ``season``
was built (by ``fdb-project --season S --through-season S-1``) from data that
predated that season, so comparing it to the season's realized results never
leaks the future. This module does the comparison.

The one rule that keeps it apples-to-apples: **actuals are priced through the
exact same scoring function the projections used** (:func:`apps.projections.scoring.score_line`).
We sum each player's realized season stat line from ``fct_player_game_stats`` and
score those totals under the same format, so any gap is the model's, not the
scoring's.

The DB is touched only by the two loaders (:func:`load_projections`,
:func:`load_actuals`); everything downstream is pure functions over dataclasses,
so the metrics are unit-testable without a database.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from apps.projections import scoring

# Canonical position display order; anything else sorts after, alphabetically.
_POSITION_ORDER = ("QB", "RB", "WR", "TE")

# Regular season is weeks 1-18; weeks 19+ are playoffs. Projections are framed on a
# 17-game regular season, so we grade against regular-season totals only — otherwise
# deep-playoff teams' actuals are inflated by games the projection never modeled.
_REGULAR_SEASON_MAX_WEEK = 18


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass
class Projection:
    """One projected season line for a player (the model's output, snapshotted)."""

    player_id: int
    points: float
    floor: float
    ceiling: float


@dataclass
class Actual:
    """One player's realized season: games, position, and scored season total."""

    player_id: int
    position: str
    games: int
    points: float


@dataclass
class Eval:
    """A projection paired with its realized outcome (one player, one format)."""

    player_id: int
    position: str
    projected: float
    actual: float
    floor: float
    ceiling: float
    games: int

    @property
    def error(self) -> float:
        """Signed error: positive means the projection was too high."""
        return self.projected - self.actual

    @property
    def abs_error(self) -> float:
        return abs(self.error)

    @property
    def in_band(self) -> bool:
        """Did the realized total land inside the projected floor/ceiling band?"""
        return self.floor <= self.actual <= self.ceiling


@dataclass
class Metrics:
    """Accuracy summary for a set of evaluations (overall or one position)."""

    label: str
    n: int
    mae: float  # mean absolute error
    rmse: float  # root mean squared error
    bias: float  # mean signed error (projected - actual); >0 == over-projecting
    pearson: float  # linear correlation of projected vs actual
    spearman: float  # rank correlation (what matters for draft ordering)
    band_pct: float  # fraction of actuals inside the floor/ceiling band


# ---------------------------------------------------------------------------
# Loading (the only DB touches)
# ---------------------------------------------------------------------------


def latest_snapshot(conn, season: int, source: str, scoring_format: str) -> date | None:
    """Most recent season-long (``week=0``) snapshot for this season/source/format."""
    row = conn.execute(
        """
        select max(snapshot_date) as d
        from fct_projections
        where season = ? and source = ? and scoring_format = ? and week = 0
        """,
        [season, source, scoring_format],
    ).fetchone()
    return row[0] if row else None


def load_projections(
    conn, season: int, source: str, scoring_format: str, snapshot_date: date
) -> dict[int, Projection]:
    """Projections for one snapshot, as ``{player_id: Projection}``."""
    cur = conn.execute(
        """
        select player_id, projected_points, floor, ceiling
        from fct_projections
        where season = ? and source = ? and scoring_format = ?
          and week = 0 and snapshot_date = ?
        """,
        [season, source, scoring_format, snapshot_date],
    )
    out: dict[int, Projection] = {}
    for pid, pts, floor, ceiling in cur.fetchall():
        out[pid] = Projection(pid, _num(pts), _num(floor), _num(ceiling))
    return out


# Realized season stat totals, named to match scoring._POINTS canonical keys so the
# row maps straight into score_line. mode(position) is the player's primary spot.
_ACTUALS_SQL = """
select
    player_id,
    mode(position)                       as position,
    count(*)                             as games,
    sum(coalesce(pass_yards, 0))         as pass_yards,
    sum(coalesce(pass_tds, 0))           as pass_tds,
    sum(coalesce(interceptions, 0))      as interceptions,
    sum(coalesce(rush_yards, 0))         as rush_yards,
    sum(coalesce(rush_tds, 0))           as rush_tds,
    sum(coalesce(receptions, 0))         as receptions,
    sum(coalesce(rec_yards, 0))          as rec_yards,
    sum(coalesce(rec_tds, 0))            as rec_tds,
    sum(coalesce(fumbles_lost, 0))       as fumbles_lost,
    sum(coalesce(two_pt_conversions, 0)) as two_pt
from fct_player_game_stats
where season = ? and week <= ?
group by player_id
"""

_STAT_KEYS = (
    "pass_yards",
    "pass_tds",
    "interceptions",
    "rush_yards",
    "rush_tds",
    "receptions",
    "rec_yards",
    "rec_tds",
    "fumbles_lost",
    "two_pt",
)


def load_actuals(conn, season: int, settings: Mapping[str, float]) -> dict[int, Actual]:
    """Realized, scored season totals for ``season``, as ``{player_id: Actual}``.

    ``settings`` is one row from ``scoring_settings`` (the chosen format); each
    player's summed stat line is priced through :func:`scoring.score_line` so the
    actuals are computed identically to the projections being graded.
    """
    cur = conn.execute(_ACTUALS_SQL, [season, _REGULAR_SEASON_MAX_WEEK])
    cols = [d[0] for d in cur.description]
    out: dict[int, Actual] = {}
    for row in cur.fetchall():
        rec = dict(zip(cols, row, strict=True))
        pid = rec["player_id"]
        position = rec["position"] or "UNK"
        stats = {k: _num(rec[k]) for k in _STAT_KEYS}
        points = scoring.score_line(stats, settings, position)
        out[pid] = Actual(pid, position, int(rec["games"]), points)
    return out


def _num(v) -> float:
    return 0.0 if v is None else float(v)


# ---------------------------------------------------------------------------
# Joining + metrics (pure)
# ---------------------------------------------------------------------------


def build_evals(
    projections: Mapping[int, Projection],
    actuals: Mapping[int, Actual],
    *,
    min_games: int = 1,
) -> list[Eval]:
    """Pair each projected player with their realized season.

    A player projected but with no realized stats (didn't play) gets ``actual=0``,
    ``games=0`` and is dropped by any ``min_games >= 1`` filter. ``min_games``
    therefore selects the universe: ``1`` grades "when a player played, how close
    were we?"; ``0`` includes availability misses (projected points, zero games).
    """
    evals: list[Eval] = []
    for pid, proj in projections.items():
        act = actuals.get(pid)
        position = act.position if act else "UNK"
        actual_points = act.points if act else 0.0
        games = act.games if act else 0
        if games < min_games:
            continue
        evals.append(
            Eval(
                player_id=pid,
                position=position,
                projected=proj.points,
                actual=actual_points,
                floor=proj.floor,
                ceiling=proj.ceiling,
                games=games,
            )
        )
    return evals


def metrics(evals: list[Eval], label: str = "ALL") -> Metrics:
    """Accuracy summary over a list of evaluations."""
    n = len(evals)
    if n == 0:
        return Metrics(label, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    errors = [e.error for e in evals]
    mae = sum(abs(x) for x in errors) / n
    rmse = math.sqrt(sum(x * x for x in errors) / n)
    bias = sum(errors) / n
    proj = [e.projected for e in evals]
    act = [e.actual for e in evals]
    band = sum(1 for e in evals if e.in_band) / n
    return Metrics(
        label=label,
        n=n,
        mae=mae,
        rmse=rmse,
        bias=bias,
        pearson=_pearson(proj, act),
        spearman=_spearman(proj, act),
        band_pct=band,
    )


def metrics_by_position(evals: list[Eval]) -> list[Metrics]:
    """Per-position metrics, ordered QB/RB/WR/TE then any extras alphabetically."""
    groups: dict[str, list[Eval]] = {}
    for e in evals:
        groups.setdefault(e.position, []).append(e)
    ordered = sorted(groups, key=_position_sort_key)
    return [metrics(groups[p], p) for p in ordered]


def _position_sort_key(pos: str) -> tuple[int, str]:
    rank = _POSITION_ORDER.index(pos) if pos in _POSITION_ORDER else len(_POSITION_ORDER)
    return rank, pos


def biggest_misses(evals: list[Eval], n: int) -> list[Eval]:
    """The ``n`` evaluations with the largest absolute error, worst first."""
    return sorted(evals, key=lambda e: e.abs_error, reverse=True)[:n]


# --- correlation helpers (pure python; no numpy/scipy) -------------------


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    denom = math.sqrt(vx * vy)
    return cov / denom if denom else 0.0


def _spearman(xs: list[float], ys: list[float]) -> float:
    """Spearman rho = Pearson on average (tie-corrected) ranks."""
    if len(xs) < 2:
        return 0.0
    return _pearson(_ranks(xs), _ranks(ys))


def _ranks(values: list[float]) -> list[float]:
    """Average ranks (ties share the mean of the ranks they'd occupy)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank for the tie block
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks
