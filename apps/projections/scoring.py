"""Turn a stat line into fantasy points.

The ``scoring_settings`` table is the authoritative scoring source for apps (its
columns mirror ``config/scoring.yaml``; the migration seeds ``rec_pts`` and leans
on column DEFAULTs for the rest, so every row is complete). We read it once and
score projected *season totals* against it.

Per-game bonuses (100-yd rush/rec, 300-yd pass) are intentionally **not** applied
to season totals — they're game-level thresholds and are ``0`` in every shipped
format anyway. ``te_premium`` (extra points per reception for tight ends) is
applied because it's additive and position-based, not game-level.
"""

from __future__ import annotations

from collections.abc import Mapping

# Stat key -> scoring_settings column that prices it. Keys are the canonical names
# the projection model emits; missing stats score as zero.
_POINTS = {
    "pass_yards": "pass_yard_pts",
    "pass_tds": "pass_td_pts",
    "interceptions": "pass_int_pts",
    "rush_yards": "rush_yard_pts",
    "rush_tds": "rush_td_pts",
    "receptions": "rec_pts",
    "rec_yards": "rec_yard_pts",
    "rec_tds": "rec_td_pts",
    "fumbles_lost": "fumble_lost_pts",
    "two_pt": "two_pt_pts",
}


def load_scoring_settings(conn) -> dict[str, dict[str, float]]:
    """Read every scoring format from the ``scoring_settings`` table.

    Returns ``{scoring_format: {column: value}}`` with numeric values coerced to
    float so callers don't juggle ``Decimal``.
    """
    cur = conn.execute("select * from scoring_settings")
    cols = [d[0] for d in cur.description]
    out: dict[str, dict[str, float]] = {}
    for row in cur.fetchall():
        rec = dict(zip(cols, row, strict=True))
        fmt = rec.pop("scoring_format")
        out[fmt] = {k: float(v) if v is not None else 0.0 for k, v in rec.items()}
    return out


def score_line(
    stats: Mapping[str, float], settings: Mapping[str, float], position: str | None = None
) -> float:
    """Fantasy points for a stat line under one scoring format.

    ``stats`` is a mapping of canonical stat name -> value (see ``_POINTS``);
    absent stats count as zero. ``te_premium`` adds points per reception for TEs.
    """
    pts = 0.0
    for stat, col in _POINTS.items():
        value = stats.get(stat)
        if value:
            pts += float(value) * settings.get(col, 0.0)

    if position == "TE":
        pts += float(stats.get("receptions", 0.0)) * settings.get("te_premium", 0.0)

    return pts
