"""Load the project's wide Bloomberg event-study export.

The file has 12 deal columns followed by three blocks of 426 trading-day offsets (-420..+5 around
the announcement): target price, target volume, benchmark level, in that order. The blocks are
unlabelled, so the order is checked by tests and by the day-0 diagnostic in the run script.

The file carries no calendar dates for the offsets. Dates here are reconstructed on a plain
weekday calendar anchored on the announce date (weekend announcements roll to the next weekday),
so exchange holidays can shift them by a day. The screen itself only uses offsets.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from marketsurv.data.diagnostics import BLOCK, META_COLUMNS, N_META, OFFSETS, split_blocks

TAKEOVER_TYPES = {"M&A", "BUY"}
MIN_OBS = 400


def _validate_layout(raw: pd.DataFrame) -> None:
    expected_width = N_META + 3 * BLOCK
    if raw.shape[1] != expected_width:
        raise ValueError(f"expected {expected_width} columns, got {raw.shape[1]}")
    missing = set(META_COLUMNS).difference(raw.columns[:N_META])
    if missing:
        raise ValueError(f"metadata columns missing: {', '.join(sorted(missing))}")


def load_datapull(path: str | Path) -> tuple[pd.DataFrame, dict[int, pd.DataFrame]]:
    """Return normalized deals and time series from a Bloomberg CSV export.

    The deal table contains one row per complete, deduplicated takeover. The series mapping is
    keyed by ``deal_id`` and contains ``ret``, ``volume`` and ``mkt`` columns.
    """
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"data pull does not exist: {source}")
    raw = pd.read_csv(source, low_memory=False)
    _validate_layout(raw)
    meta, price, volume, bench = split_blocks(raw)

    complete = np.ones(len(raw), dtype=bool)
    for block in (price, volume, bench):
        complete &= np.isfinite(block).sum(axis=1) >= MIN_OBS
    keep = complete & meta["Deal Type"].isin(TAKEOVER_TYPES).to_numpy()
    # The same target/date can appear on several rows (multiple acquirers): keep the first.
    dup = meta.assign(_d=meta["Announce Date"]).duplicated(["Target Ticker", "_d"]).to_numpy()
    keep &= ~dup

    announce = pd.to_datetime(meta["Announce Date"], format="%m/%d/%Y", errors="coerce")
    invalid_dates = announce.isna() & keep
    if invalid_dates.any():
        rows = ", ".join(map(str, np.flatnonzero(invalid_dates)[:10]))
        raise ValueError(f"invalid announcement date in usable row(s): {rows}")

    deals: list[dict[str, object]] = []
    series: dict[int, pd.DataFrame] = {}
    for i in np.flatnonzero(keep):
        day0 = announce.iloc[i] + pd.offsets.BDay(0)  # weekend -> next weekday
        idx = pd.bdate_range(day0 - pd.offsets.BDay(-OFFSETS[0]), periods=BLOCK)
        series[int(i)] = pd.DataFrame(
            {
                "ret": pd.Series(price[i], idx).pct_change(),
                "volume": volume[i],
                "mkt": pd.Series(bench[i], idx).pct_change(),
            },
            index=idx,
        )
        deals.append(
            {
                "deal_id": int(i),
                "target": meta["Target Name"].iloc[i],
                "ticker": meta["Target Ticker"].iloc[i],
                "acquirer": meta["Acquirer Name"].iloc[i],
                "deal_type": meta["Deal Type"].iloc[i],
                "status": meta["Deal Status"].iloc[i],
                "value_mn": meta["Announced Total Value (mil.)"].iloc[i],
                "announce_date": announce.iloc[i],
                "day0_date": day0,
                "weekend_announce": bool(announce.iloc[i].weekday() >= 5),
            }
        )
    columns = [
        "deal_id",
        "target",
        "ticker",
        "acquirer",
        "deal_type",
        "status",
        "value_mn",
        "announce_date",
        "day0_date",
        "weekend_announce",
    ]
    return pd.DataFrame(deals, columns=columns), series
