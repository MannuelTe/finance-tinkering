"""Command line.

    uransig run [--refresh]      event study, symmetry test, variants, figure
    uransig speed                half-lives, equity vs physical vs spot lead-lag
    uransig backtest             walk-forward drift trade with costs
    uransig events               per-event window sums
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest as bt
from . import plots, speed, study
from .prices import MARKET, PHYSICAL, PROXIES, load_prices, load_spot, log_returns

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "data" / "events.csv"


def _data(refresh):
    ret = log_returns(load_prices(refresh))
    return ret, study.load_events(EVENTS)


def _paths(ret, ev, names=PROXIES, market=MARKET):
    return study.event_paths(ret, ev, list(names), list(market))


def _fmt(sym: study.Symmetry) -> pd.DataFrame:
    rows = []
    for k in sym.diff:
        lo, hi = sym.ci[k]
        rows.append({"metric": k, "bull": sym.bull[k], "bear (flipped)": sym.bear[k],
                     "bull - bear": sym.diff[k], "90% CI": f"[{lo:+.3f}, {hi:+.3f}]",
                     "p": sym.p[k]})
    return pd.DataFrame(rows).set_index("metric")


def _isolated(ev, index):
    """Signed events whose window holds no other signed event, so windows don't overlap."""
    e = ev[ev.direction != "none"].reset_index(drop=True)
    pos = study.align(e["date"], index, e["session"])
    keep = [all(not (-study.PRE <= q - p <= study.POST) for j, q in enumerate(pos) if j != i)
            for i, p in enumerate(pos)]
    return e[keep]


def run(args):
    ret, ev = _data(args.refresh)
    variants = {
        "all events, basket": (ev, PROXIES),
        "surprises only": (ev[ev.timing == "surprise"], PROXIES),
        "known release session": (ev[ev.session != "unknown"], PROXIES),
        "CCJ only": (ev, ("CCJ",)),
        "drop DeepSeek and COVID": (ev[~ev.date.dt.year.isin([2020]) &
                                       (ev.date != "2025-01-27")], PROXIES),
        "isolated events (no other event in -20..+60)": (_isolated(ev, ret.index), PROXIES),
    }
    pd.set_option("display.width", 120, "display.float_format", "{:+.3f}".format)
    for name, (e, names) in variants.items():
        bull, _ = _paths(ret, e[e.direction == "bull"], names)
        bear, _ = _paths(ret, e[e.direction == "bear"], names)
        sym = study.symmetry_test(bull, bear)
        print(f"\n== {name}: {len(bull)} bull, {len(bear)} bear")
        print(_fmt(sym).to_string())
        if name == "all events, basket":
            plots.signatures(bull, bear, ROOT / "figures" / "signatures.png",
                             "Uranium equities after bullish vs bearish news")
            mil, _ = _paths(ret, ev[ev.direction == "none"])

    print(f"\n== military / weapons events (unsigned, n={len(mil)})")
    print(study.window_sums(mil).mean().to_string())
    pos = study.align(ev["date"], ret.index, ev["session"])
    noise = study.placebo(ret, list(PROXIES), list(MARKET), exclude=pos)
    print(f"\n== placebo: {len(noise)} random days, std of each window for ONE event")
    print(noise.std().to_string())


def _split(ret, ev):
    bull, kb = _paths(ret, ev[ev.direction == "bull"])
    bear, kr = _paths(ret, ev[ev.direction == "bear"])
    return bull, kb, bear, kr


