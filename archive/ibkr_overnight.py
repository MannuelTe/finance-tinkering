#!/usr/bin/env python3
"""SPY overnight research + read-only IBKR integration. NO order submission.

Setup: pip install numpy pandas
For IBKR functions, install official Python TWS API from Interactive Brokers:
https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/
Enable socket API and Read-Only API in paper TWS (usual port 7497;
paper Gateway usually 4002). No credentials belong in this file.

Examples:
  python ibkr_overnight.py selftest
  python ibkr_overnight.py backtest SPY.csv --cost-bps 2
  python ibkr_overnight.py signal SPY.csv --cost-bps 2
  python ibkr_overnight.py download --symbol SPY --output SPY.csv
  python ibkr_overnight.py screen returns.csv quotes.csv

BAR CSV: date,open,close (one row EVERY trading session, ascending dates).
Use consistently split AND dividend adjusted open/close for total returns.
Never combine adjusted close with raw open. IBKR TRADES download is a
PRICE-RETURN dataset (splits adjusted, dividends not adjusted); it omits
dividend income. Obtain validated total-return OHLC separately for investment
results. Adjusted prices cannot be used to determine actual share quantities.

Model: local IID Gaussian MLE (denominator n), 60 observations by default.
Estimate expected overnight return from prior overnight returns. Estimate both
overnight and close-to-close daily volatility. Use the larger variance as a
conservative sizing denominator, NOT as a fitted overnight volatility estimate.
Entry requires mean - roundtrip cost > z * standard error of mean. Default z=0
is an EV filter, NOT evidence of statistical significance. Quarter-Kelly-style
sizing: clip(0.25 * net_mean / risk_variance, 0, 1). No borrowed cash.
Expected return determines exposure; exposure * realized return updates equity.
Realized returns enter subsequent rolling MLE windows, never their own signal.
No arbitrary EV*return adjustment is made to the volatility estimate.

Timing: row t represents sale at open t after buying close t-1. Its overnight
estimate uses data through open t-1; daily estimate uses closes through t-2,
available BEFORE submitting MOC on t-1. signal() assumes all supplied bars are
completed sessions and makes a conservative NEXT-session-close plan; it is
not an unattended scheduler or an intraday signal service.

Costs: --cost-bps is ALL-IN roundtrip cost per invested dollar, not per side.
Two half-spreads approximately equal one full spread for an ordinary roundtrip.
Auction fills need implementation shortfall, not a mechanically applied NBBO
spread. Costs exclude tax; no cash interest, dividend payment delay, fixed
commission minimums, volume impact, margin or borrow costs are simulated.
Backtest uses fractional theoretical exposure, not whole-share execution.

SCREEN CSVs:
 returns.csv: date,symbol,return -- aligned close->next-open simple returns,
 all symbols share the SAME cash-market session endpoints, including futures.
 quotes.csv: date,slot,symbol,bid,ask -- one synchronized valid NBBO per slot
 per symbol, slots sampled at a fixed cadence in chosen entry/exit windows.
 Use exchange timestamps; reject stale quotes upstream. No delayed quotes.
 At least 60 paired return observations and 30 paired quote days required.
 Per-day paired mean full spreads; moving-block bootstrap by days, 5-day blocks.
 Both raw and beta-normalized savings shown. Candidate must meet beta >=1.1,
 correlation >=0.8, and RAW saving lower CI >0.1 bps by default. This enforces
 the user's strict cheaper-spread condition; beta-normalized savings alone
 do not qualify. CI is exploratory, not multiple-testing corrected; beta
 uncertainty, depth, commissions and auction slippage need separate validation.
 Do not optimize the strategy using full-sample screening (selection leakage).

IBKR hooks: download uses official ibapi read-only historical data. order_plan
returns untransmitted MOC BUY / OPG MKT SELL objects for a supervising system.
It never calls placeOrder, even in paper. Submit exit ONLY for confirmed owned
filled shares before next session's opening cutoff, not alongside the entry.
Production integration still requires exchange calendar (early closes/holidays),
MOC cutoff checks, current-price sizing and cash reserve, account/position/order
reconciliation, persistent idempotency, fill handling, disconnect recovery,
corporate actions, alerts and emergency exit policy. A MOC price is unknown
when sizing, so a price buffer is required. Overnight gap losses remain possible.

Research checked 2026-09-18 (not measurements from an IBKR account):
SPY issuer 30-day median spread 0.00% rounded, as of Sep 17 (NOT zero cost):
https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy
SSO 0.01%=1 bp, UPRO 0.02%=2 bps as of Sep 17; daily targets 2x/3x,
not empirically estimated overnight betas:
https://www.proshares.com/our-etfs/leveraged-and-inverse/sso
https://www.proshares.com/our-etfs/leveraged-and-inverse/upro
VOO issuer page 0.004%=0.4 bp at retrieval; not a high-beta fund:
https://advisors.vanguard.com/investments/products/voo/vanguard-sp-500-etf
ES/MES warrant testing, not a claimed cheaper alternative; leverage on margin
is not beta per dollar of notional. Futures must be sampled at equity close/open,
not their own daily bars or settlement; handle roll, basis, multiplier and fees.
https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.contractSpecs.html
No authenticated broker session or real-data strategy backtest was run here.
"""
from __future__ import annotations
import argparse
import json
import math
import threading
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Config:
    window: int = 60
    cost_bps: float = 2.0
    fraction: float = 0.25
    cap: float = 1.0
    z: float = 0.0

    def __post_init__(self):
        if self.window < 3 or not all(math.isfinite(x) for x in
                (self.cost_bps, self.fraction, self.cap, self.z)):
            raise ValueError('Invalid configuration')
        if self.cost_bps < 0 or not 0 < self.fraction <= 1 or not 0 < self.cap <= 1 or self.z < 0:
            raise ValueError('Costs/z must be nonnegative; fraction/cap in (0,1]')


