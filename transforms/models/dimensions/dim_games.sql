-- dim_games: one row per game (schema owned by 001_init_dimensions.sql).
-- TODO: build from staged nflverse schedules, mapping home/away abbrs to team_id
-- via dim_teams and parsing weather/venue. Full-column shell; emits no rows yet.
{{ config(materialized="incremental", unique_key="game_id") }}

select
    cast(null as varchar)   as game_id,
    cast(null as integer)   as season,
    cast(null as integer)   as week,
    cast(null as varchar)   as season_type,
    cast(null as date)      as game_date,
    cast(null as timestamp) as kickoff_time,
    cast(null as integer)   as home_team_id,
    cast(null as integer)   as away_team_id,
    cast(null as integer)   as home_score,
    cast(null as integer)   as away_score,
    cast(null as varchar)   as stadium,
    cast(null as varchar)   as surface,
    cast(null as varchar)   as roof,
    cast(null as integer)   as weather_temp_f,
    cast(null as integer)   as weather_wind_mph,
    cast(null as varchar)   as weather_desc
where false
