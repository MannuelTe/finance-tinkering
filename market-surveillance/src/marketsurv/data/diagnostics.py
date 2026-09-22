"""Shared checks for the wide day-offset datapull layout, used both on a small pilot (before
scaling up a Terminal pull) and on the full pull (as a sanity check before analysis)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

N_META = 12
OFFSETS = np.arange(-420, 6)
BLOCK = len(OFFSETS)
POS0 = int(np.flatnonzero(OFFSETS == 0)[0])


@dataclass
class RowCheck:
    row: int
    target: str
    ticker: str
    announce_date: str
    price_obs: int
    volume_obs: int
    bench_obs: int
    peak_offset: float  # offset in -2..+2 with the largest |return|; NaN if unscorable
    issues: list[str]


def split_blocks(raw: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    if raw.shape[1] < N_META + 3 * BLOCK:
        raise ValueError(
            f"expected at least {N_META + 3 * BLOCK} columns (12 meta + 3x{BLOCK} offset "
            f"blocks), got {raw.shape[1]}. Did the export get truncated?"
        )
    meta = raw.iloc[:, :N_META]
    body = raw.iloc[:, N_META : N_META + 3 * BLOCK].apply(pd.to_numeric, errors="coerce")
    body = body.to_numpy()
    return meta, body[:, :BLOCK], body[:, BLOCK : 2 * BLOCK], body[:, 2 * BLOCK :]


def _peak_offset(price_row: np.ndarray) -> float:
    window = price_row[POS0 - 2 : POS0 + 3]
    if np.isfinite(window).sum() < 2:
        return float("nan")
    ret = np.diff(np.log(window))
    if not np.isfinite(ret).any():
        return float("nan")
    return float(OFFSETS[POS0 - 2 : POS0 + 3][1:][np.nanargmax(np.abs(ret))])


def check_rows(raw: pd.DataFrame, min_obs: int = 400) -> list[RowCheck]:
    meta, price, volume, bench = split_blocks(raw)
    out = []
    for i in range(len(raw)):
        issues = []
        p_obs, v_obs, b_obs = (int(np.isfinite(x[i]).sum()) for x in (price, volume, bench))
        if p_obs == 0:
            issues.append("no price data at all — wrong ticker field, or formula didn't fire")
        elif p_obs < min_obs:
            issues.append(f"price has only {p_obs}/{BLOCK} days — fill likely truncated")
        if v_obs < min_obs and p_obs >= min_obs:
            issues.append(f"volume has only {v_obs}/{BLOCK} days but price is complete — "
                           "volume block may be pointing at a different ticker/row")
        if b_obs < min_obs and p_obs >= min_obs:
            issues.append(f"benchmark has only {b_obs}/{BLOCK} days")
        peak = _peak_offset(price[i]) if p_obs >= 4 else float("nan")
        if np.isfinite(peak) and peak < 0:
            issues.append(f"largest price move is at offset {peak:+.0f}, not 0 — "
                           "Announce Date and the price column may be misaligned for this row")
        out.append(RowCheck(
            row=i, target=str(meta.iloc[i]["Target Name"]), ticker=str(meta.iloc[i]["Target Ticker"]),
            announce_date=str(meta.iloc[i]["Announce Date"]),
            price_obs=p_obs, volume_obs=v_obs, bench_obs=b_obs, peak_offset=peak, issues=issues,
        ))
    return out
