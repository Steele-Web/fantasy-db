---
name: sleeper-crosswalk
description: fantasy-db — how dim_players / player_id_crosswalk are built and how the internal player_id surrogate is minted
metadata:
  type: project
---

In fantasy-db the Sleeper players list (`/players/nfl`, ~12k rows) is the **crosswalk
hub**: each player object carries foreign ids (gsis, espn, yahoo, sportradar,
rotowire, rotoworld, stats, swish, fantasy_data, oddsjam), so one snapshot builds
both `dim_players` (bio) and `player_id_crosswalk` (unpivoted source/source_id rows).
Pipeline: `fdb-ingest sleeper` → `fdb-stage sleeper` → `dbt run`.
`scrapers/sleeper.py`, `staging/sleeper.py`, and dbt models `stg_sleeper_players`
(ephemeral, latest snapshot), `int_sleeper_player_keys`, `dim_players`,
`player_id_crosswalk`.

The internal `player_id` surrogate is minted in **one** place,
`int_sleeper_player_keys` (keyed on Sleeper's player_id), so dim_players and the
crosswalk both read it and there's no circular ref. Strategy = **stable
incremental**: first build numbers all ids 1..N; later builds leave existing ids
untouched and append only new sleeper_ids, numbered from `max(player_id)` upward
ordered by `sleeper_id` ASC (deterministic given the same input). Verified: re-running
dbt does not shift existing player_ids.

`int_sleeper_player_keys` is a **second dbt-owned table** with no migration backing
it — an exception to the [[dbt-migration-ownership]] rule (like `fct_pbp`).
dim_players/crosswalk still upsert into their migration-created tables.

Known limits: ~32 Sleeper rows without `full_name` (team DSTs/placeholders) are
dropped in staging, so DSTs aren't in dim_players yet. nflverse is meant to enrich
draft_*/debut_season later by joining on `source='gsis'` in the crosswalk.
