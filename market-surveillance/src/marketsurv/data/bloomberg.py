"""Bloomberg Desktop API adapter.

Every export is written below ``data/raw`` (gitignored). A logged-in Bloomberg Terminal and the
optional ``bloomberg`` dependency group are required.
"""

import re
from pathlib import Path

import pandas as pd

DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


def _blp():
    try:
        from xbbg import blp
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Bloomberg support requires: uv sync --extra bloomberg") from e
    return blp


def _output_path(name: str, raw_dir: str | Path) -> Path:
    """Resolve an export name without allowing writes outside the raw-data directory."""
    if not name or Path(name).name != name:
        raise ValueError("name must be a non-empty filename stem")
    destination = Path(raw_dir)
    destination.mkdir(parents=True, exist_ok=True)
    return destination / f"{name}.parquet"


def daily_history(
    tickers: list[str],
    start: str,
    end: str,
    name: str,
    *,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
) -> pd.DataFrame:
    """Pull adjusted daily prices and volume and persist them as Parquet."""
    if not tickers:
        raise ValueError("at least one ticker is required")
    df = _blp().bdh(tickers, ["PX_LAST", "PX_VOLUME"], start, end, adjust="all")
    df.to_parquet(_output_path(name, raw_dir))
    return df


def reference(
    tickers: list[str],
    fields: list[str],
    name: str,
    *,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
) -> pd.DataFrame:
    """Pull reference fields and persist them as Parquet."""
    if not tickers or not fields:
        raise ValueError("at least one ticker and field are required")
    df = _blp().bdp(tickers, fields)
    df.to_parquet(_output_path(name, raw_dir))
    return df


def intraday_bars(
    ticker: str,
    start: str,
    end: str,
    interval_min: int = 1,
    *,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
) -> pd.DataFrame:
    """TRADE bars. Bloomberg only retains a limited intraday window; pull early and cache."""
    if not ticker:
        raise ValueError("ticker is required")
    if interval_min <= 0:
        raise ValueError("interval_min must be positive")
    df = _blp().bdib(ticker, start, end, typ="TRADE", interval=interval_min)
    safe_ticker = re.sub(r"[^A-Za-z0-9_.-]+", "_", ticker).strip("_")
    stem = f"bars_{safe_ticker}_{start[:10]}_{end[:10]}"
    df.to_parquet(_output_path(stem, raw_dir))
    return df
