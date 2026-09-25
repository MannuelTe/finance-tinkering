import numpy as np
import pandas as pd
import pytest

from marketsurv.data.datapull import BLOCK, N_META, OFFSETS, load_datapull

META = [
    "Deal Type",
    "Announce Date",
    "Target Name",
    "Acquirer Name",
    "Seller Name",
    "Announced Total Value (mil.)",
    "Payment Type",
    "TV/EBITDA",
    "Deal Status",
    "Target Ticker",
    "Acquirer Ticker",
    "Seller Ticker",
]


def make_csv(path, rows):
    cols = META + [f"c{i}" for i in range(3 * BLOCK)]
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)


def row(deal_type="M&A", date="3/21/2026", ticker="AAA IM", blocks=True):
    meta = [deal_type, date, "Target", "Acq", None, 100.0, "Cash", None, "Pending", ticker, "B", ""]
    n = np.arange(BLOCK)
    body = (
        np.concatenate([10 + n * 0.01, 1000 + n, 500 + n * 0.1]) if blocks else [np.nan] * 3 * BLOCK
    )
    return meta + list(body)


def test_keeps_complete_takeovers_only(tmp_path):
    p = tmp_path / "d.csv"
    make_csv(
        p, [row(), row(deal_type="INV", ticker="BBB IM"), row(ticker="CCC IM", blocks=False), row()]
    )  # last row duplicates the first (same ticker and date)
    deals, series = load_datapull(p)
    assert list(deals.ticker) == ["AAA IM"]
    s = series[0]
    assert len(s) == BLOCK and s.index.is_monotonic_increasing


def test_weekend_announce_rolls_to_monday_and_day0_is_offset_zero(tmp_path):
    p = tmp_path / "d.csv"
    make_csv(p, [row(date="3/21/2026")])  # a Saturday
    deals, series = load_datapull(p)
    assert deals.weekend_announce.iloc[0]
    assert deals.day0_date.iloc[0] == pd.Timestamp("2026-03-23")
    assert series[0].index[int(np.flatnonzero(OFFSETS == 0)[0])] == pd.Timestamp("2026-03-23")


def test_rejects_wrong_layout(tmp_path):
    p = tmp_path / "d.csv"
    pd.DataFrame(np.zeros((1, N_META + 5)), columns=[f"c{i}" for i in range(N_META + 5)]).to_csv(
        p, index=False
    )
    with pytest.raises(ValueError):
        load_datapull(p)


def test_rejects_unrecognized_metadata_columns(tmp_path):
    p = tmp_path / "d.csv"
    columns = [f"meta{i}" for i in range(N_META)] + [f"c{i}" for i in range(3 * BLOCK)]
    pd.DataFrame([row()], columns=columns).to_csv(p, index=False)
    with pytest.raises(ValueError, match="metadata columns missing"):
        load_datapull(p)
