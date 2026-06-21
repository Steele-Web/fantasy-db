"""Sleeper scraper — pulls the NFL players master list.

Sleeper's public API (https://api.sleeper.app/v1) needs no auth. The players
endpoint returns one big JSON object keyed by Sleeper player_id; each player
carries foreign IDs to many other systems (gsis, espn, yahoo, sportradar,
rotowire, rotoworld, stats, swish, fantasy_data, oddsjam). That makes it the
hub that feeds player_id_crosswalk — one fetch yields a multi-source crosswalk.

The endpoint is large (~12k players, several MB) and changes slowly, so pull it
on a snapshot cadence rather than every run.

Raw layout (Hive-partitioned directory per snapshot, like the nflverse sets):
    data/raw/sleeper/players/snapshot_date=YYYY-MM-DD/data.parquet
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date

import pandas as pd

from config.settings import raw_path
from scrapers.base import http_session, memory_duckdb, source_config, write_parquet

PLAYERS_PATH = "players/nfl"

# Native/foreign ID fields. Sleeper returns several of these as JSON numbers
# (espn_id, yahoo_id, ...); coercing them to strings keeps NULLs from forcing a
# float dtype (which would turn "3139477" into "3139477.0") and matches the
# crosswalk's VARCHAR source_id column.
ID_FIELDS = {
    "player_id",
    "gsis_id",
    "espn_id",
    "yahoo_id",
    "rotowire_id",
    "rotoworld_id",
    "sportradar_id",
    "stats_id",
    "swish_id",
    "fantasy_data_id",
    "oddsjam_id",
    "kalshi_id",
    "pandascore_id",
    "opta_id",
}


def _fetch_players(sess, base_url: str, timeout: int, retries: int) -> dict:
    url = f"{base_url.rstrip('/')}/{PLAYERS_PATH}"
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = sess.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as err:  # noqa: BLE001 - retried below, re-raised after
            last_err = err
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_err}")


def _flatten(players: dict) -> pd.DataFrame:
    """One row per player. Scalars kept as-is; ID fields coerced to clean strings;
    nested values (metadata, fantasy_positions, competitions) JSON-encoded so the
    raw layer stays faithful while remaining flat/typed Parquet."""
    rows: list[dict] = []
    for pid, p in players.items():
        row: dict = {}
        for key, val in p.items():
            if isinstance(val, (list, dict)):
                row[key] = json.dumps(val, separators=(",", ":")) if val else None
            elif key in ID_FIELDS:
                row[key] = str(val) if val not in (None, "") else None
            else:
                row[key] = val
        row.setdefault("player_id", str(pid))
        rows.append(row)
    return pd.DataFrame(rows)


def run(names: list[str] | None = None, *_args, **_kwargs) -> int:
    """Fetch the players list into the raw layer. Returns failure count (0/1)."""
    cfg = source_config("sleeper")
    base_url = cfg.get("base_url", "https://api.sleeper.app/v1")
    timeout = int(cfg.get("request_timeout_seconds", 30))
    retries = int(cfg.get("max_retries", 3))
    snapshot = date.today().isoformat()

    print(f"-> sleeper players (snapshot {snapshot}) ... ", end="", flush=True)
    started = time.monotonic()
    try:
        sess = http_session("sleeper")
        players = _fetch_players(sess, base_url, timeout, retries)
        df = _flatten(players)
        out = raw_path("sleeper", "players", f"snapshot_date={snapshot}", "data.parquet")
        with memory_duckdb() as conn:
            conn.register("players_df", df)
            rows = write_parquet(conn, "SELECT * FROM players_df", out)
        print(f"{rows:,} players -> 1 file in {time.monotonic() - started:.1f}s")
        return 0
    except Exception as err:  # noqa: BLE001 - reported, surfaced as failure count
        print("FAILED")
        print(f"   {str(err).splitlines()[0]}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape the Sleeper players list into data/raw/.")
    parser.parse_args()
    return run(None)


if __name__ == "__main__":
    sys.exit(main())
