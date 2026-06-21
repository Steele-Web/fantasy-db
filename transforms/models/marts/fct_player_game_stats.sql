-- fct_player_game_stats: the headline mart — one unified row per player per game.
-- Schema owned by 002_add_marts.sql; dbt upserts on (player_id, game_id).
--
-- Source: staged nflverse weekly player stats (the modern `stats_player` feed). The
-- gsis player_id is translated to the internal player_id via player_id_crosswalk
-- (source='gsis'); team/opponent abbrs map to team_id via dim_teams. game_id is
-- derived by matching (season, week, team) against dim_games rather than the feed's
-- own game_id column, which nflverse only populates for some seasons — the lookup
-- is exact for every season and keeps the FK to dim_games clean. Snap-count and NGS
-- columns (offensive_snaps, routes_run,
-- cpoe-derived separation/cushion, rush_yards_before_contact/over_expected, red-zone
-- usage) stay NULL until those datasets are ingested.
{{ config(materialized="incremental", unique_key=["player_id", "game_id"]) }}

with ps as (
    select * from read_parquet(
        'data/staging/nflverse_player_stats/**/*.parquet',
        hive_partitioning = true, union_by_name = true
    )
),
xwalk as (
    select source_id as gsis_id, player_id
    from {{ ref("player_id_crosswalk") }}
    where source = 'gsis'
),
teams as (
    select season, abbr, team_id from {{ ref("dim_teams") }}
),
-- (season, week, team_id) -> game_id, from both sides of every scheduled game
team_games as (
    select season, week, home_team_id as team_id, game_id from {{ ref("dim_games") }}
    union all
    select season, week, away_team_id as team_id, game_id from {{ ref("dim_games") }}
)

select
    cast(x.player_id as integer)                    as player_id,
    tg.game_id                                      as game_id,
    cast(ps.season as integer)                      as season,
    cast(ps.week as integer)                        as week,
    dt.team_id                                      as team_id,
    dopp.team_id                                    as opponent_id,
    ps.position                                     as position,

    -- Snap counts / usage (need snap_counts/NGS — not yet ingested)
    cast(null as integer)                           as offensive_snaps,
    cast(null as decimal(5,2))                      as offensive_snap_pct,
    cast(null as integer)                           as routes_run,

    -- Passing
    cast(ps.attempts as integer)                    as pass_attempts,
    cast(ps.completions as integer)                 as pass_completions,
    cast(ps.passing_yards as integer)               as pass_yards,
    cast(ps.passing_tds as integer)                 as pass_tds,
    cast(ps.passing_interceptions as integer)       as interceptions,
    cast(ps.sacks_suffered as integer)              as sacks_taken,
    cast(ps.passing_air_yards as integer)           as pass_air_yards,
    cast(ps.passing_epa as decimal(7,3))            as pass_epa,
    cast(ps.passing_cpoe as decimal(5,2))           as cpoe,

    -- Rushing
    cast(ps.carries as integer)                     as rush_attempts,
    cast(ps.rushing_yards as integer)               as rush_yards,
    cast(ps.rushing_tds as integer)                 as rush_tds,
    cast(null as decimal(6,2))                      as rush_yards_before_contact,
    cast(null as decimal(6,2))                      as rush_yards_over_expected,

    -- Receiving
    cast(ps.targets as integer)                     as targets,
    cast(ps.receptions as integer)                  as receptions,
    cast(ps.receiving_yards as integer)             as rec_yards,
    cast(ps.receiving_tds as integer)               as rec_tds,
    cast(ps.receiving_air_yards as integer)         as air_yards,
    cast(ps.receiving_yards_after_catch as integer) as yac,
    cast(ps.target_share as decimal(5,2))           as target_share,
    cast(ps.air_yards_share as decimal(5,2))        as air_yards_share,
    cast(null as decimal(4,2))                      as avg_separation,
    cast(null as decimal(4,2))                      as avg_cushion,

    -- Red zone / high-value (need pbp — not yet ingested)
    cast(null as integer)                           as rz_carries,
    cast(null as integer)                           as rz_targets,
    cast(null as integer)                           as inside_5_carries,
    cast(null as integer)                           as inside_5_targets,

    -- Misc
    cast(coalesce(ps.sack_fumbles, 0)
       + coalesce(ps.rushing_fumbles, 0)
       + coalesce(ps.receiving_fumbles, 0) as integer)            as fumbles,
    cast(coalesce(ps.sack_fumbles_lost, 0)
       + coalesce(ps.rushing_fumbles_lost, 0)
       + coalesce(ps.receiving_fumbles_lost, 0) as integer)       as fumbles_lost,
    cast(coalesce(ps.passing_2pt_conversions, 0)
       + coalesce(ps.rushing_2pt_conversions, 0)
       + coalesce(ps.receiving_2pt_conversions, 0) as integer)    as two_pt_conversions,

    current_timestamp                               as ingested_at
from ps
join xwalk x on x.gsis_id = ps.player_id
join teams dt on dt.season = ps.season and dt.abbr = {{ canonical_team("ps.team") }}
join team_games tg on tg.season = ps.season and tg.week = ps.week and tg.team_id = dt.team_id
left join teams dopp on dopp.season = ps.season and dopp.abbr = {{ canonical_team("ps.opponent_team") }}
where ps.player_id is not null
-- one row per player per game (weekly feed is already 1:1, guard the PK anyway)
qualify row_number() over (partition by x.player_id, tg.game_id order by ps.season) = 1