def load_bars(path):
    d = pd.read_csv(path, parse_dates=['date']).set_index('date')
    if d.index.has_duplicates or not d.index.is_monotonic_increasing or d.index.hasnans:
        raise ValueError('Dates must be unique, valid and ascending')
    p = d[['open', 'close']].astype(float)
    if not np.isfinite(p).all().all() or (p <= 0).any().any():
        raise ValueError('Prices must be finite and positive')
    return p


def estimate(overnight, daily, c):
    a, b = np.asarray(overnight)[-c.window:], np.asarray(daily)[-c.window:]
    if len(a) < c.window or len(b) < c.window or not np.isfinite(np.r_[a, b]).all():
        return dict(mu=np.nan, sigma_overnight=np.nan, sigma_daily=np.nan, weight=0.0)
    mu, so, sd = float(a.mean()), float(a.std(ddof=0)), float(b.std(ddof=0))
    net = mu - c.cost_bps / 10000
    v = max(so**2, sd**2)
    w = 0.0 if v < 1e-12 or net <= c.z * so / math.sqrt(c.window) else min(c.cap, c.fraction * net / v)
    return dict(mu=mu, sigma_overnight=so, sigma_daily=sd, weight=w)


def backtest(d, c, initial=10000):
    if initial <= 0 or not math.isfinite(initial):
        raise ValueError('Initial equity must be positive')
    if len(d) < c.window + 3:
        raise ValueError('Insufficient history after conservative signal lag')
    overnight = d.open / d.close.shift(1) - 1
    daily = d.close.pct_change(fill_method=None)
    rows = []
    for t in range(c.window + 2, len(d)):
        e = estimate(overnight.iloc[:t], daily.iloc[:t-1], c)
        r = float(overnight.iloc[t])
        rows.append(dict(date=d.index[t], **e, overnight_return=r,
                         strategy_return=e['weight'] * (r-c.cost_bps/10000),
                         overnight_net=r-c.cost_bps/10000,
                         buy_hold=float(daily.iloc[t])))
    out = pd.DataFrame(rows).set_index('date')
    for name in ['strategy_return', 'overnight_net', 'buy_hold']:
        if (out[name] <= -1).any():
            raise ValueError('Insolvent path; inspect data/costs')
        out[name + '_equity'] = initial * (1+out[name]).cumprod()
    return out


def summary(out, initial):
    result = {}
    for name in ['strategy_return', 'overnight_net', 'buy_hold']:
        r = out[name]
        eq = np.r_[initial, out[name+'_equity'].to_numpy()]
        result[name] = dict(ending_equity=float(eq[-1]),
            annualized_252=float((eq[-1]/initial)**(252/len(r))-1),
            annualized_vol=float(r.std(ddof=0)*np.sqrt(252)),
            max_drawdown=float((eq/np.maximum.accumulate(eq)-1).min()))
    result['sessions'] = len(out)
    result['traded_sessions'] = int((out.weight > 0).sum())
    result['note'] = 'Common evaluation dates; buy_hold excludes entry/exit costs. No tax/cash interest.'
    return result


