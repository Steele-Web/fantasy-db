-- player_id_crosswalk: maps every source's native player id to our internal
-- player_id (schema owned by 001_init_dimensions.sql; upserts on (source, source_id)).
--
-- Sleeper is the hub: its player object carries foreign ids to many systems, so a
-- single snapshot unpivots into crosswalk rows for all of them at once. nflverse,
-- pfr, etc. join in later on the shared keys here (notably source='gsis').
--
-- A source_id can only point at one player_id, so on the off chance Sleeper has a
-- duplicate foreign id we keep the lowest player_id (deterministic) to satisfy the
-- (source, source_id) primary key.
{{ config(materialized="incremental", unique_key=["source", "source_id"]) }}

with players as (
    select cast(k.player_id as integer) as player_id, b.*
    from {{ ref("int_sleeper_player_keys") }} k
    join {{ ref("stg_sleeper_players") }} b on b.sleeper_id = k.sleeper_id
),

unpivoted as (
    select player_id, 'sleeper'      as source, sleeper_id      as source_id from players where sleeper_id      is not null
    union all select player_id, 'gsis',         gsis_id         from players where gsis_id         is not null
    union all select player_id, 'espn',         espn_id         from players where espn_id         is not null
    union all select player_id, 'yahoo',        yahoo_id        from players where yahoo_id        is not null
    union all select player_id, 'rotowire',     rotowire_id     from players where rotowire_id     is not null
    union all select player_id, 'rotoworld',    rotoworld_id    from players where rotoworld_id    is not null
    union all select player_id, 'sportradar',   sportradar_id   from players where sportradar_id   is not null
    union all select player_id, 'stats',        stats_id        from players where stats_id        is not null
    union all select player_id, 'swish',        swish_id        from players where swish_id        is not null
    union all select player_id, 'fantasy_data', fantasy_data_id from players where fantasy_data_id is not null
    union all select player_id, 'oddsjam',      oddsjam_id      from players where oddsjam_id      is not null
),

-- The nflverse master extends the crosswalk to every gsis id (so weekly stats
-- always resolve), plus the pfr/espn ids it carries. For players both sources know
-- the player_id is identical, so these rows just reinforce the Sleeper ones; the
-- qualify below keeps a single deterministic row per (source, source_id).
nflverse_keys as (
    select nk.player_id, nk.gsis_id, p.pfr_id, p.espn_id
    from {{ ref("int_nflverse_player_keys") }} nk
    join {{ ref("stg_nflverse_players") }} p on p.gsis_id = nk.gsis_id
),

nflverse_ids as (
    select player_id, 'gsis' as source, gsis_id  as source_id from nflverse_keys where gsis_id  is not null
    union all select player_id, 'pfr',  pfr_id  from nflverse_keys where pfr_id  is not null
    union all select player_id, 'espn', espn_id from nflverse_keys where espn_id is not null
),

all_ids as (
    select * from unpivoted
    union all
    select * from nflverse_ids
)

select player_id, source, source_id
from all_ids
qualify row_number() over (partition by source, source_id order by player_id) = 1
