"""Check a small pilot pull before committing Terminal time to the full 300-500 row pull.

    uv run python scripts/validate_pilot.py data/raw/pilot.csv

Run this on ~10 rows first (see docs/data-pull-checklist.md). It reports, per row: how many of
the 426 offset days are filled in each block, and whether the biggest price move in the -2..+2
window around the announcement lands on day 0 (it should). Fix what it flags before scaling up —
every issue type here is one that cost a full re-pull in a past attempt.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from marketsurv.data.diagnostics import check_rows

PILOT_ROW_LIMIT = 25  # this script is for eyeballing; past that, use the real loader instead


def main(path: str) -> None:
    raw = pd.read_csv(path, low_memory=False)
    if len(raw) > PILOT_ROW_LIMIT:
        print(f"WARNING: {len(raw)} rows — this checker is meant for a small pilot "
              f"(<= {PILOT_ROW_LIMIT}). Reading anyway, but review the output carefully.\n")

    checks = check_rows(raw)
    n_clean = sum(1 for c in checks if not c.issues)
    print(f"{n_clean}/{len(checks)} rows passed with no issues.\n")

    for c in checks:
        status = "OK" if not c.issues else "ISSUES"
        print(f"[{status}] row {c.row}: {c.target} ({c.ticker}), announced {c.announce_date}")
        print(f"        price {c.price_obs}/426, volume {c.volume_obs}/426, "
              f"benchmark {c.bench_obs}/426, peak move at offset {c.peak_offset:+.0f}"
              if c.peak_offset == c.peak_offset else
              f"        price {c.price_obs}/426, volume {c.volume_obs}/426, "
              f"benchmark {c.bench_obs}/426, peak move: unscorable")
        for issue in c.issues:
            print(f"        - {issue}")

    if n_clean < len(checks):
        print("\nDo not scale this pull up yet — fix the issues above and re-run the pilot.")
    else:
        print("\nPilot looks clean. Still do the entity-name and date-alignment spot checks in "
              "docs/data-pull-checklist.md §2 and §4 by hand (they need outside information this "
              "script doesn't have), then scale up.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_pilot.py <pilot.csv>")
    main(sys.argv[1])
