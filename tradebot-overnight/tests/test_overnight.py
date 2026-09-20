from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from tradebot import overnight
from tradebot.broker.base import Order
from tradebot.broker.ibkr import IBKRBroker, to_ib_order
from tradebot.data.sources.ibkr import download_daily_bars
from tradebot.overnight import OvernightConfig, backtest, estimate, next_signal, summary

ET = ZoneInfo("America/New_York")


def _synthetic(seed: int = 8, n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0.001, 0.01, n))
    open_ = np.r_[100, close[:-1]] * (1 + rng.normal(0.001, 0.004, n))
    return pd.DataFrame({"open": open_, "close": close}, index=pd.bdate_range("2020-01-01", periods=n))


# ---- ported from the original selftest --------------------------------------------------


def test_estimate_is_gaussian_mle_with_denominator_n():
    a = np.array([0.001, 0.002, -0.001, 0.004, 0.002])
    e = estimate(a, a, OvernightConfig(window=5, cost_bps=0))
    assert e["sigma_daily"] ** 2 == pytest.approx(np.mean((a - a.mean()) ** 2))


def test_no_entry_when_mean_is_negative_or_variance_is_zero():
    c = OvernightConfig(window=5, cost_bps=0)
    a = np.array([0.001, 0.002, -0.001, 0.004, 0.002])
    assert estimate(-abs(a), a, c)["weight"] == 0
    assert estimate(np.ones(5), np.ones(5), c)["weight"] == 0


def test_costs_can_remove_all_edge():
    d = _synthetic()
    assert (backtest(d, OvernightConfig(window=5, cost_bps=100)).weight == 0).all()
    a = np.array([0.001, 0.002, -0.001, 0.004, 0.002])
    assert estimate(a, a, OvernightConfig(window=5, cost_bps=10_000))["weight"] == 0


def test_weights_never_use_future_data():
    c = OvernightConfig(window=5, cost_bps=0)
    d = _synthetic()
    changed = d.copy()
    changed.iloc[50:, :] *= 1.2
    b, b2 = backtest(d, c), backtest(changed, c)
    pd.testing.assert_series_equal(b.weight.loc[: d.index[50]], b2.weight.loc[: d.index[50]])


def test_weights_bounded_and_pnl_is_weight_times_overnight_return():
    b = backtest(_synthetic(), OvernightConfig(window=5, cost_bps=0))
    assert b.weight.between(0, 1).all()
    np.testing.assert_allclose(b.strategy_return, b.weight * b.overnight_return)


# ---- golden values computed by the ORIGINAL ibkr_overnight.py before it was archived ----


def test_matches_original_implementation_golden_values():
    d = _synthetic(seed=8, n=200)
    c = OvernightConfig(window=20, cost_bps=2)
    b = backtest(d, c)
    s = summary(b, 10_000)
    assert (b.index[0].date().isoformat(), b.index[-1].date().isoformat(), len(b)) == (
        "2020-01-31",
        "2020-10-06",
        178,
    )
    assert b.weight.sum() == pytest.approx(120.84089244804721, rel=1e-12)
    assert s["traded_sessions"] == 136
    assert s["strategy_return"]["ending_equity"] == pytest.approx(10982.421971746235, rel=1e-12)
    assert s["overnight_net"]["ending_equity"] == pytest.approx(11324.908480387432, rel=1e-12)
    assert s["buy_hold"]["ending_equity"] == pytest.approx(12342.114459750226, rel=1e-12)
    assert s["strategy_return"]["max_drawdown"] == pytest.approx(-0.0167770756182839, rel=1e-12)
    sig = next_signal(d, c)
    assert sig["mu"] == pytest.approx(0.001645122238, rel=1e-9)
    assert sig["sigma_overnight"] == pytest.approx(0.003724394841, rel=1e-9)
    assert sig["sigma_daily"] == pytest.approx(0.008026480836, rel=1e-9)
    assert (sig["weight"], sig["action"], sig["transmit"]) == (1.0, "PLAN_BUY_CLOSE", False)
    assert sig["history_through"] == "2020-10-06"


