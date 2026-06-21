"""Sleeper scraper — STUB.

Target raw layout:
    data/raw/sleeper/players/snapshot_date=YYYY-MM-DD.parquet

Sleeper's public API (https://api.sleeper.app/v1) needs no auth. The players
endpoint is large; pull it on a snapshot cadence rather than every run. Its IDs
feed player_id_crosswalk (source='sleeper').
"""

from __future__ import annotations

import sys


def run(*_args, **_kwargs) -> int:
    raise NotImplementedError(
        "sleeper scraper not implemented yet — see module docstring for the target layout."
    )


def main() -> int:
    print("sleeper scraper is not implemented yet.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
