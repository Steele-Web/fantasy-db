---
name: dbt-migration-ownership
description: fantasy-db — how DuckDB schema ownership is split between hand-rolled migrations and dbt
metadata:
  type: project
---

In fantasy-db, the DuckDB schema (PKs, types, constraints) is owned by hand-rolled
SQL in `db/migrations/` applied by `fdb-migrate` (`db/migrate.py`). dbt does **not**
own that DDL: every model in `transforms/` is `materialized: incremental` with
`on_schema_change: ignore`, so it UPSERTS into the migration-created tables on the
natural key instead of dropping/recreating them. Run `fdb-migrate` before `dbt run`.

Two consequences that bite if forgotten:
- dbt builds the insert from the **target table's** full column list, so each model
  must select every column the migration table has, including default lineage
  columns (`created_at`/`updated_at`, `ingested_at`) — even in empty `where false` stubs.
- `fct_pbp` has no migration table (pbp stays in Parquet via the `v_pbp` view, created
  by the pbp staging step in `db.connection.refresh_pbp_view`), so dbt owns it outright.

Project converted TS→Python on 2026-06-20: uv, medallion raw→staging→marts. See README.

As of 2026-06-21 the player-game path is fully built (no longer stubs): `dim_franchises`,
`dim_teams`, `dim_games`, `fct_player_game_stats` populated from nflverse weekly stats +
schedules for 2018–2025 (147k player-game rows). Two gotchas baked into those models:
- nflverse migrated weekly stats off the legacy `player_stats/player_stats_<y>` asset to
  the `stats_player/stats_player_week_<y>` release (115 cols, covers 2025). Its `game_id`
  column is only populated for some seasons, so `fct_player_game_stats` derives game_id by
  matching (season, week, team) against `dim_games`, not the feed column.
- weekly stats use canonical team abbrs (LV/LA always) but schedules use OAK for 2018–19;
  the `canonical_team()` macro normalizes both sides. dim_teams abbrs are franchise-canonical.
- crosswalk/dim_players extended past Sleeper via the nflverse players master, keyed by
  `int_nflverse_player_keys` (mints ids ABOVE the sleeper max; see [[sleeper-crosswalk]]).
Still stubs: `fct_projections`, `fct_team_game_stats`, `fct_vegas_lines`, `fct_pbp`.
