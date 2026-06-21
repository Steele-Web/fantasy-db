-- fct_player_game_stats: the headline mart — one unified row per player per game,
-- merging nflverse player_stats + snap counts + NGS, keyed on internal player_id.
-- Schema owned by 002_add_marts.sql; dbt upserts on (player_id, game_id).
--
-- TODO: replace this shell with the real build:
--   with staged as (
--       select * from read_parquet(
--           'data/staging/nflverse_player_stats/**/*.parquet',
--           hive_partitioning = true, union_by_name = true)
--   )
--   ... join snap_counts + ngs, translate source ids -> player_id via
--   player_id_crosswalk, map team/opponent abbrs -> team_id, derive game_id.
-- Full-column shell so the upsert column-matches the table; emits no rows yet.
{{ config(materialized="incremental", unique_key=["player_id", "game_id"]) }}

select
    cast(null as integer)       as player_id,
    cast(null as varchar)       as game_id,
    cast(null as integer)       as season,
    cast(null as integer)       as week,
    cast(null as integer)       as team_id,
    cast(null as integer)       as opponent_id,
    cast(null as varchar)       as position,
    cast(null as integer)       as offensive_snaps,
    cast(null as decimal(5,2))  as offensive_snap_pct,
    cast(null as integer)       as routes_run,
    cast(null as integer)       as pass_attempts,
    cast(null as integer)       as pass_completions,
    cast(null as integer)       as pass_yards,
    cast(null as integer)       as pass_tds,
    cast(null as integer)       as interceptions,
    cast(null as integer)       as sacks_taken,
    cast(null as integer)       as pass_air_yards,
    cast(null as decimal(7,3))  as pass_epa,
    cast(null as decimal(5,2))  as cpoe,
    cast(null as integer)       as rush_attempts,
    cast(null as integer)       as rush_yards,
    cast(null as integer)       as rush_tds,
    cast(null as decimal(6,2))  as rush_yards_before_contact,
    cast(null as decimal(6,2))  as rush_yards_over_expected,
    cast(null as integer)       as targets,
    cast(null as integer)       as receptions,
    cast(null as integer)       as rec_yards,
    cast(null as integer)       as rec_tds,
    cast(null as integer)       as air_yards,
    cast(null as integer)       as yac,
    cast(null as decimal(5,2))  as target_share,
    cast(null as decimal(5,2))  as air_yards_share,
    cast(null as decimal(4,2))  as avg_separation,
    cast(null as decimal(4,2))  as avg_cushion,
    cast(null as integer)       as rz_carries,
    cast(null as integer)       as rz_targets,
    cast(null as integer)       as inside_5_carries,
    cast(null as integer)       as inside_5_targets,
    cast(null as integer)       as fumbles,
    cast(null as integer)       as fumbles_lost,
    cast(null as integer)       as two_pt_conversions,
    cast(null as timestamp)     as ingested_at
where false
