"""Value-based draft board: rank players *across* positions for a draft.

A projection alone can't tell you whether to draft a 250-point RB or a 280-point
QB — points aren't comparable across positions because the positions have very
different replacement levels (the league starts far more RBs/WRs than QBs/TEs).
The fix is **value over replacement (VOR)**: price every player against the best
player at his position you could still get *for free* once the league's starting
slots are filled, then rank everyone by that surplus.

The replacement level falls straight out of roster construction. In a 12-team
league that starts 1 QB, the 12 best QBs go as starters, so the *13th* QB is the
replacement baseline; a QB is only worth his points above that QB13 line. FLEX
slots are allocated greedily to whichever flex-eligible position has the most
valuable players still on the board, which is what deepens RB/WR replacement
levels in practice.

Everything here is a pure function over dataclasses except :func:`load_projections`
(the one DB touch), so the VOR/tiering math is unit-testable without a database.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from statistics import median

# Positions the projection model covers (K/DST aren't projected, so they never
# reach the board). FLEX draws from RB/WR/TE; SUPERFLEX adds QB.
VBD_POSITIONS = ("QB", "RB", "WR", "TE")
FLEX_POSITIONS = ("RB", "WR", "TE")
SUPERFLEX_POSITIONS = ("QB", "RB", "WR", "TE")

# Roster keys that mean "a flex slot" and the positions each draws from. Base
# positional keys (QB/RB/WR/TE) are handled directly; bench/K/DST are ignored.
_FLEX_KEYS = {
    "FLEX": FLEX_POSITIONS,
    "WRT": FLEX_POSITIONS,
    "REC_FLEX": ("WR", "TE"),
    "SUPERFLEX": SUPERFLEX_POSITIONS,
    "SFLEX": SUPERFLEX_POSITIONS,
    "QFLEX": SUPERFLEX_POSITIONS,
}


@dataclass
class PlayerProj:
    """One player's season-long projection — the board's raw input."""

    player_id: int
    position: str
    points: float
    floor: float = 0.0
    ceiling: float = 0.0


@dataclass
class BoardEntry:
    """A ranked player on the draft board: their value over replacement + tier."""

    player_id: int
    position: str
    points: float
    floor: float
    ceiling: float
    vor: float
    overall_rank: int = 0
    position_rank: int = 0
    tier: int = 0
    starter: bool = False  # would be drafted into a starting slot leaguewide


# ---------------------------------------------------------------------------
# Loading (the only DB touch)
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


def latest_projection_season(conn, source: str) -> int | None:
    """Newest season this source has season-long projections for."""
    row = conn.execute(
        "select max(season) as s from fct_projections where source = ? and week = 0",
        [source],
    ).fetchone()
    return row[0] if row else None


def load_projections(
    conn, season: int, source: str, scoring_format: str, snapshot_date: date
) -> list[PlayerProj]:
    """Season-long projections joined to each player's position (one snapshot).

    Only the four projected positions are returned; ``fct_projections`` has no
    position column, so position comes from ``dim_players``.
    """
    cur = conn.execute(
        """
        select p.player_id, d.position, p.projected_points, p.floor, p.ceiling
        from fct_projections p
        join dim_players d using (player_id)
        where p.season = ? and p.source = ? and p.scoring_format = ?
          and p.week = 0 and p.snapshot_date = ?
          and d.position in ('QB', 'RB', 'WR', 'TE')
        """,
        [season, source, scoring_format, snapshot_date],
    )
    out: list[PlayerProj] = []
    for pid, pos, pts, floor, ceiling in cur.fetchall():
        out.append(PlayerProj(pid, pos, _num(pts), _num(floor), _num(ceiling)))
    return out


def _num(v) -> float:
    return 0.0 if v is None else float(v)


# ---------------------------------------------------------------------------
# Roster -> starter counts (pure)
# ---------------------------------------------------------------------------


def starter_counts(
    roster: Mapping[str, int], teams: int, pools: Mapping[str, list[float]]
) -> dict[str, int]:
    """How many players at each position get drafted as starters leaguewide.

    Base positional slots are ``roster[pos] * teams``. Each FLEX slot is then
    handed to whichever eligible position has the most valuable player still on
    the board (greedy), since that's who actually fills flex. ``pools`` maps each
    position to its points sorted descending — the order flex is drawn from.
    """
    counts: dict[str, int] = {pos: int(roster.get(pos, 0)) * teams for pos in VBD_POSITIONS}

    for key, eligible in _FLEX_KEYS.items():
        slots = int(roster.get(key, 0)) * teams
        for _ in range(slots):
            pos = _best_remaining(eligible, counts, pools)
            if pos is None:
                break
            counts[pos] += 1
    return counts


def _best_remaining(
    eligible: Iterable[str], counts: Mapping[str, int], pools: Mapping[str, list[float]]
) -> str | None:
    """The eligible position whose next undrafted player is most valuable."""
    best_pos: str | None = None
    best_pts = float("-inf")
    for pos in eligible:
        pool = pools.get(pos, [])
        idx = counts[pos]  # next player not yet counted as a starter
        if idx < len(pool) and pool[idx] > best_pts:
            best_pts = pool[idx]
            best_pos = pos
    return best_pos


def replacement_levels(
    pools: Mapping[str, list[float]], starters: Mapping[str, int]
) -> dict[str, float]:
    """Replacement points per position = the best player who *won't* start.

    With ``n`` starters drafted at a position, the replacement baseline is the
    (n+1)-th best player there (index ``n`` in the descending pool) — the value
    you can still get once every starting slot is filled. Falls back to the last
    available player, or ``0`` for an empty pool.
    """
    out: dict[str, float] = {}
    for pos, pool in pools.items():
        n = starters.get(pos, 0)
        if not pool:
            out[pos] = 0.0
        elif n < len(pool):
            out[pos] = pool[n]
        else:
            out[pos] = pool[-1]
    return out


# ---------------------------------------------------------------------------
# Board (pure)
# ---------------------------------------------------------------------------


def build_board(
    projections: Iterable[PlayerProj],
    roster: Mapping[str, int],
    teams: int,
    *,
    tier_factor: float = 2.0,
) -> list[BoardEntry]:
    """Rank players across positions by value over replacement, with tiers.

    Returns entries sorted by VOR descending, each stamped with overall/position
    rank, tier, and whether they'd be drafted into a starting slot leaguewide.
    """
    pools = _pools(projections)
    starters = starter_counts(roster, teams, pools)
    replacement = replacement_levels(pools, starters)

    entries = [
        BoardEntry(
            player_id=p.player_id,
            position=p.position,
            points=p.points,
            floor=p.floor,
            ceiling=p.ceiling,
            vor=p.points - replacement.get(p.position, 0.0),
        )
        for p in projections
    ]
    entries.sort(key=lambda e: e.vor, reverse=True)

    pos_seen: dict[str, int] = defaultdict(int)
    for i, e in enumerate(entries, start=1):
        e.overall_rank = i
        pos_seen[e.position] += 1
        e.position_rank = pos_seen[e.position]
        e.starter = e.position_rank <= starters.get(e.position, 0)

    assign_tiers(entries, tier_factor=tier_factor)
    return entries


def _pools(projections: Iterable[PlayerProj]) -> dict[str, list[float]]:
    """Per-position projected points, each sorted descending."""
    pools: dict[str, list[float]] = defaultdict(list)
    for p in projections:
        pools[p.position].append(p.points)
    for pts in pools.values():
        pts.sort(reverse=True)
    return dict(pools)


def assign_tiers(entries: Iterable[BoardEntry], *, tier_factor: float = 2.0) -> None:
    """Tier each position's players by VOR gap, in place.

    Tiers are per *position* (the way draft cheat-sheets read): a break falls
    wherever the VOR drop to the next player at that position is more than
    ``tier_factor`` times the typical (median) drop — a cliff, not a step. Tiering
    across positions instead would be swamped by the long flat tail of below-
    replacement players, collapsing the threshold to zero. Players in one tier are
    roughly interchangeable, so tiers tell you how much of a positional run you can
    wait out before the value falls off.
    """
    by_pos: dict[str, list[BoardEntry]] = defaultdict(list)
    for e in entries:  # entries arrive VOR-sorted, so each group stays VOR-sorted
        by_pos[e.position].append(e)
    for group in by_pos.values():
        _tier_group(group, tier_factor)


def _tier_group(group: list[BoardEntry], tier_factor: float) -> None:
    if not group:
        return
    gaps = [group[i - 1].vor - group[i].vor for i in range(1, len(group))]
    positive = [g for g in gaps if g > 0]
    threshold = tier_factor * median(positive) if positive else float("inf")

    tier = 1
    group[0].tier = 1
    for i in range(1, len(group)):
        if group[i - 1].vor - group[i].vor > threshold:
            tier += 1
        group[i].tier = tier
