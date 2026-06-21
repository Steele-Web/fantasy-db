-- stg_nflverse_schedules: nflverse game/schedule results, read from the raw layer
-- and clipped to the seasons we ingest weekly stats for. Feeds dim_teams (the
-- per-season team set) and dim_games. Ephemeral — owns no table.
{{ config(materialized="ephemeral") }}

select *
from read_parquet('data/raw/nflverse/schedules/all.parquet')
where season between 2018 and 2025
