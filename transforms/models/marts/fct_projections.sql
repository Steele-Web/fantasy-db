-- fct_projections: snapshotted projections (yours + external). Schema owned by
-- 002_add_marts.sql. Append-only by the full natural key so the backtester only
-- sees what was known at each snapshot_date.
-- TODO: union staged fantasypros projections + your model outputs, crosswalk to
-- player_id. Full-column shell; emits no rows yet.
{{ config(materialized="incremental", unique_key=[
    "snapshot_date", "source", "player_id", "season", "week", "scoring_format"
]) }}

select
    cast(null as date)          as snapshot_date,
    cast(null as varchar)       as source,
    cast(null as integer)       as player_id,
    cast(null as integer)       as season,
    cast(null as integer)       as week,
    cast(null as varchar)       as scoring_format,
    cast(null as decimal(5,2))  as projected_points,
    cast(null as decimal(5,2))  as floor,
    cast(null as decimal(5,2))  as ceiling,
    cast(null as decimal(6,2))  as proj_pass_yards,
    cast(null as decimal(4,2))  as proj_pass_tds,
    cast(null as decimal(6,2))  as proj_rush_yards,
    cast(null as decimal(4,2))  as proj_rush_tds,
    cast(null as decimal(5,2))  as proj_receptions,
    cast(null as decimal(6,2))  as proj_rec_yards,
    cast(null as decimal(4,2))  as proj_rec_tds
where false