def next_signal(d, c):
    # For next session close: all input sessions must already be completed.
    overnight = (d.open / d.close.shift(1)-1).dropna()
    daily = d.close.pct_change(fill_method=None).dropna()
    e = estimate(overnight, daily, c)
    if not math.isfinite(e['mu']):
        raise ValueError('Insufficient history')
    return dict(**e, history_through=str(d.index[-1].date()),
                action='PLAN_BUY_CLOSE' if e['weight'] > 0 else 'STAY_CASH',
                transmit=False, scope='Conservative next-session-close plan only')


def order_plan(quantity, account):
    """IBKR-native templates; caller must implement execution lifecycle."""
    from ibapi.order import Order
    from decimal import Decimal
    if not isinstance(quantity, int) or quantity <= 0 or not account:
        raise ValueError('Positive integer quantity and explicit account required')
    entry, exit_order = Order(), Order()
    for o in (entry, exit_order):
        o.account, o.totalQuantity, o.transmit = account, Decimal(quantity), False
        o.outsideRth, o.orderRef = False, 'overnight_mle_REQUIRES_SUPERVISOR'
    entry.action, entry.orderType, entry.tif = 'BUY', 'MOC', 'DAY'
    exit_order.action, exit_order.orderType, exit_order.tif = 'SELL', 'MKT', 'OPG'
    return entry, exit_order


