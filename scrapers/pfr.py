"""Pro Football Reference scraper — STUB.

Target raw layout (per the project layout):
    data/raw/pfr/game_logs/season=YYYY/week=WW/data.parquet
    data/raw/pfr/snap_counts/season=YYYY/week=WW/data.parquet
    data/raw/pfr/advanced_stats/season=YYYY/week=WW/data.parquet

PFR is rate-limit strict (see config/sources.yaml: ~10 req/min, 6s delay). Use
`scrapers.base.http_session("pfr")` + `RateLimiter(...)`, parse tables with
pandas.read_html, and write with `scrapers.base.write_parquet` (or pandas).
"""

from __future__ import annotations

import sys


def run(*_args, **_kwargs) -> int:
    raise NotImplementedError(
        "pfr scraper not implemented yet — see module docstring for the target layout."
    )


def main() -> int:
    print("pfr scraper is not implemented yet.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
