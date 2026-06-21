-- stg_nflverse_players: the nflverse players master (one row per player across all
-- eras), read straight from the raw layer. It is the authoritative source of gsis
-- ids + bio for the thousands of historical players the Sleeper snapshot doesn't
-- carry, so it extends the registry/crosswalk beyond Sleeper's active-leaning
-- universe. Ephemeral — owns no table; just isolates "which columns / which file".
{{ config(materialized="ephemeral") }}

select
    gsis_id,
    display_name                        as full_name,
    first_name                          as first_name,
    last_name                           as last_name,
    position                            as position,
    try_cast(birth_date as date)        as birthdate,
    try_cast(height as integer)         as height_inches,
    try_cast(weight as integer)         as weight_lbs,
    college_name                        as college,
    try_cast(draft_year as integer)     as draft_year,
    try_cast(draft_round as integer)    as draft_round,
    try_cast(draft_pick as integer)     as draft_pick,
    try_cast(rookie_season as integer)  as debut_season,
    lower(status)                       as status,
    pfr_id                              as pfr_id,
    cast(espn_id as varchar)            as espn_id
from read_parquet('data/raw/nflverse/players/all.parquet')
where gsis_id is not null
