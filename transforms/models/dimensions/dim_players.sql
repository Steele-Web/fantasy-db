-- dim_players: internal player registry (schema owned by 001_init_dimensions.sql).
-- Bio is sourced from the latest Sleeper snapshot (the crosswalk hub); the stable
-- surrogate player_id comes from int_sleeper_player_keys. draft_* / debut_season
-- are left NULL for nflverse to enrich later (joined via gsis_id through the
-- crosswalk). Upserts on player_id; created_at is preserved across runs.
{{ config(materialized="incremental", unique_key="player_id") }}

with keys as (
    select * from {{ ref("int_sleeper_player_keys") }}
),
bio as (
    select * from {{ ref("stg_sleeper_players") }}
)

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
    b.status                        as status,
    {% if is_incremental() -%}
    coalesce(prev.created_at, current_timestamp) as created_at,
    {%- else -%}
    current_timestamp as created_at,
    {%- endif %}
    current_timestamp               as updated_at
from keys k
join bio b on b.sleeper_id = k.sleeper_id
{% if is_incremental() %}
left join {{ this }} prev on prev.player_id = cast(k.player_id as integer)
{% endif %}
