"""Projections app — season-long fantasy projections (``fdb-project``).

A transparent statistical baseline that reads the marts read-only, projects each
player's full-season stat line, scores it through ``scoring_settings``, and snapshots
the result to ``fct_projections`` with ``source='my_model_v1'`` and ``week=0``.

Modules:
  * ``model``   — the baseline projection (opportunity x regressed efficiency).
  * ``scoring`` — load scoring_settings and price a stat line into points.
  * ``cli``     — the ``fdb-project`` entry point that ties it together.

Reads fct_player_game_stats, dim_players, scoring_settings; never touches raw/staging.
"""
