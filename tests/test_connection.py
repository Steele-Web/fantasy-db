"""db.connection helpers that don't need a remote/httpfs connection."""

import duckdb

import config.settings as settings
from db.connection import query, refresh_pbp_view


def test_query_returns_rows_as_column_keyed_dicts():
    conn = duckdb.connect(":memory:")
    try:
        rows = query(conn, "SELECT 1 AS id, 'ab' AS name UNION ALL SELECT 2, 'cd' ORDER BY id")
    finally:
        conn.close()
    assert rows == [{"id": 1, "name": "ab"}, {"id": 2, "name": "cd"}]


def test_query_passes_through_parameters():
    conn = duckdb.connect(":memory:")
    try:
        rows = query(conn, "SELECT ? AS n", [42])
    finally:
        conn.close()
    assert rows == [{"n": 42}]


def test_refresh_pbp_view_is_false_when_no_staged_files(tmp_path, monkeypatch):
    # No parquet under the staging dir -> the view can't be built, returns False
    # without ever opening the (network-loading) main connection.
    monkeypatch.setattr(settings, "staging_path", lambda *a, **k: tmp_path)
    assert refresh_pbp_view() is False
