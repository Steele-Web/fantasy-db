-- fct_team_game_stats: one row per team per game (offense + what they allowed),
-- for matchup analysis. Schema owned by 002_add_marts.sql; upsert on (team_id, game_id).
-- TODO: aggregate from staged pbp / team stats. Full-column shell; emits no rows yet.
{{ config(materialized="incremental", unique_key=["team_id", "game_id"]) }}

select
    cast(null as integer)       as team_id,
    cast(null as varchar)       as game_id,
    cast(null as integer)       as season,
    cast(null as integer)       as week,
    cast(null as integer)       as opponent_id,
    cast(null as boolean)       as is_home,
    cast(null as integer)       as points,
    cast(null as integer)       as total_yards,
    cast(null as integer)       as pass_yards,
    cast(null as integer)       as rush_yards,
    cast(null as integer)       as plays,
    cast(null as decimal(4,2))  as seconds_per_play,
    cast(null as decimal(5,2))  as pass_rate,
    cast(null as decimal(5,2))  as pace_neutral,
    cast(null as integer)       as points_allowed,
    cast(null as integer)       as yards_allowed,
    cast(null as integer)       as pass_yards_allowed,
    cast(null as integer)       as rush_yards_allowed,
    cast(null as integer)       as sacks,
    cast(null as integer)       as interceptions
where false
