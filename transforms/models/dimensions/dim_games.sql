-- dim_games: one row per game (schema owned by 001_init_dimensions.sql). Built from
-- the staged nflverse schedule; home/away abbrs map to team_id via dim_teams (with
-- canonical-abbr normalization), and the nflverse game_id is kept as-is so weekly
-- stats join straight onto it. Upserts on game_id.
{{ config(materialized="incremental", unique_key="game_id") }}

with sched as (
    select * from {{ ref("stg_nflverse_schedules") }}
),
teams as (
    select season, abbr, team_id from {{ ref("dim_teams") }}
)

select
    s.game_id                                   as game_id,
    cast(s.season as integer)                   as season,
    cast(s.week as integer)                     as week,
    case when s.game_type = 'REG' then 'REG' else 'POST' end as season_type,
    try_cast(s.gameday as date)                 as game_date,
    try_cast(s.gameday || ' ' || coalesce(s.gametime, '00:00') as timestamp) as kickoff_time,
    h.team_id                                   as home_team_id,
    a.team_id                                   as away_team_id,
    cast(s.home_score as integer)               as home_score,
    cast(s.away_score as integer)               as away_score,
    s.stadium                                   as stadium,
    s.surface                                   as surface,
    s.roof                                      as roof,
    try_cast(s.temp as integer)                 as weather_temp_f,
    try_cast(s.wind as integer)                 as weather_wind_mph,
    cast(null as varchar)                       as weather_desc
from sched s
left join teams h on h.season = s.season and h.abbr = {{ canonical_team("s.home_team") }}
left join teams a on a.season = s.season and a.abbr = {{ canonical_team("s.away_team") }}
