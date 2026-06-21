---
name: dbt-migration-ownership
description: fantasy-db — how DuckDB schema ownership is split between hand-rolled migrations and dbt
metadata:
  type: project
---

In fantasy-db, the DuckDB schema (PKs, types, constraints) is owned by hand-rolled
SQL in `db/migrations/` applied by `fdb-migrate` (`db/migrate.py`). dbt does **not**
own that DDL: every model in `transforms/` is `materialized: incremental` with
`on_schema_change: ignore`, so it UPSERTS into the migration-created tables on the
natural key instead of dropping/recreating them. Run `fdb-migrate` before `dbt run`.

Two consequences that bite if forgotten:
- dbt builds the insert from the **target table's** full column list, so each model
  must select every column the migration table has, including default lineage
  columns (`created_at`/`updated_at`, `ingested_at`) — even in empty `where false` stubs.
- `fct_pbp` has no migration table (pbp stays in Parquet via the `v_pbp` view, created
  by the pbp staging step in `db.connection.refresh_pbp_view`), so dbt owns it outright.

Project converted TS→Python on 2026-06-20: uv, medallion raw→staging→marts. Only the
nflverse source is wired end-to-end; other scrapers/apps are stubs. See the project README.
