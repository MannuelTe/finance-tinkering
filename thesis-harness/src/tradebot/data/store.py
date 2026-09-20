from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from tradebot.config import settings


def _path_for(symbol: str) -> Path:
    return Path(settings.data_dir) / "bars" / f"{symbol}.parquet"


def write_bars(symbol: str, df: pd.DataFrame) -> None:
    """Append-and-dedupe write. Expects columns: ts, open, high, low, close, volume."""
    path = _path_for(symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_parquet(path)
        df = pd.concat([existing, df]).drop_duplicates(subset="ts").sort_values("ts")
    df.to_parquet(path, index=False)


def read_bars(symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    path = _path_for(symbol)
    if not path.exists():
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    con = duckdb.connect()
    query = "SELECT * FROM read_parquet(?)"
    params: list[object] = [str(path)]
    if start is not None:
        query += " WHERE ts >= ?"
        params.append(start)
        if end is not None:
            query += " AND ts <= ?"
            params.append(end)
    elif end is not None:
        query += " WHERE ts <= ?"
        params.append(end)
    query += " ORDER BY ts"
    return con.execute(query, params).df()
