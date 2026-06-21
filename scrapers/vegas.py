"""Vegas lines scraper — STUB.

Target raw layout:
    data/raw/vegas/lines/season=YYYY/week=WW.parquet

Pull from an odds API (provider/api_key via env + config/sources.yaml). Capture
the snapshot timestamp on every pull — line *history* is what makes the
backtester valid, so this layer is append-only by snapshot.
"""

from __future__ import annotations

import sys


def run(*_args, **_kwargs) -> int:
    raise NotImplementedError(
        "vegas scraper not implemented yet — see module docstring for the target layout."
    )


def main() -> int:
    print("vegas scraper is not implemented yet.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
