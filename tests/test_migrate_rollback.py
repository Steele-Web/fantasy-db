"""A failing migration must roll back cleanly and not be recorded as applied."""

import duckdb
import pytest

import db.migrate as migrate
from db.migrate import _applied_versions, apply_pending


def test_failing_migration_rolls_back_and_is_not_recorded(tmp_path, monkeypatch):
    bad = tmp_path / "099_broken.sql"
    bad.write_text("CREATE TABLE ok (id INTEGER); THIS IS NOT VALID SQL;")
    monkeypatch.setattr(migrate, "_discover", lambda: [(99, bad)])

    conn = duckdb.connect(str(tmp_path / "test.duckdb"))
    try:
        with pytest.raises(duckdb.Error):
            apply_pending(conn)

        # The version is not bookkept...
        assert 99 not in _applied_versions(conn)
        # ...and the partial work was rolled back (table from the same file is gone).
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        assert "ok" not in tables
    finally:
        conn.close()
