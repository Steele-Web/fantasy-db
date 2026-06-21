"""Hand-rolled SQL migration runner for the DuckDB marts/dimensions.

Migrations are numbered ``NNN_name.sql`` files in ``db/migrations/``. Each file is
applied exactly once, in filename order, inside a transaction, and recorded in a
``schema_migrations`` bookkeeping table. Re-running is a no-op once everything is
applied — so ``fdb-migrate`` is safe to run on every checkout.

Usage:
    fdb-migrate              # apply all pending migrations
    fdb-migrate --status     # show applied vs pending, apply nothing
    python -m db.migrate
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import duckdb

from config.settings import DB_PATH, MIGRATIONS_DIR
from db.connection import connect

_VERSION_RE = re.compile(r"^(\d+)_")


def _discover() -> list[tuple[int, Path]]:
    """Return (version, path) for every migration, sorted by version."""
    found: list[tuple[int, Path]] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = _VERSION_RE.match(path.name)
        if not m:
            raise ValueError(f"Migration {path.name!r} must start with a number, e.g. 001_init.sql")
        found.append((int(m.group(1)), path))
    versions = [v for v, _ in found]
    if len(versions) != len(set(versions)):
        raise ValueError(f"Duplicate migration version numbers in {MIGRATIONS_DIR}")
    return found


def _ensure_bookkeeping(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    INTEGER PRIMARY KEY,
            name       VARCHAR NOT NULL,
            applied_at TIMESTAMP DEFAULT current_timestamp
        );
        """
    )


def _applied_versions(conn: duckdb.DuckDBPyConnection) -> set[int]:
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}


def apply_pending(conn: duckdb.DuckDBPyConnection) -> list[Path]:
    """Apply every migration not yet recorded. Returns the files applied."""
    _ensure_bookkeeping(conn)
    applied = _applied_versions(conn)
    ran: list[Path] = []
    for version, path in _discover():
        if version in applied:
            continue
        sql = path.read_text()
        conn.execute("BEGIN TRANSACTION;")
        try:
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?);",
                [version, path.name],
            )
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        ran.append(path)
    return ran


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply DuckDB schema migrations.")
    parser.add_argument("--status", action="store_true", help="Show status, apply nothing.")
    args = parser.parse_args()

    print(f"DB: {DB_PATH}")
    with connect() as conn:
        _ensure_bookkeeping(conn)
        applied = _applied_versions(conn)
        discovered = _discover()

        if args.status:
            for version, path in discovered:
                mark = "applied" if version in applied else "PENDING"
                print(f"  [{mark:>7}] {path.name}")
            if not discovered:
                print("  (no migrations found)")
            return

        ran = apply_pending(conn)
        if ran:
            for path in ran:
                print(f"  applied {path.name}")
            print(f"Done. {len(ran)} migration(s) applied.")
        else:
            print("Already up to date — nothing to apply.")


if __name__ == "__main__":
    sys.exit(main())
