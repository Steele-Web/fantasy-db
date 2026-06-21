-- int_pbp_redzone: per (player, season, week) red-zone (yardline <= 20) and inside-5
-- carry/target counts, derived from play-by-play. Reads the raw pbp parquet directly
-- with a tight column projection — pbp is 372 columns, so a full staging pass blows
-- memory, but the columnar read of seven fields and a group-by is cheap. Rusher /
-- receiver ids are gsis (-> player_id via the crosswalk). Ephemeral — joined into
-- fct_player_game_stats on (player_id, season, week).
{{ config(materialized="ephemeral") }}

with plays as (
    select season, week, yardline_100, rush_attempt, pass_attempt,
           rusher_player_id, receiver_player_id
    from read_parquet(
        'data/raw/nflverse/pbp/**/*.parquet',
        hive_partitioning = true, union_by_name = true
    )
),
rush as (
    select
        rusher_player_id as gsis, season, week,
        count(*) filter (where yardline_100 <= 20) as rz_carries,
        count(*) filter (where yardline_100 <= 5)  as inside_5_carries
    from plays
    where rush_attempt = 1 and rusher_player_id is not null
    group by 1, 2, 3
),
rec as (
    select
        receiver_player_id as gsis, season, week,
        count(*) filter (where yardline_100 <= 20) as rz_targets,
        count(*) filter (where yardline_100 <= 5)  as inside_5_targets
    from plays
    where pass_attempt = 1 and receiver_player_id is not null
    group by 1, 2, 3
),
combined as (
    select
        coalesce(rush.gsis, rec.gsis)       as gsis,
        coalesce(rush.season, rec.season)   as season,
        coalesce(rush.week, rec.week)       as week,
        coalesce(rush.rz_carries, 0)        as rz_carries,
        coalesce(rush.inside_5_carries, 0)  as inside_5_carries,
        coalesce(rec.rz_targets, 0)         as rz_targets,
        coalesce(rec.inside_5_targets, 0)   as inside_5_targets
    from rush
    full outer join rec
        on rush.gsis = rec.gsis and rush.season = rec.season and rush.week = rec.week
),
gsis_map as (
    select source_id as gsis, player_id
    from {{ ref("player_id_crosswalk") }}
    where source = 'gsis'
)

select
    g.player_id                         as player_id,
    cast(c.season as integer)           as season,
    cast(c.week as integer)             as week,
    cast(c.rz_carries as integer)       as rz_carries,
    cast(c.rz_targets as integer)       as rz_targets,
    cast(c.inside_5_carries as integer) as inside_5_carries,
    cast(c.inside_5_targets as integer) as inside_5_targets
from combined c
join gsis_map g on g.gsis = c.gsis
