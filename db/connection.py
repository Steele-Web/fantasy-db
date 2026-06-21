"""DuckDB connection helpers.

A single place to open the database with the extensions we always want loaded
(httpfs, for reading nflverse files straight off GitHub). Everything else —
scrapers, staging, apps — goes through `connect()`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from config.settings import DB_PATH


@contextmanager
def connect(
    path: Path | str = DB_PATH, *, read_only: bool = False
) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open the DuckDB database as a context manager with httpfs loaded.

    Creates the parent directory on first use. Use `read_only=True` from apps so
    multiple readers can share the file while a write job is not running.
    """
    path = Path(path)
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path), read_only=read_only)
    try:
        conn.execute("INSTALL httpfs; LOAD httpfs;")
        yield conn
    finally:
        conn.close()


def query(conn: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> list[dict]:
    """Run a query and return rows as plain dicts (column name -> value)."""
    cur = conn.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def refresh_pbp_view() -> bool:
    """(Re)create the v_pbp view over staged play-by-play Parquet, if any exists.

    DuckDB binds a view's schema at creation time, so the view can only exist once
    there are files to read. Called by the pbp staging step. Returns True if the
    view was created, False if no staged pbp files were found.
    """
    from config.settings import staging_path

    pbp_dir = staging_path("nflverse_pbp")
    if not any(pbp_dir.glob("**/*.parquet")):
        return False
    glob = (pbp_dir / "**" / "*.parquet").as_posix()
    with connect() as conn:
        conn.execute(
            f"CREATE OR REPLACE VIEW v_pbp AS "
            f"SELECT * FROM read_parquet('{glob}', hive_partitioning = true, union_by_name = true);"
        )
    return True
