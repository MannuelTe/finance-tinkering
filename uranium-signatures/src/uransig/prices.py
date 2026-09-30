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
# Securities an informed trader would most naturally use for a given event (events.csv 'direct')
DIRECT = ("EXC", "ETR", "D", "EIX", "PCG", "UUUU", "CEG", "LEU", "OKLO", "XLU")
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "prices.csv"
VOLUME_CACHE = CACHE.with_name("volume.csv")
SPOT_CACHE = CACHE.with_name("spot_monthly.csv")
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PURANUSDM"


def _download():
    import yfinance as yf

    tickers = list(dict.fromkeys(PROXIES + MARKET + (PHYSICAL,) + DIRECT))
    d = yf.download(tickers, start="2005-01-01", auto_adjust=True, progress=False)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    d["Close"][tickers].dropna(how="all").to_csv(CACHE)
    d["Volume"][tickers].dropna(how="all").to_csv(VOLUME_CACHE)


def load_prices(refresh: bool = False) -> pd.DataFrame:
    """Adjusted closes, one column per ticker, indexed by trading day."""
    if refresh or not CACHE.exists() or not VOLUME_CACHE.exists():
        _download()
    return pd.read_csv(CACHE, index_col=0, parse_dates=True)


def load_volume() -> pd.DataFrame:
    """Daily share volume, same layout as load_prices; call load_prices first."""
    if not VOLUME_CACHE.exists():
        _download()
    return pd.read_csv(VOLUME_CACHE, index_col=0, parse_dates=True)


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
