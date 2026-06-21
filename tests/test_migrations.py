"""The migration runner applies all SQL files and is idempotent."""

import duckdb

from db.migrate import _applied_versions, _discover, apply_pending


def test_discover_finds_numbered_migrations():
    versions = [v for v, _ in _discover()]
    assert versions == sorted(versions)
    assert len(versions) == len(set(versions))
    assert 1 in versions  # 001_init_dimensions.sql


def test_apply_pending_creates_schema_and_is_idempotent(tmp_path):
    conn = duckdb.connect(str(tmp_path / "test.duckdb"))
    try:
        ran = apply_pending(conn)
        assert ran, "expected migrations to run on a fresh DB"

        tables = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        assert {"dim_players", "fct_player_game_stats", "scoring_settings"} <= tables

        # Seeded scoring formats present.
        rows = conn.execute("SELECT scoring_format FROM scoring_settings").fetchall()
        formats = {r[0] for r in rows}
        assert {"ppr", "half_ppr", "standard"} <= formats

        # Second run applies nothing.
        assert apply_pending(conn) == []
        assert len(_applied_versions(conn)) == len(_discover())
    finally:
        conn.close()
