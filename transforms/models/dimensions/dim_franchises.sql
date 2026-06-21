-- dim_franchises: the 32 modern franchise identities (groups teams across
-- relocations). Hand-maintained reference data; dim_teams references franchise_id.
-- Schema owned by 001_init_dimensions.sql. dim_teams holds a foreign key to
-- franchise_id, and DuckDB forbids deleting OR updating a referenced parent key
-- (both delete+insert and merge touch it). So this model is additive: on a re-run it
-- inserts only brand-new franchise_ids and never disturbs existing referenced rows.
{{ config(materialized="incremental", unique_key="franchise_id") }}

select
    cast(franchise_id as integer) as franchise_id,
    canonical_name                as canonical_name
from (values
    (1,  'Cardinals'),
    (2,  'Falcons'),
    (3,  'Ravens'),
    (4,  'Bills'),
    (5,  'Panthers'),
    (6,  'Bears'),
    (7,  'Bengals'),
    (8,  'Browns'),
    (9,  'Cowboys'),
    (10, 'Broncos'),
    (11, 'Lions'),
    (12, 'Packers'),
    (13, 'Texans'),
    (14, 'Colts'),
    (15, 'Jaguars'),
    (16, 'Chiefs'),
    (17, 'Chargers'),
    (18, 'Rams'),
    (19, 'Raiders'),
    (20, 'Dolphins'),
    (21, 'Vikings'),
    (22, 'Patriots'),
    (23, 'Saints'),
    (24, 'Giants'),
    (25, 'Jets'),
    (26, 'Eagles'),
    (27, 'Steelers'),
    (28, 'Seahawks'),
    (29, '49ers'),
    (30, 'Buccaneers'),
    (31, 'Titans'),
    (32, 'Commanders')
) as f(franchise_id, canonical_name)
{% if is_incremental() %}
where franchise_id not in (select franchise_id from {{ this }})
{% endif %}
