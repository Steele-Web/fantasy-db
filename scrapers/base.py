"""Shared scraper plumbing: a polite HTTP session, a rate limiter, an in-memory
DuckDB for remote-file conversion, and a Parquet writer for the raw layer."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb
import requests

import config


class RateLimiter:
    """Simple sleep-based limiter: at most `per_minute` actions, evenly spaced."""

    def __init__(self, per_minute: int) -> None:
        self._min_interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._last = 0.0

    def wait(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last = time.monotonic()


def source_config(source: str) -> dict:
    """Return the merged config block for a source (defaults + source overrides)."""
    cfg = config.sources()
    merged = dict(cfg.get("defaults", {}))
    merged.update(cfg.get("sources", {}).get(source, {}))
    return merged


def http_session(source: str) -> requests.Session:
    """A requests session carrying the configured User-Agent and timeout default."""
    cfg = source_config(source)
    sess = requests.Session()
    sess.headers["User-Agent"] = cfg.get("user_agent", "fantasy-db/0.1")
    return sess


@contextmanager
def memory_duckdb() -> Iterator[duckdb.DuckDBPyConnection]:
    """An in-memory DuckDB with httpfs loaded — for converting remote files to
    local Parquet without touching (or locking) the main database."""
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("INSTALL httpfs; LOAD httpfs;")
        yield conn
    finally:
        conn.close()


def write_parquet(conn: duckdb.DuckDBPyConnection, select_sql: str, out: Path) -> int:
    """Run `select_sql`, write the result to `out` as Parquet, return row count.

    Writes to a temp file and renames so a failed/partial write never leaves a
    corrupt parquet in the raw tree.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    conn.execute(f"COPY ({select_sql}) TO '{tmp.as_posix()}' (FORMAT parquet);")
    rows = conn.execute(f"SELECT count(*) FROM read_parquet('{tmp.as_posix()}');").fetchone()[0]
    tmp.replace(out)
    return int(rows)
