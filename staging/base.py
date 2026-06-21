"""Shared staging plumbing: locate raw inputs and write partitioned staging output."""

from __future__ import annotations

import shutil

import duckdb

from config.settings import RAW_DIR, staging_path


def raw_glob(source: str, dataset: str) -> str:
    """A recursive parquet glob for one raw dataset, e.g. all season partitions."""
    return (RAW_DIR / source / dataset / "**" / "*.parquet").as_posix()


def has_raw(source: str, dataset: str) -> bool:
    return any((RAW_DIR / source / dataset).glob("**/*.parquet"))


def write_partitioned(
    conn: duckdb.DuckDBPyConnection,
    select_sql: str,
    table: str,
    partition_cols: list[str],
) -> int:
    """Full-refresh a staging table: wipe its directory, then write `select_sql`
    partitioned by `partition_cols` (Hive-style: season=YYYY/week=WW/...).

    Returns the row count written.
    """
    dest = staging_path(table)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    cols = ", ".join(partition_cols)
    conn.execute(
        f"COPY ({select_sql}) TO '{dest.as_posix()}' "
        f"(FORMAT parquet, PARTITION_BY ({cols}), OVERWRITE_OR_IGNORE);"
    )
    written_glob = (dest / "**" / "*.parquet").as_posix()
    count = conn.execute(f"SELECT count(*) FROM read_parquet('{written_glob}');").fetchone()
    return int(count[0])
