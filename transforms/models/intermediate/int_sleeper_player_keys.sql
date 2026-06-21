-- int_sleeper_player_keys: the single source of truth for the internal surrogate
-- player_id, keyed on Sleeper's player_id (the most complete spine). Both
-- dim_players and player_id_crosswalk read from here, so the surrogate is minted
-- in exactly one place and there is no circular ref between those two models.
--
-- Stability: this is the one dbt-OWNED table (no migration backs it — like
-- fct_pbp it's an exception to "migrations own the schema"). On the first build
-- every Sleeper id gets a number 1..N. On later builds existing ids are left
-- untouched; only brand-new Sleeper ids are appended, numbered from max(player_id)
-- upward and ordered by sleeper_id ASC so the same input always yields the same
-- assignment. delete+insert with unique_key=sleeper_id therefore never disturbs
-- an already-assigned player.
{{ config(materialized="incremental", unique_key="sleeper_id") }}

with src as (
    select distinct sleeper_id
    from {{ ref("stg_sleeper_players") }}
    where sleeper_id is not null
)

{% if is_incremental() %}

, new_keys as (
    select s.sleeper_id
    from src s
    left join {{ this }} existing on existing.sleeper_id = s.sleeper_id
    where existing.sleeper_id is null
)

select
    (select coalesce(max(player_id), 0) from {{ this }})
        + row_number() over (order by sleeper_id) as player_id,
    sleeper_id
from new_keys

{% else %}

select
    row_number() over (order by sleeper_id) as player_id,
    sleeper_id
from src

{% endif %}
