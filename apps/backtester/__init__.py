"""Backtester — grade snapshotted projections against realized results.

``fdb-backtest`` loads a season-long projection snapshot (``fct_projections``,
``week=0``) and the realized season (``fct_player_game_stats``), scores both
through the same ``scoring_settings`` format, and reports accuracy overall and
per position (MAE / RMSE / bias / Pearson / Spearman / floor-ceiling coverage)
plus the biggest individual misses.

Because each snapshot was built only from data that predated its season (see
``fdb-project --through-season``), the comparison never leaks the future. The
evaluation math lives in :mod:`apps.backtester.evaluate` as pure functions over
dataclasses; only its two loaders touch the database.
"""
