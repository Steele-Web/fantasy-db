"""NFL Next Gen Stats scraper — STUB.

Target raw layout:
    data/raw/ngs/passing/season=YYYY/week=WW.parquet
    data/raw/ngs/rushing/season=YYYY/week=WW.parquet
    data/raw/ngs/receiving/season=YYYY/week=WW.parquet

NGS is distributed via nflverse releases (ngs_<type>.csv.gz / parquet), so this
can mirror scrapers.nflverse: read the remote asset and write to the raw layer.
"""

from __future__ import annotations

import sys


def run(*_args, **_kwargs) -> int:
    raise NotImplementedError(
        "ngs scraper not implemented yet — see module docstring for the target layout."
    )


def main() -> int:
    print("ngs scraper is not implemented yet.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