# ---- validation ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        {"window": 2},
        {"cost_bps": -1},
        {"fraction": 0},
        {"cap": 1.5},
        {"z": -1},
        {"cost_bps": float("nan")},
    ],
)
def test_config_rejects_invalid_values(bad):
    with pytest.raises(ValueError):
        OvernightConfig(**bad)


def test_bars_must_be_unique_ascending_positive_and_finite():
    d = _synthetic(n=10)
    with pytest.raises(ValueError, match="unique"):
        overnight.validate_bars(pd.concat([d, d.iloc[:1]]))
    with pytest.raises(ValueError, match="ascending"):
        overnight.validate_bars(d.iloc[::-1])
    bad = d.copy()
    bad.iloc[3, 0] = -1.0
    with pytest.raises(ValueError, match="positive"):
        overnight.validate_bars(bad)
    bad.iloc[3, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        overnight.validate_bars(bad)


def test_backtest_needs_history_and_a_positive_start():
    with pytest.raises(ValueError, match="Insufficient"):
        backtest(_synthetic(n=7), OvernightConfig(window=5))  # needs window + 3 = 8 bars
    with pytest.raises(ValueError, match="Initial equity"):
        backtest(_synthetic(), OvernightConfig(window=5), initial=0)


def test_frame_to_bars_normalises_engine_frames():
    ts = pd.to_datetime(["2026-01-02 00:00", "2026-01-05 00:00", "2026-01-06 00:00"]).tz_localize(
        "America/New_York"
    )
    frame = pd.DataFrame({"ts": ts, "open": [1.0, 2, 3], "high": 9, "low": 0.5, "close": [1.5, 2.5, 3.5]})
    bars = overnight.frame_to_bars(frame)
    assert list(bars.columns) == ["open", "close"]
    assert bars.index.tz is None and bars.index[0] == pd.Timestamp("2026-01-02")


# ---- order plan: never transmittable ------------------------------------------------------


def test_order_plan_is_moc_entry_and_opg_exit_and_untransmittable():
    entry, exit_order = overnight.order_plan("SPY", 10, "DU123")
    assert (entry.order_type, entry.tif, entry.qty) == ("MOC", "DAY", 10.0)
    assert (exit_order.order_type, exit_order.tif, exit_order.qty) == ("MKT", "OPG", -10.0)
    assert not entry.transmit and not exit_order.transmit
    assert entry.account == exit_order.account == "DU123"
    for order in (entry, exit_order):
        with pytest.raises(ValueError, match="plan-only"):
            to_ib_order(order)


@pytest.mark.parametrize("qty", [0, -1, 1.5, True, None])
def test_order_plan_requires_a_positive_integer_quantity(qty):
    with pytest.raises(ValueError):
        overnight.order_plan("SPY", qty, "DU123")


def test_order_plan_requires_an_explicit_account():
    with pytest.raises(ValueError):
        overnight.order_plan("SPY", 5, "")


def test_placing_a_plan_places_nothing_at_all():
    """A plan-only order anywhere in the batch must abort the whole batch before sending."""
    sent: list[object] = []

    class StubIB:
        def placeOrder(self, contract, order):
            sent.append(order)

        def sleep(self, _):
            pass

    broker = IBKRBroker()
    broker._ib = StubIB()
    entry, _ = overnight.order_plan("SPY", 3, "DU123")
    with pytest.raises(ValueError, match="plan-only"):
        broker.place([Order("TLT", 5.0), entry])
    assert sent == []


# ---- translation of real order types ------------------------------------------------------


def test_to_ib_order_supports_market_moc_and_limit():
    m = to_ib_order(Order("SPY", 5.0))
    assert (m.action, m.totalQuantity, m.orderType, m.tif) == ("BUY", 5.0, "MKT", "DAY")
    moc = to_ib_order(Order("SPY", -2.0, "MOC", account="DU1", ref="x"))
    assert (moc.action, moc.orderType, moc.account, moc.orderRef) == ("SELL", "MOC", "DU1", "x")
    lmt = to_ib_order(Order("SPY", 1.0, "LMT", limit_price=101.5))
    assert (lmt.orderType, lmt.lmtPrice) == ("LMT", 101.5)
    opg = to_ib_order(Order("SPY", -1.0, "MKT", tif="OPG"))
    assert (opg.orderType, opg.tif) == ("MKT", "OPG")


@pytest.mark.parametrize(
    "order",
    [
        Order("SPY", 1.0, "LMT"),  # limit price missing
        Order("SPY", 1.0, "LMT", limit_price=-1.0),
        Order("SPY", 1.0, "STP"),  # unsupported type must not silently become a market order
        Order("SPY", 0.0),
        Order("SPY", float("nan")),
    ],
)
def test_to_ib_order_rejects_impossible_orders(order):
    with pytest.raises(ValueError):
        to_ib_order(order)


# ---- IBKR download ------------------------------------------------------------------------


class _DownloadIB:
    def __init__(self, bars):
        self.bars, self.kwargs = bars, None

    def reqHistoricalData(self, contract, **kwargs):
        self.kwargs = {"symbol": contract.symbol, **kwargs}
        return self.bars


def test_download_ends_at_midnight_utc_and_returns_open_close():
    bars = [
        SimpleNamespace(date=date(2026, 9, 16), open=1.0, close=1.5),
        SimpleNamespace(date=date(2026, 9, 17), open=2.0, close=2.5),
    ]
    ib = _DownloadIB(bars)
    frame = download_daily_bars(ib, "SPY", "2 Y", now=datetime(2026, 9, 18, 21, 30, tzinfo=UTC))
    assert ib.kwargs["endDateTime"] == "20260918-00:00:00"
    assert (ib.kwargs["whatToShow"], ib.kwargs["useRTH"], ib.kwargs["durationStr"]) == ("TRADES", True, "2 Y")
    assert list(frame.columns) == ["date", "open", "close"]
    assert frame.date.tolist() == ["2026-09-16", "2026-09-17"]


def test_download_with_no_bars_is_an_error_not_an_empty_frame():
    with pytest.raises(RuntimeError, match="No historical bars"):
        download_daily_bars(_DownloadIB([]), "SPY")


# ---- spread screen ------------------------------------------------------------------------


def _screen_inputs(candidate_spread_bps: float, seed: int = 3):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2021-01-01", periods=120).strftime("%Y-%m-%d")
    spy = rng.normal(0.0005, 0.004, 120)
    rows = []
    for symbol, beta in [("SPY", 1.0), ("CAND", 1.3)]:
        ret = beta * spy + rng.normal(0, 0.0008, 120)
        rows += [{"date": d, "symbol": symbol, "return": v} for d, v in zip(days, ret, strict=True)]
    quotes = []
    for d in days[:80]:
        for slot in range(3):
            for symbol, bps in [("SPY", 1.0), ("CAND", candidate_spread_bps)]:
                mid = 100.0
                half = mid * bps / 10_000 / 2
                quotes.append({"date": d, "slot": slot, "symbol": symbol, "bid": mid - half, "ask": mid + half})
    return pd.DataFrame(rows), pd.DataFrame(quotes)


def test_screen_qualifies_a_cheaper_high_beta_candidate_only():
    cheap = overnight.screen_frames(*_screen_inputs(0.5))[0]
    assert cheap["symbol"] == "CAND" and cheap["qualifies"]
    assert cheap["raw_saving_bps"] == pytest.approx(0.5, abs=1e-6)
    dear = overnight.screen_frames(*_screen_inputs(2.0))[0]
    assert not dear["qualifies"]  # costs MORE than SPY: the strict cheaper-spread rule fails


def test_screen_rejects_crossed_quotes_duplicates_and_missing_spy():
    r, q = _screen_inputs(0.5)
    crossed = q.copy()
    crossed.loc[0, "bid"] = crossed.loc[0, "ask"] + 1
    with pytest.raises(ValueError, match="crossed"):
        overnight.screen_frames(r, crossed)
    with pytest.raises(ValueError, match="Duplicate"):
        overnight.screen_frames(r, pd.concat([q, q.iloc[:1]]))
    with pytest.raises(ValueError, match="SPY"):
        overnight.screen_frames(r[r.symbol != "SPY"], q)


# ---- intraday history download -------------------------------------------------------------


class _PagingIB:
    """Serves 'months' of fake 5-minute bars, newest first, like IBKR's 1 M requests."""

    def __init__(self, months: int) -> None:
        self.calls: list[str] = []
        self.months = months

    def reqHistoricalData(self, contract, **kw):
        from types import SimpleNamespace

        self.calls.append(kw["endDateTime"])
        if len(self.calls) > self.months:
            return []
        end = (
            pd.Timestamp("2026-09-18 20:00", tz="UTC")
            if kw["endDateTime"] == ""
            else pd.Timestamp(kw["endDateTime"].replace("-", " "), tz="UTC")
        )
        stamps = pd.date_range(end=end - pd.Timedelta(minutes=5), periods=6, freq="5min", tz="UTC")
        return [SimpleNamespace(date=t.to_pydatetime(), open=1.0, high=1.0, low=1.0, close=1.0, volume=1) for t in stamps]


def test_intraday_history_pages_backwards_and_dedupes():
    from tradebot.data.sources.ibkr import download_intraday_history

    ib = _PagingIB(months=3)
    frame = download_intraday_history(ib, "SPY", months=5)
    assert ib.calls[0] == "" and all(c.endswith(":00") or c == "" for c in ib.calls)
    assert len(ib.calls) == 4  # three chunks, then an empty answer stops the paging
    assert frame.ts.is_monotonic_increasing and not frame.ts.duplicated().any()
    assert str(frame.ts.dt.tz) == "UTC"


def test_intraday_history_with_no_data_is_an_error():
    from tradebot.data.sources.ibkr import download_intraday_history

    with pytest.raises(RuntimeError, match="No intraday bars"):
        download_intraday_history(_PagingIB(months=0), "SPY", months=2)


# ---- intraday volatility and the volatility-aware binary rule ------------------------------


def _session_bars(day: str, sigma: float, seed: int = 1, skip: int = 0) -> pd.DataFrame:
    """A full 09:30-16:00 ET day of 5-minute bars with i.i.d. returns of std `sigma`."""
    start = pd.Timestamp(f"{day} 09:30", tz="America/New_York").tz_convert("UTC")
    stamps = pd.date_range(start, periods=78, freq="5min")
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, sigma, 78)))
    open_ = np.r_[100.0, close[:-1]]
    frame = pd.DataFrame({"ts": stamps, "open": open_, "close": close})
    return frame.iloc[skip:].reset_index(drop=True) if skip else frame


