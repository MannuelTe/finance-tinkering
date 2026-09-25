"""Pull event-study datasets from a logged-in Bloomberg Terminal.

Usage:
    uv run --extra bloomberg python scripts/pull_bloomberg.py events data/raw/events.csv
    uv run --extra bloomberg python scripts/pull_bloomberg.py reference data/raw/events.csv

events.csv columns: ticker (Bloomberg, e.g. "ABC US Equity"), event_date (YYYY-MM-DD), benchmark
(e.g. "SPX Index"). Export this input from Bloomberg's M&A screen before running the script.
"""

import argparse
from pathlib import Path

import pandas as pd

from marketsurv.data import bloomberg as bbg

PAD_BEFORE_DAYS = 420  # ~250 est. days + 30 gap + margin for holidays
PAD_AFTER_DAYS = 10
REF_FIELDS = ["ID_ISIN", "ID_MIC_PRIM_EXCH", "LEGAL_ENTITY_IDENTIFIER", "CRNCY", "SECURITY_NAME"]
EVENT_COLUMNS = frozenset({"ticker", "event_date", "benchmark"})


def _read_events(path: str | Path, *, include_benchmark: bool) -> pd.DataFrame:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"event file does not exist: {source}")
    events = pd.read_csv(source)
    required = EVENT_COLUMNS if include_benchmark else EVENT_COLUMNS - {"benchmark"}
    missing = required.difference(events.columns)
    if missing:
        raise ValueError(f"event file is missing columns: {', '.join(sorted(missing))}")
    if events.empty:
        raise ValueError("event file contains no rows")
    if events[list(required)].isna().any().any():
        raise ValueError("event file contains missing values in required columns")
    return events


def pull_events(path: str | Path) -> None:
    """Pull target and benchmark daily histories for an event manifest."""
    ev = _read_events(path, include_benchmark=True)
    ev["event_date"] = pd.to_datetime(ev["event_date"], errors="raise")
    start = (ev["event_date"].min() - pd.Timedelta(days=PAD_BEFORE_DAYS)).strftime("%Y-%m-%d")
    end = (ev["event_date"].max() + pd.Timedelta(days=PAD_AFTER_DAYS)).strftime("%Y-%m-%d")
    bbg.daily_history(sorted(ev["ticker"].unique()), start, end, "daily_targets")
    bbg.daily_history(sorted(ev["benchmark"].unique()), start, end, "daily_benchmarks")


def pull_reference(path: str | Path) -> None:
    """Pull identifier and instrument reference data for an event manifest."""
    ev = _read_events(path, include_benchmark=False)
    bbg.reference(sorted(ev["ticker"].unique()), REF_FIELDS, "reference_targets")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=["events", "reference"])
    parser.add_argument("events_csv", type=Path, help="CSV event manifest")
    arguments = parser.parse_args()
    {"events": pull_events, "reference": pull_reference}[arguments.dataset](arguments.events_csv)
