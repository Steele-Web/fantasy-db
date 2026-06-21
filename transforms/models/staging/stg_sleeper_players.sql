-- stg_sleeper_players: the latest Sleeper snapshot, read straight from the
-- staging Parquet. Ephemeral (inlined as a CTE) — it owns no table; it just
-- isolates "which snapshot" so dim_players, the crosswalk, and the surrogate
-- model all agree on one set of rows.
{{ config(materialized="ephemeral") }}

with raw as (
    select * from read_parquet(
        'data/staging/sleeper_players/**/*.parquet',
        hive_partitioning = true,
        union_by_name = true
    )
)

select *
from raw
where snapshot_date = (select max(snapshot_date) from raw)
