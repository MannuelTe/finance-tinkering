"""Daily prices for the tradeable uranium proxies, cached to data/cache/."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Uranium names with a long daily history. KAP.L (Kazatomprom GDR) only has a
# short history on Yahoo, and SRUUF/U-U.TO (Sprott trust) starts in 2021.
PROXIES = ("CCJ", "DNN", "NXE", "URA")
MARKET = ("SPY", "XLE")
PHYSICAL = "U-U.TO"  # Sprott Physical Uranium Trust, USD line: a daily price for pounds held
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "prices.csv"
SPOT_CACHE = CACHE.with_name("spot_monthly.csv")
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PURANUSDM"


def load_prices(refresh: bool = False, path: Path = CACHE) -> pd.DataFrame:
    """Adjusted closes, one column per ticker, indexed by trading day."""
    if path.exists() and not refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    import yfinance as yf

    tickers = list(PROXIES + MARKET + (PHYSICAL,))
    px = yf.download(tickers, start="2005-01-01", auto_adjust=True, progress=False)["Close"]
    px = px[tickers].dropna(how="all")
    path.parent.mkdir(parents=True, exist_ok=True)
    px.to_csv(path)
    return px


def log_returns(px: pd.DataFrame) -> pd.DataFrame:
    """Log returns on the NYSE calendar. The Sprott trust trades in Toronto, whose
    holidays differ; its TSX-only days are dropped rather than splitting windows."""
    px = px[px["SPY"].notna()] if "SPY" in px else px
    return np.log(px).diff().iloc[1:]


def load_spot(refresh: bool = False, path: Path = SPOT_CACHE) -> pd.Series:
    """IMF monthly uranium price via FRED (USD/lb, a monthly average of spot assessments)."""
    if not path.exists() or refresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.read_csv(FRED, index_col=0, parse_dates=True).to_csv(path)
    return pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0].rename("spot")
