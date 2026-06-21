"""Staging plumbing (base) and the nflverse staging step."""

import duckdb
import pytest

import staging.base as sbase
import staging.nflverse as snfl
from staging.base import has_raw, raw_glob, write_partitioned
from staging.nflverse import STAGEABLE, WEEKLY, _select, stage_dataset


def test_raw_glob_is_recursive_parquet_under_source_dataset():
    g = raw_glob("nflverse", "player_stats")
    assert g.endswith("nflverse/player_stats/**/*.parquet")


def test_has_raw_true_only_when_a_parquet_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(sbase, "RAW_DIR", tmp_path)
    assert has_raw("nflverse", "player_stats") is False

    target = tmp_path / "nflverse" / "player_stats" / "season=2023"
    target.mkdir(parents=True)
    (target / "data.parquet").write_bytes(b"")  # presence is all has_raw checks
    assert has_raw("nflverse", "player_stats") is True


def test_select_requires_partition_keys_non_null():
    sql = _select("some/glob/*.parquet", ["season", "week"])
    assert "SELECT DISTINCT *" in sql
    assert "season IS NOT NULL AND week IS NOT NULL" in sql


def test_write_partitioned_writes_rows_and_full_refreshes(tmp_path, monkeypatch):
    dest = tmp_path / "staging" / "nflverse_player_stats"
    monkeypatch.setattr(sbase, "staging_path", lambda table, *parts: dest)

    conn = duckdb.connect(":memory:")
    try:
        first = write_partitioned(
            conn,
            "SELECT * FROM (VALUES (2023, 1, 'a'), (2023, 2, 'b'), (2024, 1, 'c')) "
            "t(season, week, player)",
            "nflverse_player_stats",
            ["season", "week"],
        )
        assert first == 3
        assert (dest / "season=2023").exists()

        # A second write fully refreshes: only the new rows remain.
        second = write_partitioned(
            conn,
            "SELECT * FROM (VALUES (2025, 9, 'z')) t(season, week, player)",
            "nflverse_player_stats",
            ["season", "week"],
        )
        assert second == 1
        assert not (dest / "season=2023").exists()
    finally:
        conn.close()


def test_stageable_registry_is_consistent():
    assert set(STAGEABLE) == set(WEEKLY) | set(snfl.SEASONAL)
    assert len(STAGEABLE) == len(set(STAGEABLE))  # no dupes


def test_stage_dataset_rejects_unknown_dataset():
    with pytest.raises(ValueError, match="Don't know how to stage"):
        stage_dataset("not_a_real_dataset")


def test_stage_dataset_errors_when_no_raw_present(tmp_path, monkeypatch):
    # Point raw lookups at an empty tree so a valid dataset has nothing to stage.
    monkeypatch.setattr(sbase, "RAW_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match="No raw data"):
        stage_dataset("player_stats")
