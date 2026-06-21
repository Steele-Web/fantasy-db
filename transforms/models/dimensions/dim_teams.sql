-- dim_teams: one row per team per season (schema owned by 001_init_dimensions.sql).
-- The seasonal (season, abbr) pairs are derived from the nflverse schedule; the
-- city/name/conference/division come from a static franchise map. Abbreviations are
-- franchise-CANONICAL (e.g. the 2018-19 Raiders carry LV, not OAK) so weekly stats
-- — which already use canonical abbrs — join cleanly; franchise_id still groups the
-- relocation. team_id = season*100 + franchise_id is stable and deterministic.
-- dim_games holds a foreign key to team_id, and DuckDB forbids deleting OR updating a
-- referenced parent key (both delete+insert and merge touch it). So this model is
-- additive: on a re-run it inserts only brand-new team_ids (e.g. a newly ingested
-- season) and never disturbs existing referenced rows.
{{ config(materialized="incremental", unique_key="team_id") }}

with team_meta as (
    select * from (values
        -- abbr, franchise_id, city,            name,         conference, division
        ('ARI', 1,  'Arizona',       'Cardinals',  'NFC', 'West'),
        ('ATL', 2,  'Atlanta',       'Falcons',    'NFC', 'South'),
        ('BAL', 3,  'Baltimore',     'Ravens',     'AFC', 'North'),
        ('BUF', 4,  'Buffalo',       'Bills',      'AFC', 'East'),
        ('CAR', 5,  'Carolina',      'Panthers',   'NFC', 'South'),
        ('CHI', 6,  'Chicago',       'Bears',      'NFC', 'North'),
        ('CIN', 7,  'Cincinnati',    'Bengals',    'AFC', 'North'),
        ('CLE', 8,  'Cleveland',     'Browns',     'AFC', 'North'),
        ('DAL', 9,  'Dallas',        'Cowboys',    'NFC', 'East'),
        ('DEN', 10, 'Denver',        'Broncos',    'AFC', 'West'),
        ('DET', 11, 'Detroit',       'Lions',      'NFC', 'North'),
        ('GB',  12, 'Green Bay',     'Packers',    'NFC', 'North'),
        ('HOU', 13, 'Houston',       'Texans',     'AFC', 'South'),
        ('IND', 14, 'Indianapolis',  'Colts',      'AFC', 'South'),
        ('JAX', 15, 'Jacksonville',  'Jaguars',    'AFC', 'South'),
        ('KC',  16, 'Kansas City',   'Chiefs',     'AFC', 'West'),
        ('LAC', 17, 'Los Angeles',   'Chargers',   'AFC', 'West'),
        ('LA',  18, 'Los Angeles',   'Rams',       'NFC', 'West'),
        ('LV',  19, 'Las Vegas',     'Raiders',    'AFC', 'West'),
        ('MIA', 20, 'Miami',         'Dolphins',   'AFC', 'East'),
        ('MIN', 21, 'Minnesota',     'Vikings',    'NFC', 'North'),
        ('NE',  22, 'New England',   'Patriots',   'AFC', 'East'),
        ('NO',  23, 'New Orleans',   'Saints',     'NFC', 'South'),
        ('NYG', 24, 'New York',      'Giants',     'NFC', 'East'),
        ('NYJ', 25, 'New York',      'Jets',       'AFC', 'East'),
        ('PHI', 26, 'Philadelphia',  'Eagles',     'NFC', 'East'),
        ('PIT', 27, 'Pittsburgh',    'Steelers',   'AFC', 'North'),
        ('SEA', 28, 'Seattle',       'Seahawks',   'NFC', 'West'),
        ('SF',  29, 'San Francisco', '49ers',      'NFC', 'West'),
        ('TB',  30, 'Tampa Bay',     'Buccaneers', 'NFC', 'South'),
        ('TEN', 31, 'Tennessee',     'Titans',     'AFC', 'South'),
        ('WAS', 32, 'Washington',    'Commanders', 'NFC', 'East')
    ) as t(abbr, franchise_id, city, name, conference, division)
),

season_teams as (
    select distinct season, {{ canonical_team("team") }} as abbr
    from (
        select season, home_team as team from {{ ref("stg_nflverse_schedules") }}
        union all
        select season, away_team as team from {{ ref("stg_nflverse_schedules") }}
    )
)

select
    cast(st.season * 100 + m.franchise_id as integer) as team_id,
    cast(m.franchise_id as integer)                   as franchise_id,
    cast(st.season as integer)                        as season,
    m.abbr                                            as abbr,
    m.city                                            as city,
    m.name                                            as name,
    m.conference                                      as conference,
    m.division                                        as division
from season_teams st
join team_meta m on m.abbr = st.abbr
{% if is_incremental() %}
where (st.season * 100 + m.franchise_id) not in (select team_id from {{ this }})
{% endif %}