def download(symbol, host, port, client_id, duration):
    """Read-only official TWS API, sequential single historical request."""
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract

    class Reader(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.ready, self.done = threading.Event(), threading.Event()
            self.rows, self.failure = [], None

        def nextValidId(self, orderId):
            self.ready.set()

        def historicalData(self, reqId, bar):
            self.rows.append(dict(date=bar.date, open=bar.open, close=bar.close))

        def historicalDataEnd(self, reqId, start, end):
            self.done.set()

        def error(self, reqId, *args):
            # Pre/post errorTime API signatures; accepts optional advanced JSON.
            offset = 1 if len(args) >= 3 and isinstance(args[1], int) else 0
            code = args[offset] if args else -1
            if code not in {2104, 2106, 2107, 2108, 2158}:
                self.failure = f'IBKR request {reqId}: {args}'
                self.done.set()

    app = Reader()
    worker = None
    try:
        app.connect(host, port, client_id)
        worker = threading.Thread(target=app.run, daemon=True)
        worker.start()
        if not app.ready.wait(15):
            raise RuntimeError(app.failure or 'TWS handshake timeout')
        contract = Contract()
        contract.symbol, contract.secType = symbol, 'STK'
        contract.exchange, contract.currency = 'SMART', 'USD'
        # End at today's midnight UTC, ensuring no partial current-session bar.
        end = pd.Timestamp.now(tz='UTC').strftime('%Y%m%d-00:00:00')
        app.reqHistoricalData(1, contract, end, duration, '1 day', 'TRADES', 1, 1, False, [])
        if not app.done.wait(45):
            app.cancelHistoricalData(1)
            raise TimeoutError('Historical data timeout')
        if app.failure:
            raise RuntimeError(app.failure)
        if not app.rows:
            raise RuntimeError('No historical bars returned')
        d = pd.DataFrame(app.rows)
        d['date'] = pd.to_datetime(d.date, format='%Y%m%d').dt.strftime('%Y-%m-%d')
        return d
    finally:
        app.disconnect()
        if worker:
            worker.join(timeout=2)


def screen(returns_path, quotes_path, min_beta=1.1, min_corr=0.8, min_saving=0.1):
    r = pd.read_csv(returns_path).pivot(index='date', columns='symbol', values='return').sort_index()
    q = pd.read_csv(quotes_path)
    if 'SPY' not in r or 'SPY' not in set(q.symbol):
        raise ValueError('SPY is required in both datasets')
    if q.duplicated(['date', 'slot', 'symbol']).any():
        raise ValueError('Duplicate quote slots')
    if not np.isfinite(q[['bid', 'ask']]).all().all() or (q.bid <= 0).any() or (q.ask <= q.bid).any():
        raise ValueError('Reject invalid, locked or crossed quotes')
    q['bps'] = 10000*(q.ask-q.bid)/((q.ask+q.bid)/2)
    p = q.pivot(index=['date', 'slot'], columns='symbol', values='bps').sort_index()
    results = []
    for symbol in sorted(set(r.columns) & set(p.columns) - {'SPY'}):
        rr = r[['SPY', symbol]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(rr) < 60 or rr.SPY.var(ddof=0) <= 0:
            continue
        beta = float(np.cov(rr[symbol], rr.SPY, ddof=0)[0, 1]/rr.SPY.var(ddof=0))
        corr = float(rr.corr().iloc[0, 1])
        pairs = p[['SPY', symbol]].dropna()
        daily = pairs.groupby(level='date').mean()
        if len(daily) < 30 or beta <= 0 or not math.isfinite(corr):
            continue
        delta = (daily.SPY-daily[symbol]).to_numpy()
        # Circular moving-block resampling preserves short-run serial dependence.
        rng = np.random.default_rng(42)
        n, block = len(delta), 5
        starts = rng.integers(0, n, size=(3000, math.ceil(n/block)))
        idx = ((starts[..., None]+np.arange(block)) % n).reshape(3000, -1)[:, :n]
        low, high = np.quantile(delta[idx].mean(axis=1), [0.025, 0.975])
        results.append(dict(symbol=symbol, overnight_beta=beta, correlation=corr,
            paired_return_days=len(rr), paired_quote_days=n,
            spy_mean_spread_bps=float(daily.SPY.mean()),
            candidate_mean_spread_bps=float(daily[symbol].mean()),
            raw_saving_bps=float(delta.mean()), ci95_low_bps=float(low), ci95_high_bps=float(high),
            beta_normalized_saving_bps=float((daily.SPY-daily[symbol]/beta).mean()),
            qualifies=bool(beta >= min_beta and corr >= min_corr and low > min_saving)))
    return results


def selftest():
    c = Config(window=5, cost_bps=0)
    a = np.array([.001, .002, -.001, .004, .002])
    e = estimate(a, a, c)
    assert np.isclose(e['sigma_daily']**2, np.mean((a-a.mean())**2))
    assert estimate(-abs(a), a, c)['weight'] == 0
    assert estimate(np.ones(5), np.ones(5), c)['weight'] == 0
    rng = np.random.default_rng(8)
    close = 100*np.cumprod(1+rng.normal(.001, .01, 100))
    op = np.r_[100, close[:-1]]*(1+rng.normal(.001, .004, 100))
    d = pd.DataFrame({'open': op, 'close': close}, index=pd.bdate_range('2020-01-01', periods=100))
    b = backtest(d, c)
    changed = d.copy()
    changed.iloc[50:, :] *= 1.2
    b2 = backtest(changed, c)
    pd.testing.assert_series_equal(b.weight.loc[:d.index[50]], b2.weight.loc[:d.index[50]])
    assert b.weight.between(0, 1).all()
    np.testing.assert_allclose(b.strategy_return, b.weight*b.overnight_return)
    cc = Config(window=5, cost_bps=10000)
    assert (backtest(d, Config(window=5, cost_bps=100)).weight == 0).all()
    assert estimate(a, a, cc)['weight'] == 0
    print('PASS: Gaussian MLE, no-future-data weights, costs, bounds, zero variance, P&L')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('selftest')
    for cmd in ['backtest', 'signal']:
        p = sub.add_parser(cmd)
        p.add_argument('csv')
        p.add_argument('--window', type=int, default=60)
        p.add_argument('--cost-bps', type=float, default=2)
        p.add_argument('--fraction', type=float, default=.25)
        p.add_argument('--cap', type=float, default=1)
        p.add_argument('--z', type=float, default=0)
        if cmd == 'backtest':
            p.add_argument('--initial', type=float, default=10000)
            p.add_argument('--output', default=None)
    p = sub.add_parser('download')
    p.add_argument('--symbol', default='SPY')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=7497)
    p.add_argument('--client-id', type=int, default=91)
    p.add_argument('--duration', default='2 Y')
    p.add_argument('--output', required=True)
    p = sub.add_parser('screen')
    p.add_argument('returns_csv')
    p.add_argument('quotes_csv')
    p.add_argument('--min-beta', type=float, default=1.1)
    p.add_argument('--min-corr', type=float, default=.8)
    p.add_argument('--min-saving-bps', type=float, default=.1)
    args = parser.parse_args()
    if args.command == 'selftest':
        selftest()
    elif args.command == 'download':
        d = download(args.symbol, args.host, args.port, args.client_id, args.duration)
        d.to_csv(args.output, index=False, mode='x')
        print('Saved PRICE-only bars; dividends excluded. No orders submitted.')
    elif args.command == 'screen':
        print(json.dumps(screen(args.returns_csv, args.quotes_csv, args.min_beta,
                                args.min_corr, args.min_saving_bps), indent=2, allow_nan=False))
    else:
        d = load_bars(args.csv)
        c = Config(args.window, args.cost_bps, args.fraction, args.cap, args.z)
        if args.command == 'signal':
            print(json.dumps(next_signal(d, c), indent=2, allow_nan=False))
        else:
            out = backtest(d, c, args.initial)
            if args.output:
                out.to_csv(args.output, mode='x')
            print(json.dumps(summary(out, args.initial), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
