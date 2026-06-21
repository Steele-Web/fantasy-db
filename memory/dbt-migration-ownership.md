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

FK + incremental gotcha (bit me): the migration declares FKs (dim_games.home/away_team_id
-> dim_teams.team_id; dim_teams.franchise_id -> dim_franchises). DuckDB forbids deleting OR
updating a referenced parent key, so on a RE-RUN both delete+insert AND merge (merge does
`UPDATE BY NAME`, which rewrites the PK) fail with "key ... still referenced". Fix: FK-parent
dims (`dim_franchises`, `dim_teams`) are ADDITIVE — `{% if is_incremental() %} where <key>
not in (select <key> from {{ this }}) {% endif %}` — insert only new keys, never touch
existing rows. The first full run worked only because all tables were empty. A full `dbt run`
is now idempotent.

fct_player_game_stats enrichment is joined on (player_id, season, week) from ephemeral int
models: `int_snap_counts` (snaps; keyed by pfr_player_id -> crosswalk source='pfr'),
`int_ngs_player_week` (NGS separation/cushion/RYOE; gsis; NGS numbers the SB week 23 -> remap
to 22), `int_pbp_redzone` (rz/inside-5 carries+targets; reads RAW pbp directly with a 7-col
projection). routes_run and rush_yards_before_contact stay NULL (not in nflverse free feeds).
New `ngs` source has a scraper+staging (one file per type, all seasons). fct_vegas_lines built
from schedule closing lines (sportsbook='nflverse_closing').

pbp is now fully built (2026-06-21): staging skips the full-row `DISTINCT *` for pbp
(`_SKIP_DEDUP` in staging/nflverse.py — it OOMs over 370+ cols and pbp is already unique on
(game_id, play_id)); the no-dedup partitioned COPY is cheap. The pbp staging step calls
`db.connection.refresh_pbp_view()` to create `v_pbp` (full 370-col fidelity over the staged
parquet). `fct_pbp` is a dbt-OWNED trimmed/typed per-play mart (63 cols, keyed game_id/play_id,
skill actors kept as native gsis ids -> join dim_players via crosswalk source='gsis'); since no
migration backs it, the old stub's narrow schema means you must `dbt run --select fct_pbp
--full-refresh` once when the column set changes. Cross-checks: pbp rush_touchdown plays ==
fct_player_game_stats rush_tds per season. Still stubs: `fct_projections`, `fct_team_game_stats`.
