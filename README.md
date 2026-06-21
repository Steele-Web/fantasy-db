# fantasy-db

A Python data pipeline that ingests NFL stats from multiple sources into a local
**DuckDB** for fantasy football analytics. Data flows in one direction through a
medallion layout — **raw → staging → marts** — so every layer is reproducible
from the one before it.

```
scrapers/  → data/raw/      (untouched source-of-truth Parquet)
staging/   → data/staging/  (cleaned, typed, validated Parquet)
transforms/ (dbt) → data/fantasy.duckdb  (dimensions + fact marts)
apps/      ← read only from marts + dimensions
```

The crosswalk (`player_id_crosswalk`) is the keystone: every fact table uses an
internal `player_id`, and the crosswalk translates each source's native IDs during
the staging→mart step. Snapshotted tables (projections, rankings, vegas lines,
status) are append-only because their history is what makes the backtester valid.

## Layout

| path           | what it is                                                       |
|----------------|------------------------------------------------------------------|
| `scrapers/`    | one module per source; writes `data/raw/<source>/...`            |
| `staging/`     | raw→staging cleaning; writes `data/staging/<table>/...`          |
| `transforms/`  | dbt project (staging→marts) building `data/fantasy.duckdb`       |
| `db/`          | DuckDB connection + hand-rolled SQL migration runner             |
| `apps/`        | projections, draft tool, waiver analyzer, backtester             |
| `config/`      | `scoring.yaml`, `leagues.yaml`, `sources.yaml` + path settings   |
| `data/`        | the raw/staging Parquet lake and the `fantasy.duckdb` file       |
| `tests/`       | pytest suite                                                     |

## Setup

Uses [uv](https://docs.astral.sh/uv/). Install dependencies into a managed venv:

```bash
uv sync                       # core deps
uv sync --extra transforms    # also install dbt (for the marts build)
```

## Usage

```bash
uv run fdb-migrate                       # create/upgrade the DuckDB schema
uv run fdb-ingest --list                 # show sources
uv run fdb-ingest nflverse               # scrape all nflverse datasets -> data/raw/
uv run fdb-ingest nflverse:player_stats  # just one dataset
uv run fdb-stage  nflverse               # raw -> data/staging/
uv run fdb-query                         # example read

# pick seasons for per-season datasets:
SEASONS=2022,2023 uv run fdb-ingest nflverse:pbp
```

Override the DB location with `DB_PATH`, the data root with `DATA_DIR`, and the
default seasons (2020–2024) with `SEASONS`. See `config/settings.py`.

### Building marts (dbt)

```bash
uv run --extra transforms dbt run --project-dir transforms --profiles-dir transforms
```

The player-game pipeline is built end-to-end: `dim_franchises`, `dim_teams`,
`dim_games`, `fct_player_game_stats`, and `fct_vegas_lines` are populated from nflverse
weekly stats, schedules, snap counts, Next Gen Stats, and play-by-play (2018–2025).
The remaining marts (`fct_projections`, `fct_team_game_stats`, `fct_pbp`) are still
scaffolded stubs that compile but emit no rows.

## Status

- **nflverse** scraper + staging: working end-to-end.
- **sleeper** scraper + staging: working end-to-end. Its players list is the
  crosswalk hub — one snapshot builds `dim_players` (bio) and
  `player_id_crosswalk` (sleeper, gsis, espn, yahoo, sportradar, rotowire,
  rotoworld, stats, swish, fantasy_data, oddsjam). Pull on a cadence:
  `fdb-ingest sleeper && fdb-stage sleeper`, then `dbt run`.
- **ngs** scraper + staging: working end-to-end (passing/rushing/receiving Next Gen
  Stats from nflverse releases). **pfr, vegas, fantasypros**: stubs with the target
  raw layout documented in each module.
- **dim_players + player_id_crosswalk**: built from sleeper, extended with the
  nflverse players master (gsis ids + bio for historical players sleeper omits).
- **dim_franchises / dim_teams / dim_games / fct_player_game_stats / fct_vegas_lines**:
  built for 2018–2025 from nflverse schedules + weekly stats, enriched with snap counts,
  Next Gen Stats, and play-by-play red-zone usage. Other marts: scaffolded stubs.
- **apps**: `fdb-query` works; the four app packages are stubs.

Add a source by following the nflverse pattern: a `scrapers/<source>.py` that
writes `data/raw/<source>/...`, then a `staging/<source>.py` that cleans it, then
wire it into a dbt model.

## Querying outside this repo

`data/fantasy.duckdb` is a plain file — any DuckDB client can read it:

```sql
-- duckdb data/fantasy.duckdb
SELECT scoring_format, rec_pts FROM scoring_settings;
```
