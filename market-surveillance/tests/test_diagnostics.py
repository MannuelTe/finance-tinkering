import numpy as np
import pandas as pd

from marketsurv.data.diagnostics import BLOCK, check_rows

META = ["Deal Type", "Announce Date", "Target Name", "Acquirer Name", "Seller Name",
        "Announced Total Value (mil.)", "Payment Type", "TV/EBITDA", "Deal Status",
        "Target Ticker", "Acquirer Ticker", "Seller Ticker"]


def make_row(price=None, volume=None, bench=None):
    n = np.arange(BLOCK)
    price = np.full(BLOCK, np.nan) if price is None else price
    volume = 1000 + n if volume is None else volume
    bench = 500 + n * 0.1 if bench is None else bench
    meta = ["M&A", "3/23/2026", "Target", "Acq", None, 100.0, "Cash", None, "Pending",
            "AAA IM", "B", ""]
    return meta + list(price) + list(volume) + list(bench)


def df(rows):
    return pd.DataFrame(rows, columns=META + [f"c{i}" for i in range(3 * BLOCK)])


def test_flags_missing_price_block():
    checks = check_rows(df([make_row()]))
    assert any("no price data" in i for i in checks[0].issues)


def test_flags_truncated_fill():
    price = np.full(BLOCK, np.nan)
    price[:101] = 10 + np.arange(101) * 0.01  # matches the pull-2 failure: only 101/426 filled
    checks = check_rows(df([make_row(price=price)]))
    assert any("only 101/426" in i for i in checks[0].issues)


def test_flags_misaligned_jump_before_day_zero():
    pos0 = int(np.flatnonzero(np.arange(-420, 6) == 0)[0])
    price = 10 + np.arange(BLOCK) * 0.001
    price[pos0 - 1 :] += 2.0  # the jump happens a day early relative to the announce date
    checks = check_rows(df([make_row(price=price)]))
    assert any("offset -1" in i or "offset -2" in i for i in checks[0].issues)


def test_clean_row_has_no_issues():
    pos0 = int(np.flatnonzero(np.arange(-420, 6) == 0)[0])
    price = 10 + np.arange(BLOCK) * 0.001
    price[pos0:] += 2.0
    checks = check_rows(df([make_row(price=price)]))
    assert checks[0].issues == []