def test_intraday_variance_matches_the_definition_and_scales_to_a_full_session():
    bars = _session_bars("2026-09-16", sigma=0.001)
    open_, close = bars.ts.iloc[0], bars.ts.iloc[-1] + pd.Timedelta(minutes=5)
    decision = overnight.decision_time(close.to_pydatetime())
    assert decision.astimezone(ET).strftime("%H:%M") == "15:00"
    got = overnight.intraday_variance(bars, open_.to_pydatetime(), close.to_pydatetime(), decision)
    used = bars[bars.ts + pd.Timedelta(minutes=5) <= decision]
    rets = np.log(used.close.to_numpy() / np.r_[used.open.iloc[0], used.close.to_numpy()[:-1]])
    assert len(used) == 66  # 09:30 .. 14:55 starts
    assert got == pytest.approx((rets**2).sum() * 390 / 330)
    assert got == pytest.approx(0.001**2 * 78, rel=0.35)  # ~ a full-day variance


def test_intraday_variance_needs_coverage_and_ignores_bars_after_the_decision():
    bars = _session_bars("2026-09-16", 0.001)
    open_, close = bars.ts.iloc[0], bars.ts.iloc[-1] + pd.Timedelta(minutes=5)
    decision = overnight.decision_time(close.to_pydatetime())
    gappy = bars.drop(bars.index[10:30])  # 20 of 66 bars missing -> coverage < 90%
    assert overnight.intraday_variance(gappy, open_.to_pydatetime(), close.to_pydatetime(), decision) is None
    # bars after 15:00 must never leak into the number
    tampered = bars.copy()
    tampered.loc[tampered.ts >= decision, ["open", "close"]] = 1e6
    a = overnight.intraday_variance(bars, open_.to_pydatetime(), close.to_pydatetime(), decision)
    b = overnight.intraday_variance(tampered, open_.to_pydatetime(), close.to_pydatetime(), decision)
    assert a == b


