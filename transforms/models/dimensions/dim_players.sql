-- dim_players: internal player registry (schema owned by 001_init_dimensions.sql).
-- Two bio sources, unioned on the shared surrogate player_id:
--   1. the latest Sleeper snapshot (the crosswalk hub) — keyed via
--      int_sleeper_player_keys; draft_* / debut_season are left NULL there.
--   2. the nflverse players master — for the thousands of (mostly historical)
--      players Sleeper doesn't carry, keyed via int_nflverse_player_keys. Sleeper
--      wins for players both sources know (the nflverse branch excludes any
--      player_id already minted from Sleeper), so bio stays stable.
-- Upserts on player_id; created_at is preserved across runs.
{{ config(materialized="incremental", unique_key="player_id") }}

with sleeper_players as (
    select
        cast(k.player_id as integer)    as player_id,
        b.full_name                     as full_name,
        b.first_name                    as first_name,
        b.last_name                     as last_name,
        b.position                      as position,
        b.birth_date                    as birthdate,
        b.height_inches                 as height_inches,
        b.weight_lbs                    as weight_lbs,
        b.college                       as college,
        cast(null as integer)           as draft_year,
        cast(null as integer)           as draft_round,
        cast(null as integer)           as draft_pick,
        cast(null as integer)           as debut_season,
        b.status                        as status
    from {{ ref("int_sleeper_player_keys") }} k
    join {{ ref("stg_sleeper_players") }} b on b.sleeper_id = k.sleeper_id
),

nflverse_players as (
    select
        cast(nk.player_id as integer)   as player_id,
        p.full_name                     as full_name,
        p.first_name                    as first_name,
        p.last_name                     as last_name,
        p.position                      as position,
        p.birthdate                     as birthdate,
        p.height_inches                 as height_inches,
        p.weight_lbs                    as weight_lbs,
        p.college                       as college,
        p.draft_year                    as draft_year,
        p.draft_round                   as draft_round,
        p.draft_pick                    as draft_pick,
        p.debut_season                  as debut_season,
        p.status                        as status
    from {{ ref("int_nflverse_player_keys") }} nk
    join {{ ref("stg_nflverse_players") }} p on p.gsis_id = nk.gsis_id
    where p.full_name is not null
      and nk.player_id not in (select player_id from {{ ref("int_sleeper_player_keys") }})
),

combined as (
    select * from sleeper_players
    union all
    select * from nflverse_players
)

select
    c.player_id                     as player_id,
    c.full_name                     as full_name,
    c.first_name                    as first_name,
    c.last_name                     as last_name,
    c.position                      as position,
    c.birthdate                     as birthdate,
    c.height_inches                 as height_inches,
    c.weight_lbs                    as weight_lbs,
    c.college                       as college,
    c.draft_year                    as draft_year,
    c.draft_round                   as draft_round,
    c.draft_pick                    as draft_pick,
    c.debut_season                  as debut_season,
    c.status                        as status,
    {% if is_incremental() -%}
    coalesce(prev.created_at, current_timestamp) as created_at,
    {%- else -%}
    current_timestamp as created_at,
    {%- endif %}
    current_timestamp               as updated_at
from combined c
{% if is_incremental() %}
left join {{ this }} prev on prev.player_id = c.player_id
{% endif %}
