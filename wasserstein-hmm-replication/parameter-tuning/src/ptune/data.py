"""Price panels for the two data mappings.

* "repl":  SPY, TLT, GLD, USO, UUP (the replication's guess), from paper-replication's cache.
* "paper": ^GSPC (S&P 500 price index), IEF, GLD, USO, UUP: the mapping that reproduces the
  paper's benchmark numbers (paper_hints.md, section 6). Downloaded once and cached here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PAPER_CACHE = ROOT / "data" / "prices_paper.csv"
PAPER_TICKERS = {"^GSPC": "SPX", "IEF": "IEF", "GLD": "GLD", "USO": "USO", "UUP": "UUP"}


def prices(assets: str = "repl") -> pd.DataFrame:
    from wasserstein_hmm.config import ReplicationConfig
    from wasserstein_hmm.data import load_prices

    if assets == "repl":
        return load_prices(ReplicationConfig())
    if not PAPER_CACHE.exists():
        import yfinance as yf

        raw = yf.download(list(PAPER_TICKERS), start="2005-01-01", end="2026-02-21",
                          auto_adjust=True, progress=False)["Close"]
        PAPER_CACHE.parent.mkdir(parents=True, exist_ok=True)
        raw.rename(columns=PAPER_TICKERS)[list(PAPER_TICKERS.values())].to_csv(PAPER_CACHE)
    p = pd.read_csv(PAPER_CACHE, index_col=0, parse_dates=True)
    p.index = pd.DatetimeIndex(p.index).tz_localize(None).rename("date")
    return p.sort_index().dropna()
