"""FantasyPros scraper — STUB.

Target raw layout:
    data/raw/fantasypros/projections/snapshot_date=YYYY-MM-DD.parquet
    data/raw/fantasypros/rankings/snapshot_date=YYYY-MM-DD.parquet

Snapshot-dated and append-only: each pull is stamped with the date it was taken
so the backtester only ever sees information available at that time.
"""

from __future__ import annotations

import sys


def run(*_args, **_kwargs) -> int:
    raise NotImplementedError(
        "fantasypros scraper not implemented yet — see module docstring for the target layout."
    )


def main() -> int:
    print("fantasypros scraper is not implemented yet.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
