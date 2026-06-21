-- fct_pbp: play-by-play mart. Large; the spec keeps raw pbp in Parquet (see the
-- v_pbp view, created by the pbp staging step) and only materializes a trimmed
-- mart when a model needs it joined.
--
-- TODO: build from the staged pbp parquet:
--   select ... from read_parquet(
--       'data/staging/nflverse_pbp/**/*.parquet',
--       hive_partitioning = true, union_by_name = true)
-- selecting only the columns used downstream, keyed by (game_id, play_id).
-- Empty typed shell for now so the model builds before pbp is staged.
{{ config(materialized="incremental", unique_key=["game_id", "play_id"]) }}

select
    cast(null as varchar) as game_id,
    cast(null as integer) as play_id,
    cast(null as integer) as season,
    cast(null as integer) as week
where false
