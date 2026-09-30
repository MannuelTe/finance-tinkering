"""Command line: run the examples, a CSV portfolio, or type one in interactively.

    taxharvest examples [--only us_core] [--quick]
    taxharvest run book.csv --jurisdiction CA --realized-gains 20000 \
        --tax-savings-goal 1500 --confidence 0.9 --horizon-days 40
    taxharvest interactive
    taxharvest daily book.csv --realized-gains 18000 --harvested-loss 0 \
        --tax-savings-goal 1200 --confidence 0.95 --every 5
    taxharvest backtest book.csv --realized-gains 18000 --tax-savings-goal 1200 \
        --confidences 0.9 0.95 --every 1 5
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import report
from .engine import METHODS, HarvestProblem
from .model import FACTORS, SECTOR_VOL, Universe, fit_regime_model, prices_to_log_returns
from .portfolio import Portfolio
from .washsale import JURISDICTIONS

ASSET_COLS = ("factor", "beta", "idio_vol", "wash_group", "sector", "sector_beta", "listing")


def _ensure_known(portfolio: Portfolio, universe: Universe, extra: pd.DataFrame | None, ask):
    """Every ticker needs a wash-sale group and factor exposure; take them from the CSV,
    ask for them, or fall back to a generic single stock."""
    for t in portfolio.tickers + [b.ticker for b in portfolio.planned_buys]:
        if t in universe:
            continue
        kw = {}
        if extra is not None and t in extra.index:
            kw = {c: extra.at[t, c] for c in ASSET_COLS if c in extra and pd.notna(extra.at[t, c])}
        elif ask:
            print(f"\n{t} is not in the asset library.")
            kw["factor"] = _ask(f"  factor {FACTORS}", "US_EQ", str.upper)
            kw["beta"] = _ask("  beta to that factor", 1.0, float)
            kw["idio_vol"] = _ask("  idiosyncratic annual vol (0.25 = 25%)", 0.25, float)
            kw["wash_group"] = _ask(
                "  wash-sale group (same value = substantially identical; e.g. SP500)", t,
                str.upper)
            kw["sector"] = _ask(f"  sector {list(SECTOR_VOL)} or blank", "", str.upper)
            kw["sector_beta"] = 1.0 if kw["sector"] else 0.0
        else:
            print(f"warning: {t} unknown; treating it as a US stock, beta 1, 25% idio vol, "
                  f"its own wash-sale group", file=sys.stderr)
        universe.add(t, **kw)


def _ask(prompt, default, cast=str):
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        print("  could not parse; using default")
        return default


def _model(portfolio, universe, history_path):
    if not history_path:
        return universe.factor_model(portfolio.tickers)
    prices = pd.read_csv(history_path, index_col=0, parse_dates=True)
    missing = set(portfolio.tickers) - set(prices.columns)
    if missing:
        raise SystemExit(f"history is missing tickers: {sorted(missing)}")
    rets = prices_to_log_returns(prices[portfolio.tickers])
    print(f"fitting regime model to {len(rets)} days of history")
    model, _ = fit_regime_model(rets, verbose=True)
    return model


def _build(args, portfolio, universe, extra=None, ask=False) -> HarvestProblem:
    _ensure_known(portfolio, universe, extra, ask)
    rules = JURISDICTIONS[args.jurisdiction.upper()]
    return HarvestProblem(
        portfolio, universe, _model(portfolio, universe, args.history), rules,
        tax_rate=args.tax_rate if args.tax_rate is not None else rules.default_tax_rate,
        confidence=args.confidence, horizon_days=args.horizon_days,
        realized_gains=args.realized_gains, tax_savings_goal=args.tax_savings_goal,
        n_scenarios=args.scenarios,
    )


def cmd_examples(args):
    from . import plots
    from .scenarios import EXAMPLES

    names = [args.only] if args.only else list(EXAMPLES)
    for name in names:
        ex = EXAMPLES[name]()
        print(f"\n=== {name}: {ex.title}\n{ex.blurb}")
        out = Path(args.out) / name
        extra = None
        if ex.true_model is not None:  # learned example: also test under the data-generating F
            extra = {"true data-generating F": ex.true_model}
            p = ex.problem.portfolio
            w = np.zeros(len(p.tickers))
            for lot in p.lots:
                w[p.tickers.index(lot.ticker)] += lot.value
            out.mkdir(parents=True, exist_ok=True)
            gauss = ex.problem.universe.factor_model(p.tickers)
            plots.learned_fit(ex.history, ex.fits, ex.problem.model, gauss,
                              out / "learned_fit.png", w / w.sum())
        report.run(ex.problem, out, ex.title, method=args.method, robust=not args.no_robust,
                   quick=args.quick, animate=not args.no_anim, extra_models=extra)
        print(f"-> {out}")


def _load(args) -> HarvestProblem:
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()  # noqa: DTZ011
    df = pd.read_csv(args.portfolio)
    df.columns = [c.lower() for c in df.columns]
    df["ticker"] = df["ticker"].str.upper()
    extra = df.drop_duplicates("ticker").set_index("ticker")
    planned = pd.read_csv(args.planned) if args.planned else None
    portfolio = Portfolio.from_frame(df, as_of, planned)
    return _build(args, portfolio, Universe.default(), extra)


def cmd_run(args):
    problem = _load(args)
    report.run(problem, Path(args.out), f"{Path(args.portfolio).stem}", method=args.method,
               robust=not args.no_robust, quick=args.quick, animate=not args.no_anim)
    print(f"-> {args.out}")


def cmd_daily(args):
    from . import daily

    problem = _load(args)
    deadline = date.fromisoformat(args.deadline) if args.deadline else None
    rev = daily.review(
        problem.portfolio, problem.universe, problem.model, problem.rules,
        realized_gains=args.realized_gains, harvested_loss=args.harvested_loss,
        tax_savings_goal=args.tax_savings_goal, tax_rate=problem.tax_rate, deadline=deadline,
        confidence=args.confidence, every=args.every, n_scenarios=args.scenarios,
        size_pool=not args.no_pool)
    print(daily.describe(rev, problem.rules.symbol))
    out = Path(args.out)
    daily.append_log(out / "review_log.csv", rev)
    if len(rev.orders):
        path = out / f"orders_{rev.as_of}.csv"
        rev.orders.to_csv(path, index=False)
        print(f"  orders -> {path}\n  after selling: update the portfolio CSV, add the loss to "
              f"--harvested-loss, and add the replacement lots")
    print(f"  log -> {out / 'review_log.csv'}")


def cmd_backtest(args):
    from . import daily, plots
    from .engine import optimise

    problem = _load(args)
    rules, pools = {"sell now": 1.01}, {}
    for c in args.confidences:
        for every in args.every:
            name = {1: "daily", 5: "weekly"}.get(every, f"every {every}d")
            rules[f"{name} {c:.0%}"] = (c, every)
        print(f"one-shot plan at {c:.0%}")
        pools[f"one-shot {c:.0%}"] = optimise(dataclasses.replace(problem, confidence=c)).x
    print(f"simulating {args.paths:,} price paths over {problem.horizon_days} trading days")
    bt = daily.backtest(problem, rules, n_paths=args.paths, n_inner=args.inner)
    for name, x in pools.items():
        one = daily.backtest(problem, {name: -1}, n_paths=args.paths, n_inner=args.inner, pool=x)
        bt[name] = one[name]
    meta = bt.pop("_meta")
    cols = ["P(goal met)", "E[tax saved]", "E[market value sold]", "E[sale days]",
            "P(sold before deadline)"]
    table = pd.DataFrame({k: {c: v[c] for c in cols} for k, v in bt.items()}).T
    table.insert(0, "reviews", [1 if not isinstance(rules.get(k), tuple) else
                                len(range(0, meta["days"], rules[k][1])) + 1 for k in table.index])
    print(f"\nloss needed {problem.rules.symbol}{meta['loss_goal']:,.0f}\n"
          + table.to_string(float_format=lambda v: f"{v:,.3f}" if v < 2 else f"{v:,.0f}"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "backtest.csv")
    plots.backtest({**bt, "_meta": meta}, out / "backtest.png", problem.rules.symbol, args.title)
    if args.animate:
        c = args.confidences[-1]
        print("recording paths for the review animations")
        rec = daily.backtest(problem, {"weekly": (c, 5)}, n_paths=400, n_inner=args.inner,
                             record=True)["weekly"]
        base = min(args.confidences)
        shot = daily.backtest(problem, {"one-shot": -1}, n_paths=400, n_inner=args.inner,
                              pool=pools[f"one-shot {base:.0%}"], record=True)["one-shot"]
        cur = problem.rules.symbol
        plots.animate_review_story(rec, shot, meta["loss_goal"], meta["days"],
                                   out / "review_story.gif", cur, trigger=c)
        plots.animate_review_paths(rec, shot, meta["loss_goal"], meta["days"],
                                   out / "review_paths.gif", cur, trigger=c)
    print(f"-> {out / 'backtest.png'}")


def cmd_interactive(args):
    print("Tax-saving planner. Wash-sale (US) / superficial-loss (CA) aware.\n")
    args.jurisdiction = _ask("Jurisdiction US, CA or CH", "US", str.upper)
    rules = JURISDICTIONS[args.jurisdiction]
    print(f"  {rules.note}")
    args.tax_rate = _ask("Effective tax rate on capital gains", round(rules.default_tax_rate, 4),
                         float)
    args.realized_gains = _ask("Gains already realised this tax year", 0.0, float)
    args.confidence = _ask("Required confidence P(tax saved >= goal)", 0.9, float)
    args.horizon_days = _ask("Trading days until you harvest", 40, int)
    default_goal = max(args.realized_gains, 0.0) * args.tax_rate
    args.tax_savings_goal = _ask("Tax saving wanted in dollars", round(default_goal, 2), float)
    today = date.today().isoformat()  # noqa: DTZ011 - local calendar date is intended
    as_of = date.fromisoformat(_ask("Today's date", today))
    print("\nType one lot per line:  TICKER SHARES COST_BASIS ACQUIRED PRICE [ACCOUNT] [drip]")
    print("  e.g.  VOO 40 610.5 2026-02-03 548.2 taxable")
    print("        IVV 10 500 2024-06-01 575 ira")
    print("  planned purchases:  buy TICKER DATE [ACCOUNT]    (blank line to finish)")
    lines = []
    while True:
        line = input("> ").strip()
        if not line:
            break
        try:
            Portfolio.from_text(line, as_of)
            lines.append(line)
        except ValueError as e:
            print(f"  {e}")
    if not lines:
        print("nothing entered")
        return
    portfolio = Portfolio.from_text("\n".join(lines), as_of)
    problem = _build(args, portfolio, Universe.default(), ask=True)
    out = Path(args.out)
    Path(out).mkdir(parents=True, exist_ok=True)
    (out / "portfolio.csv").write_text(portfolio.to_csv())
    report.run(problem, out, "Your portfolio", method=args.method, robust=not args.no_robust,
               quick=args.quick, animate=not args.no_anim)
    print(f"\nFigures, trades.csv and summary.json in {out}/")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="taxharvest", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, out):
        p.add_argument("--method", choices=METHODS, default="calibrated")
        p.add_argument("--out", default=out)
        p.add_argument("--quick", action="store_true", help="fewer Monte Carlo repetitions")
        p.add_argument("--no-robust", action="store_true", help="skip robustness tests")
        p.add_argument("--no-anim", action="store_true", help="skip GIF animations")
        p.add_argument("--history", help="CSV of daily prices (date index, ticker columns) "
                                         "to learn F_P from instead of the factor model")
        p.add_argument("--scenarios", type=int, default=10_000)

    e = sub.add_parser("examples", help="run the worked examples")
    e.add_argument("--only")
    common(e, "figures")
    e.set_defaults(fn=cmd_examples)

    def book(p, confidence=0.9):
        p.add_argument("portfolio", help="CSV: account,ticker,shares,cost_basis,acquired,price"
                                         "[,drip] (+ optional factor,beta,idio_vol,wash_group,"
                                         "sector)")
        p.add_argument("--planned", help="CSV of planned buys: ticker,on,account")
        p.add_argument("--as-of")
        p.add_argument("--jurisdiction", default="US",
                       choices=["US", "CA", "CH", "us", "ca", "ch"])
        p.add_argument("--tax-rate", type=float)
        p.add_argument("--confidence", type=float, default=confidence)
        p.add_argument("--horizon-days", type=int, default=40)
        p.add_argument("--realized-gains", type=float, default=0.0,
                       help="taxable gains actually realized or explicitly planned this year")
        p.add_argument("--tax-savings-goal", type=float,
                       help="dollars of tax to save; defaults to the full modeled tax bill")

    r = sub.add_parser("run", help="optimise a portfolio CSV")
    book(r)
    common(r, "out")
    r.set_defaults(fn=cmd_run)

    d = sub.add_parser("daily", help="today's review: hold, or sell to lock losses in")
    book(d, confidence=0.95)
    d.add_argument("--harvested-loss", type=float, default=0.0,
                   help="losses already realized this year")
    d.add_argument("--deadline", help="last sale date (default: last weekday of the year)")
    d.add_argument("--every", type=int, default=5,
                   help="trading days between reviews (5 = weekly)")
    d.add_argument("--no-pool", action="store_true", help="skip sizing the lots to keep free")
    common(d, "out")
    d.set_defaults(fn=cmd_daily)

    b = sub.add_parser("backtest", help="compare review rules on simulated price paths")
    book(b)
    b.add_argument("--confidences", type=float, nargs="+", default=[0.9, 0.95])
    b.add_argument("--every", type=int, nargs="+", default=[1, 5],
                   help="review intervals in trading days")
    b.add_argument("--paths", type=int, default=2000)
    b.add_argument("--inner", type=int, default=1000,
                   help="scenarios per review for the wait confidence")
    b.add_argument("--title", default="")
    b.add_argument("--animate", action="store_true",
                   help="also write review_story.gif and review_paths.gif")
    common(b, "out")
    b.set_defaults(fn=cmd_backtest)

    i = sub.add_parser("interactive", help="type your portfolio in")
    common(i, "out")
    i.set_defaults(fn=cmd_interactive)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
