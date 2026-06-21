# fantasy-db

A small TypeScript pipeline that ingests NFL stats from [nflverse](https://github.com/nflverse/nflverse-data)
into a local **DuckDB** database for fantasy football analytics.

The job here is **gathering data**. Analytics can live in a separate repo/notebook
that simply opens the same `data/fantasy.duckdb` file.

## How it works

nflverse publishes data as parquet/CSV assets on GitHub releases. DuckDB's
`httpfs` extension reads those URLs directly, so each "ingest" is just a remote
read into a local table — no manual download or parsing step. Every run is a
full refresh (`CREATE OR REPLACE TABLE`), so the DB is always reproducible from
source and is git-ignored.

```
src/
  config.ts                  # DB path + which seasons to pull
  db.ts                      # DuckDB connection (loads httpfs)
  ingest.ts                  # CLI entrypoint
  query.ts                   # example read script
  sources/nflverse/
    datasets.ts              # dataset registry (name → URL builder)
    ingest.ts                # read remote files into a table
data/fantasy.duckdb          # the database (git-ignored, rebuildable)
```

## Setup

```bash
npm install
```

## Usage

```bash
npm run list                 # show available datasets
npm run ingest:all           # ingest every dataset (default seasons)
npm run ingest -- players player_stats   # just these tables
npm run query                # run the example query

# pick seasons for per-season datasets:
SEASONS=2021,2022,2023 npm run ingest -- pbp player_stats
```

Default seasons are 2020–2024 (see `src/config.ts`). Override per-run with the
`SEASONS` env var, or change the DB location with `DB_PATH`.

## Datasets

| table            | scope      | description                              |
|------------------|------------|------------------------------------------|
| `players`        | single     | Master player table (ids, bio, position) |
| `games`          | single     | Schedule/results, lines, metadata        |
| `player_stats`   | per-season | Weekly offensive player stats            |
| `pbp`            | per-season | Play-by-play (nflfastR) — large          |
| `rosters`        | per-season | Season rosters                           |
| `weekly_rosters` | per-season | Week-by-week rosters                     |
| `snap_counts`    | per-season | Player snap counts                       |
| `depth_charts`   | per-season | Team depth charts                        |
| `injuries`       | per-season | Injury reports                           |

Add a source by appending an entry to `DATASETS` in
`src/sources/nflverse/datasets.ts` (confirm the asset URL exists on the
[releases page](https://github.com/nflverse/nflverse-data/releases) first).

## Querying outside this repo

The database is a plain file. Any DuckDB client can read it:

```sql
-- duckdb data/fantasy.duckdb
SELECT season, count(*) FROM player_stats GROUP BY 1 ORDER BY 1;
```
