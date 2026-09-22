"""Pull the datasets listed in docs/bloomberg-pull.md. Run on the Terminal machine.

Usage:
    uv run --extra bloomberg python scripts/pull_bloomberg.py events data/raw/events.csv
    uv run --extra bloomberg python scripts/pull_bloomberg.py reference data/raw/events.csv

events.csv columns: ticker (Bloomberg, e.g. "ABC US Equity"), event_date (YYYY-MM-DD), benchmark
(e.g. "SPX Index"). Export it from the MA<GO> screen first (see docs).
"""

import argparse

import pandas as pd

from marketsurv.data import bloomberg as bbg

PAD_BEFORE_DAYS = 420  # ~250 est. days + 30 gap + margin for holidays
PAD_AFTER_DAYS = 10
REF_FIELDS = ["ID_ISIN", "ID_MIC_PRIM_EXCH", "LEGAL_ENTITY_IDENTIFIER", "CRNCY", "SECURITY_NAME"]


def pull_events(path: str) -> None:
    ev = pd.read_csv(path, parse_dates=["event_date"])
    start = (ev["event_date"].min() - pd.Timedelta(days=PAD_BEFORE_DAYS)).strftime("%Y-%m-%d")
    end = (ev["event_date"].max() + pd.Timedelta(days=PAD_AFTER_DAYS)).strftime("%Y-%m-%d")
    bbg.daily_history(sorted(ev["ticker"].unique()), start, end, "daily_targets")
    bbg.daily_history(sorted(ev["benchmark"].unique()), start, end, "daily_benchmarks")


def pull_reference(path: str) -> None:
    ev = pd.read_csv(path)
    bbg.reference(sorted(ev["ticker"].unique()), REF_FIELDS, "reference_targets")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["events", "reference"])
    ap.add_argument("events_csv")
    a = ap.parse_args()
    {"events": pull_events, "reference": pull_reference}[a.what](a.events_csv)
