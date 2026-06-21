-- dim_teams: one row per team per season (schema owned by 001_init_dimensions.sql).
-- TODO: derive from staged nflverse schedules + a maintained franchise map, wiring
-- franchise_id across relocations. Full-column shell; emits no rows yet.
{{ config(materialized="incremental", unique_key="team_id") }}

select
    cast(null as integer)   as team_id,
    cast(null as integer)   as franchise_id,
    cast(null as integer)   as season,
    cast(null as varchar)   as abbr,
    cast(null as varchar)   as city,
    cast(null as varchar)   as name,
    cast(null as varchar)   as conference,
    cast(null as varchar)   as division
where false
