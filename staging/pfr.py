"""Pro Football Reference raw -> staging — STUB.

Read data/raw/pfr/<table>/... , coerce types, dedup, and write
data/staging/pfr_<table>/season=YYYY/week=WW/. Follow the pattern in
staging.nflverse (use staging.base.write_partitioned).
"""

from __future__ import annotations

import sys


def run(*_args, **_kwargs) -> int:
    raise NotImplementedError("pfr staging not implemented yet.")


def main() -> int:
    print("pfr staging is not implemented yet.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