def speed_cmd(args):
    ret, ev = _data(args.refresh)
    bull, _, bear, _ = _split(ret, ev)
    fits = {"Bullish": speed.adjustment(bull), "Bearish (flipped)": speed.adjustment(bear)}
    print("== partial adjustment, days 0..20")
    for k, f in fits.items():
        lo, hi = f["hl_ci"]
        print(f"{k:18s} total {f['A']:+.3f}  kappa {f['kappa']:.3f}  "
              f"half-life {f['half_life']:.1f} days  90% CI [{lo:.1f}, {hi:.1f}]")
    diff = fits["Bearish (flipped)"]["hl_draws"] - fits["Bullish"]["hl_draws"]
    print(f"bear slower than bull in {np.nanmean(diff > 0):.0%} of bootstrap draws")
    paths = {"Bullish": bull.loc[:, 0:20].mean().cumsum().to_numpy(),
             "Bearish (flipped)": bear.loc[:, 0:20].mean().cumsum().to_numpy()}
    plots.adjustment(fits, paths, ROOT / "figures" / "half_life.png")

    px = load_prices()
    daily = pd.concat([ret[list(PROXIES)].mean(axis=1).rename("equity"),
                       ret[PHYSICAL].rename("physical")], axis=1).dropna()
    panels = [("Daily: uranium equities vs Sprott trust\n(2021+)",
               speed.cross_corr(daily["equity"], daily["physical"]), len(daily),
               "k: equities lead the trust by k days")]
    print(f"\n== daily equities vs physical trust, n={len(daily)}")
    for a, b, name in (("equity", "physical", "equities -> trust"),
                       ("physical", "equity", "trust -> equities")):
        r = speed.lead_lag(daily[a], daily[b])
        print(f"{name:18s} same-day {r['coef'][0]:+.3f}  lags 1-5 sum {r['lagged_sum']:+.3f} "
              f"(t {r['lagged_t']:+.1f})  share same-day {r['share_now']:.0%}")
    spot = load_spot(args.refresh)
    for avg, lab in ((False, "month-end"), (True, "month-average")):
        m = speed.monthly_pair(px["CCJ"], spot, average=avg)
        cc = speed.cross_corr(m["equity"], m["spot"], range(-3, 4))
        title = f"Monthly: Cameco ({lab}) vs spot\n(IMF monthly average, {m.index[0].year}+)"
        panels.append((title, cc, len(m), "k: Cameco leads spot by k months"))
        r = speed.lead_lag(m["equity"], m["spot"], 3)
        print(f"\n== Cameco {lab} vs spot, n={len(m)}")
        print("cross-corr " + "  ".join(f"{k:+d}:{v:+.2f}" for k, v in cc.items()))
        print(f"Cameco -> spot with spot's own lags: same-month {r['coef'][0]:+.3f}  "
              f"lags 1-3 sum {r['lagged_sum']:+.3f} (t {r['lagged_t']:+.1f})")
        ac = m["spot"].autocorr(1)
        print(f"spot autocorrelation at 1 month {ac:+.2f}, Cameco {m['equity'].autocorr(1):+.2f}")
    plots.lead_lag(panels, ROOT / "figures" / "lead_lag.png")


def backtest_cmd(args):
    ret, ev = _data(args.refresh)
    bull, kb, bear, kr = _split(ret, ev)
    ar = pd.concat([bull, bear], ignore_index=True)
    kept = pd.concat([kb, kr], ignore_index=True)
    t = bt.trades(ar, kept)
    pd.set_option("display.width", 160, "display.float_format", "{:+.3f}".format)
    print(t.to_string(index=False))
    s = bt.summary(t)
    print("\n== walk-forward summary")
    for k, v in s.items():
        print(f"{k:10s} {v:+.3f}" if isinstance(v, float) else f"{k:10s} {v}")
    for d in ("bull", "bear"):
        print(f"{d}: {bt.summary(t[t.direction == d])}")
    pos = study.align(ev["date"], ret.index, ev["session"])
    base = bt.random_baseline(ret, list(PROXIES), list(MARKET), s["trades"], exclude=pos)
    print(f"random books with the same {s['trades']} trades: mean {base.mean():+.3f}, "
          f"share beating the strategy {(base >= s['mean_net']).mean():.1%}")
    for cost in (0, 25, 50):
        c = bt.summary(bt.trades(ar, kept, cost_bp=cost))
        print(f"cost {cost:>2} bp/side: {c['trades']} trades, mean {c['mean_net']:+.3f}, "
              f"t {c['t_stat']:+.2f}")
    plots.backtest(t, base, ROOT / "figures" / "backtest.png")


def events(args):
    ret, ev = _data(args.refresh)
    ar, kept = _paths(ret, ev)
    out = pd.concat([kept[["day0", "session", "label", "direction", "timing"]],
                     study.window_sums(ar)], axis=1)
    pd.set_option("display.width", 160, "display.float_format", "{:+.3f}".format)
    print(out.to_string(index=False))


def main(argv=None):
    p = argparse.ArgumentParser(prog="uransig")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("run", run), ("speed", speed_cmd), ("backtest", backtest_cmd),
                     ("events", events)):
        s = sub.add_parser(name)
        s.add_argument("--refresh", action="store_true", help="re-download prices")
        s.set_defaults(fn=fn)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
