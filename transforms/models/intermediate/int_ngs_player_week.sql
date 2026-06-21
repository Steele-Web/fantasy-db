-- int_ngs_player_week: per (player, season, week) Next Gen Stats — the receiving
-- separation/cushion and rushing yards-over-expected that the weekly box score can't
-- give. NGS keys players by gsis id (-> player_id via the crosswalk). NGS numbers the
-- Super Bowl week 23 where the rest of the warehouse uses 22, so it is remapped here.
-- Ephemeral — joined into fct_player_game_stats on (player_id, season, week).
{{ config(materialized="ephemeral") }}

with rec as (
    select
        player_gsis_id                              as gsis,
        season,
        case when week = 23 then 22 else week end   as week,
        avg_separation,
        avg_cushion
    from read_parquet(
        'data/staging/ngs_receiving/**/*.parquet',
        hive_partitioning = true, union_by_name = true
    )
),
rush as (
    select
        player_gsis_id                              as gsis,
        season,
        case when week = 23 then 22 else week end   as week,
        rush_yards_over_expected
    from read_parquet(
        'data/staging/ngs_rushing/**/*.parquet',
        hive_partitioning = true, union_by_name = true
    )
),
combined as (
    select
        coalesce(rec.gsis, rush.gsis)       as gsis,
        coalesce(rec.season, rush.season)   as season,
        coalesce(rec.week, rush.week)       as week,
        rec.avg_separation,
        rec.avg_cushion,
        rush.rush_yards_over_expected
    from rec
    full outer join rush
        on rec.gsis = rush.gsis and rec.season = rush.season and rec.week = rush.week
),
gsis_map as (
    select source_id as gsis, player_id
    from {{ ref("player_id_crosswalk") }}
    where source = 'gsis'
)

select
    g.player_id                                     as player_id,
    cast(c.season as integer)                       as season,
    cast(c.week as integer)                         as week,
    cast(c.avg_separation as decimal(4,2))          as avg_separation,
    cast(c.avg_cushion as decimal(4,2))             as avg_cushion,
    cast(c.rush_yards_over_expected as decimal(6,2)) as rush_yards_over_expected
from combined c
join gsis_map g on g.gsis = c.gsis
