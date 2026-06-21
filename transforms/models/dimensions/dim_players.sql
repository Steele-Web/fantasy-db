-- dim_players: internal player registry (schema owned by 001_init_dimensions.sql).
-- TODO: build from staged nflverse players/rosters, assigning a stable surrogate
-- player_id and populating player_id_crosswalk from every source's native IDs.
-- Full-column shell so the upsert column-matches the table; emits no rows yet.
{{ config(materialized="incremental", unique_key="player_id") }}

select
    cast(null as integer)   as player_id,
    cast(null as varchar)   as full_name,
    cast(null as varchar)   as first_name,
    cast(null as varchar)   as last_name,
    cast(null as varchar)   as position,
    cast(null as date)      as birthdate,
    cast(null as integer)   as height_inches,
    cast(null as integer)   as weight_lbs,
    cast(null as varchar)   as college,
    cast(null as integer)   as draft_year,
    cast(null as integer)   as draft_round,
    cast(null as integer)   as draft_pick,
    cast(null as integer)   as debut_season,
    cast(null as varchar)   as status,
    cast(null as timestamp) as created_at,
    cast(null as timestamp) as updated_at
where false