def test_by_day_uses_each_days_own_close_so_early_closes_decide_at_noon():
    normal = _session_bars("2026-11-25", 0.001)
    early = _session_bars("2026-11-27", 0.001).iloc[:42]  # closes 13:00 ET
    table = overnight.intraday_variance_by_day(pd.concat([normal, early]))
    hours = {d.strftime("%Y-%m-%d"): t.astimezone(ET).strftime("%H:%M") for d, t in table.decision_at_utc.items()}
    assert hours == {"2026-11-25": "15:00", "2026-11-27": "12:00"}
    partial_day = _session_bars("2026-11-24", 0.001, skip=5)  # data starts mid-morning
    assert "2026-11-24" not in [d.strftime("%Y-%m-%d") for d in
                                overnight.intraday_variance_by_day(partial_day).index]


def test_a_stormy_day_lowers_the_sized_weight_and_flips_the_binary_decision():
    calm = np.full(60, 0.0006) + np.tile([0.0002, -0.0002], 30)  # steady small overnight edge
    daily = np.tile([0.004, -0.004], 30)
    c = OvernightConfig(window=60, cost_bps=2, binary=True, min_weight=0.5)
    calm_day = estimate(calm, daily, c, intraday_var=0.004**2)
    stormy = estimate(calm, daily, c, intraday_var=0.03**2)
    assert calm_day["weight"] == 1.0 and calm_day["raw_weight"] >= 0.5
    assert stormy["weight"] == 0.0 and 0 < stormy["raw_weight"] < 0.5
    assert stormy["sigma_intraday"] == pytest.approx(0.03)
    # with no threshold the storm no longer changes the decision (the earlier binary rule)
    assert estimate(calm, daily, OvernightConfig(window=60, cost_bps=2, binary=True), 0.03**2)["weight"] == 1.0


def test_min_weight_must_lie_within_the_cap():
    with pytest.raises(ValueError):
        OvernightConfig(min_weight=1.5)
    with pytest.raises(ValueError):
        OvernightConfig(min_weight=-0.1)


def test_backtest_skips_days_without_intraday_data_instead_of_trading_blind():
    d = _synthetic(n=120)
    c = OvernightConfig(window=20, cost_bps=0, binary=True, min_weight=0.0)
    full = backtest(d, c)
    iv = pd.Series(1e-6, index=d.index)  # tiny variance everywhere...
    iv = iv.drop(d.index[60:80])  # ...but 20 decision days missing
    gated = backtest(d, c, intraday=iv)
    assert gated.intraday_missing.sum() == 20
    assert (gated.loc[gated.intraday_missing, "weight"] == 0).all()
    # a tiny intraday variance never exceeds the overnight/daily terms, so every day that HAS
    # data must decide exactly as it did without the intraday input
    have = ~gated.intraday_missing
    pd.testing.assert_series_equal(gated.loc[have, "weight"], full.loc[have, "weight"])
    assert list(gated.decision_date[:2]) == list(d.index[c.window + 1 : c.window + 3])
