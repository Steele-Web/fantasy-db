-- int_nflverse_player_keys: extends the internal surrogate player_id space to every
-- gsis id nflverse knows, so weekly stats (keyed on gsis) always resolve to a
-- registered player. A gsis id Sleeper already carries REUSES Sleeper's player_id
-- (the two sources stay in agreement); a gsis id Sleeper lacks gets a brand-new id
-- minted ABOVE the Sleeper max, ordered by gsis_id for determinism.
--
-- Mirrors int_sleeper_player_keys: dbt-OWNED (no migration backs it), additive, and
-- never disturbs an already-assigned player — delete+insert on gsis_id only ever
-- appends ids not yet present. Run the sleeper keys before this.
{{ config(materialized="incremental", unique_key="gsis_id") }}

with nfl as (
    select distinct gsis_id from {{ ref("stg_nflverse_players") }}
),

-- gsis ids Sleeper already owns -> reuse that player_id (dedup defensively)
sleeper_gsis as (
    select gsis_id, player_id from (
        select
            b.gsis_id,
            k.player_id,
            row_number() over (partition by b.gsis_id order by k.player_id) as rn
        from {{ ref("int_sleeper_player_keys") }} k
        join {{ ref("stg_sleeper_players") }} b on b.sleeper_id = k.sleeper_id
        where b.gsis_id is not null
    ) where rn = 1
),

resolved as (
    select n.gsis_id, sg.player_id as sleeper_player_id
    from nfl n
    left join sleeper_gsis sg on sg.gsis_id = n.gsis_id
)

{% if is_incremental() %}

, todo as (
    select r.gsis_id, r.sleeper_player_id
    from resolved r
    left join {{ this }} e on e.gsis_id = r.gsis_id
    where e.gsis_id is null
),
mx as (
    select greatest(
        coalesce((select max(player_id) from {{ this }}), 0),
        coalesce((select max(player_id) from {{ ref("int_sleeper_player_keys") }}), 0)
    ) as m
)
select
    coalesce(
        t.sleeper_player_id,
        (select m from mx) + row_number() over (
            partition by (t.sleeper_player_id is null) order by t.gsis_id
        )
    ) as player_id,
    t.gsis_id
from todo t

{% else %}

select
    coalesce(
        r.sleeper_player_id,
        (select coalesce(max(player_id), 0) from {{ ref("int_sleeper_player_keys") }})
            + row_number() over (
                partition by (r.sleeper_player_id is null) order by r.gsis_id
            )
    ) as player_id,
    r.gsis_id
from resolved r

{% endif %}
