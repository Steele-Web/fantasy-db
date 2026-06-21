-- int_snap_counts: per (player, season, week) offensive snap usage from the staged
-- nflverse snap_counts feed. That feed keys players by pfr_player_id, so it resolves
-- to the internal player_id via player_id_crosswalk (source='pfr'). Ephemeral —
-- joined into fct_player_game_stats on (player_id, season, week).
{{ config(materialized="ephemeral") }}

with snaps as (
    select * from read_parquet(
        'data/staging/nflverse_snap_counts/**/*.parquet',
        hive_partitioning = true, union_by_name = true
    )
),
pfr as (
    select source_id as pfr_id, player_id
    from {{ ref("player_id_crosswalk") }}
    where source = 'pfr'
)

select
    p.player_id                                 as player_id,
    cast(s.season as integer)                   as season,
    cast(s.week as integer)                     as week,
    cast(sum(s.offense_snaps) as integer)       as offensive_snaps,
    cast(max(s.offense_pct) as decimal(5,2))    as offensive_snap_pct
from snaps s
join pfr p on p.pfr_id = s.pfr_player_id
where s.season is not null and s.week is not null
group by 1, 2, 3
