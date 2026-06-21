-- fct_vegas_lines: betting lines per game (schema owned by 002_add_marts.sql; upserts
-- on (game_id, snapshot_at, sportsbook)). The table is designed to hold many snapshots
-- per game, but the only free historical source is the nflverse schedule's CLOSING
-- consensus line — so we record one snapshot per game, stamped at kickoff and labelled
-- sportsbook='nflverse_closing'. When a live odds feed is wired up it appends here
-- under its own sportsbook label without disturbing these rows.
--
-- nflverse spread_line is from the home perspective (positive = home favored), so the
-- home betting handicap is its negation. Implied totals split the total by the spread:
-- home = total/2 - spread_home/2, away = total/2 + spread_home/2.
{{ config(materialized="incremental", unique_key=["game_id", "snapshot_at", "sportsbook"]) }}

with sched as (
    select * from {{ ref("stg_nflverse_schedules") }}
),
lines as (
    select
        game_id,
        try_cast(gameday || ' ' || coalesce(gametime, '00:00') as timestamp) as snapshot_at,
        cast(-spread_line as decimal(4,1))      as spread_home,
        cast(spread_line as decimal(4,1))       as spread_away,
        cast(total_line as decimal(4,1))        as total,
        cast(home_moneyline as integer)         as home_moneyline,
        cast(away_moneyline as integer)         as away_moneyline
    from sched
    where gameday is not null
      and (spread_line is not null or total_line is not null)
)

select
    game_id,
    snapshot_at,
    'nflverse_closing'                          as sportsbook,
    spread_home,
    spread_away,
    total,
    home_moneyline,
    away_moneyline,
    cast(total / 2.0 - spread_home / 2.0 as decimal(4,1)) as home_implied_total,
    cast(total / 2.0 + spread_home / 2.0 as decimal(4,1)) as away_implied_total
from lines
where snapshot_at is not null
