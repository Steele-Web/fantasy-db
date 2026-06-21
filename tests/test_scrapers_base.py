"""Shared scraper plumbing: rate limiting, config merge, sessions, parquet writes."""

import duckdb

import scrapers.base as base
from scrapers.base import RateLimiter, http_session, source_config, write_parquet


def test_rate_limiter_zero_per_minute_never_sleeps(monkeypatch):
    calls = []
    monkeypatch.setattr(base.time, "sleep", lambda s: calls.append(s))
    RateLimiter(0).wait()
    assert calls == []


def test_rate_limiter_spaces_consecutive_calls(monkeypatch):
    now = [100.0]
    slept = []
    monkeypatch.setattr(base.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(base.time, "sleep", lambda s: slept.append(s))

    rl = RateLimiter(60)  # one action/sec -> 1.0s min interval
    rl.wait()  # first call: clock is way past the 0.0 seed, so no sleep
    assert slept == []
    rl.wait()  # immediately again: must wait the full interval
    assert slept == [1.0]


def test_source_config_merges_defaults_with_source_override():
    cfg = source_config("nflverse")
    # default-only keys survive...
    assert "request_timeout_seconds" in cfg
    # ...and source-specific keys are present.
    assert cfg["enabled"] is True
    assert cfg["rate_limit_per_minute"] == 60


def test_source_config_unknown_source_returns_defaults_only():
    cfg = source_config("nope-not-a-source")
    assert "user_agent" in cfg  # from defaults
    assert "enabled" not in cfg  # no source block to merge


def test_http_session_carries_configured_user_agent():
    sess = http_session("nflverse")
    try:
        assert sess.headers["User-Agent"] == source_config("nflverse")["user_agent"]
    finally:
        sess.close()


def test_write_parquet_returns_rowcount_and_writes_atomically(tmp_path):
    out = tmp_path / "nested" / "out.parquet"
    conn = duckdb.connect(":memory:")
    try:
        rows = write_parquet(conn, "SELECT * FROM range(5) t(n)", out)
    finally:
        conn.close()

    assert rows == 5
    assert out.exists()
    # The temp staging file must not be left behind after the rename.
    assert not out.with_suffix(out.suffix + ".tmp").exists()


def test_write_parquet_overwrites_existing_file(tmp_path):
    out = tmp_path / "out.parquet"
    conn = duckdb.connect(":memory:")
    try:
        write_parquet(conn, "SELECT * FROM range(3) t(n)", out)
        rows = write_parquet(conn, "SELECT * FROM range(7) t(n)", out)
    finally:
        conn.close()
    assert rows == 7
