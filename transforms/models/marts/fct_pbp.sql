-- fct_pbp: play-by-play mart. Raw pbp (~370 cols) stays in Parquet and is exposed as
-- the v_pbp view (created by the pbp staging step); this model materializes the
-- trimmed, typed slice that's actually useful to join — game/play context, the skill
-- actors, outcome flags, and the nflfastR efficiency metrics — keyed on
-- (game_id, play_id). dbt OWNS this table (no migration backs it), so it is safe to
-- --full-refresh when the column set changes. Players keep their native gsis ids
-- (passer/rusher/receiver_player_id); join dim_players via the crosswalk source='gsis'.
{{ config(materialized="incremental", unique_key=["game_id", "play_id"]) }}

with pbp as (
    select * from read_parquet(
        'data/staging/nflverse_pbp/**/*.parquet',
        hive_partitioning = true, union_by_name = true
    )
)

select
    -- Keys / game context
    game_id                                     as game_id,
    cast(play_id as integer)                    as play_id,
    cast(season as integer)                     as season,
    cast(week as integer)                       as week,
    season_type                                 as season_type,
    posteam                                     as posteam,
    defteam                                     as defteam,
    home_team                                   as home_team,
    away_team                                   as away_team,

    -- Situation
    cast(qtr as integer)                        as qtr,
    cast(down as integer)                       as down,
    cast(ydstogo as integer)                    as ydstogo,
    cast(goal_to_go as boolean)                 as goal_to_go,
    cast(yardline_100 as integer)               as yardline_100,
    cast(half_seconds_remaining as integer)     as half_seconds_remaining,
    cast(game_seconds_remaining as integer)     as game_seconds_remaining,
    cast(drive as integer)                      as drive,
    cast(series as integer)                     as series,
    cast(posteam_score as integer)              as posteam_score,
    cast(defteam_score as integer)              as defteam_score,
    cast(score_differential as integer)         as score_differential,

    -- The play
    play_type                                   as play_type,
    "desc"                                      as play_desc,
    cast(yards_gained as integer)               as yards_gained,
    cast(shotgun as boolean)                    as shotgun,
    cast(no_huddle as boolean)                  as no_huddle,
    cast(qb_dropback as boolean)                as qb_dropback,
    cast(qb_scramble as boolean)                as qb_scramble,
    cast(air_yards as integer)                  as air_yards,
    cast(yards_after_catch as integer)          as yards_after_catch,

    -- Skill actors (native gsis ids; map to player_id via crosswalk source='gsis')
    passer_player_id                            as passer_player_id,
    passer_player_name                          as passer_player_name,
    rusher_player_id                            as rusher_player_id,
    rusher_player_name                          as rusher_player_name,
    receiver_player_id                          as receiver_player_id,
    receiver_player_name                        as receiver_player_name,
    td_player_id                                as td_player_id,
    td_player_name                              as td_player_name,

    -- Outcome flags
    cast(pass_attempt as boolean)               as pass_attempt,
    cast(rush_attempt as boolean)               as rush_attempt,
    cast(complete_pass as boolean)              as complete_pass,
    cast(incomplete_pass as boolean)            as incomplete_pass,
    cast(interception as boolean)               as interception,
    cast(sack as boolean)                       as sack,
    cast(fumble as boolean)                     as fumble,
    cast(fumble_lost as boolean)                as fumble_lost,
    cast(touchdown as boolean)                  as touchdown,
    cast(pass_touchdown as boolean)             as pass_touchdown,
    cast(rush_touchdown as boolean)             as rush_touchdown,
    cast(return_touchdown as boolean)           as return_touchdown,
    cast(two_point_attempt as boolean)          as two_point_attempt,
    cast(field_goal_attempt as boolean)         as field_goal_attempt,
    cast(extra_point_attempt as boolean)        as extra_point_attempt,
    cast(kickoff_attempt as boolean)            as kickoff_attempt,
    cast(punt_attempt as boolean)               as punt_attempt,
    cast(penalty as boolean)                    as penalty,
    cast(first_down as boolean)                 as first_down,

    -- nflfastR efficiency metrics
    cast(ep as double)                          as ep,
    cast(epa as double)                         as epa,
    cast(wp as double)                          as wp,
    cast(wpa as double)                         as wpa,
    cast(cp as double)                          as cp,
    cast(cpoe as double)                        as cpoe
from pbp
where game_id is not null and play_id is not null
