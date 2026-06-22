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
`dim_games`, `fct_player_game_stats`, `fct_vegas_lines`, and `fct_pbp` are populated
from nflverse weekly stats, schedules, snap counts, Next Gen Stats, and play-by-play
(2018–2025). Full-fidelity play-by-play also stays in Parquet, exposed as the `v_pbp`
view. `fct_team_game_stats` is still a scaffolded stub that compiles but emits no rows;
`fct_projections` keeps an empty dbt stub but is populated by the projections app below.

### Building projections (`fdb-project`)

A transparent season-long baseline: project each player's opportunity, price it at a
regressed (league-anchored) efficiency, score it through `scoring_settings`, and snapshot
the result to `fct_projections` (`week=0`, `source='my_model_v1'`).

```bash
uv run fdb-project                       # project next season (latest data + 1)
uv run fdb-project --dry-run --limit 20  # preview the top 20, write nothing
uv run fdb-project --season 2024 --through-season 2023   # reproduce a past snapshot
```

Re-running a given `--snapshot-date` overwrites that snapshot (idempotent), so the
backtester only ever sees what was known at that date.

### Grading projections (`fdb-backtest`)

Grade a snapshot against what actually happened. It loads the season-long snapshot
from `fct_projections`, sums each player's realized regular-season line from
`fct_player_game_stats`, scores both through the *same* `scoring_settings` format,
and reports accuracy overall and per position — MAE, RMSE, bias (signed, so you can
see systematic over/under-projection), Pearson + Spearman correlation, and how often
the realized total landed inside the projected floor/ceiling band — plus the biggest
individual misses.

```bash
# First build the snapshot for a past season (data only from before it):
uv run fdb-project  --season 2024 --through-season 2023
uv run fdb-backtest --season 2024                       # my_model_v1, ppr, latest snapshot
uv run fdb-backtest --season 2024 --format half_ppr --min-games 4 --misses 20
```

Actuals are scoped to the regular season (weeks 1–18) to match the 17-game frame the
projections are built on. `--min-games` sets the universe: the default `1` answers
"when a player played, how close were we?"; `0` also counts availability misses
(players projected for points who never took the field).

### Recalibrating the floor/ceiling band (`fdb-calibrate`)

The projection's floor/ceiling band is a per-position coefficient of variation
(`_POSITION_COV` in `apps/projections/model.py`) that started as a guess. `fdb-calibrate`
closes the loop: it reruns the *current* model across several past seasons (in-memory —
no snapshot needed), measures how often each position's realized total actually landed
inside the band, and recommends the cov that makes the band hit its nominal coverage
(~68% for the shipped `±1σ` band), printing a copy-pasteable block.

```bash
uv run fdb-calibrate                       # last 4 projectable seasons, ppr
uv run fdb-calibrate --seasons 2022,2023,2024 --format half_ppr
uv run fdb-calibrate --min-games 8         # calibrate on established roles only
```

`--min-games` chooses the universe the band should cover: `0` (default) prices in
availability risk (busts/injuries count), so it recommends wider bands; a higher value
calibrates on players with a real sample. After pasting a new block into the model,
re-run `fdb-project` to refresh snapshots.

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
  Next Gen Stats, and play-by-play red-zone usage.
- **fct_pbp + v_pbp**: play-by-play is staged (full 370-col fidelity in `v_pbp`) and a
  trimmed, typed per-play mart (`fct_pbp`, keyed on game_id/play_id) is materialized.
  Other marts: `fct_team_game_stats` is a scaffolded stub. `fct_projections` keeps an
  empty dbt stub, but the projections app now populates it (see below).
- **apps**: `fdb-query`, `fdb-project` (season-long projections), `fdb-backtest`
  (grades a projection snapshot vs. realized results), and `fdb-calibrate` (recalibrates
  the projection floor/ceiling band from history) work; `draft_tool` and
  `waiver_analyzer` are stubs.

Add a source by following the nflverse pattern: a `scrapers/<source>.py` that
writes `data/raw/<source>/...`, then a `staging/<source>.py` that cleans it, then
wire it into a dbt model.

## Querying outside this repo

`data/fantasy.duckdb` is a plain file — any DuckDB client can read it:

```sql
-- duckdb data/fantasy.duckdb
SELECT scoring_format, rec_pts FROM scoring_settings;
```
