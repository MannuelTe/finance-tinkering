"""Command line: run the examples, a CSV portfolio, or type one in interactively.

    taxharvest examples [--only us_core] [--quick]
    taxharvest run book.csv --jurisdiction CA --confidence 0.9 --horizon-days 40
    taxharvest interactive
"""

from __future__ import annotations

import argparse
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
    target_mode, override = args.target, None
    try:
        override, target_mode = float(args.target), "fixed"
    except ValueError:
        pass
    return HarvestProblem(
        portfolio, universe, _model(portfolio, universe, args.history), rules,
        tax_rate=args.tax_rate if args.tax_rate is not None else rules.default_tax_rate,
        confidence=args.confidence, horizon_days=args.horizon_days, target_mode=target_mode,
        realized_gains=args.realized_gains, target_override=override,
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


def cmd_run(args):
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()  # noqa: DTZ011
    df = pd.read_csv(args.portfolio)
    df.columns = [c.lower() for c in df.columns]
    df["ticker"] = df["ticker"].str.upper()
    extra = df.drop_duplicates("ticker").set_index("ticker")
    planned = pd.read_csv(args.planned) if args.planned else None
    portfolio = Portfolio.from_frame(df, as_of, planned)
    problem = _build(args, portfolio, Universe.default(), extra)
    report.run(problem, Path(args.out), f"{Path(args.portfolio).stem}", method=args.method,
               robust=not args.no_robust, quick=args.quick, animate=not args.no_anim)
    print(f"-> {args.out}")


def cmd_interactive(args):
    print("Tax-loss harvest planner. Wash-sale (US) / superficial-loss (CA) aware.\n")
    args.jurisdiction = _ask("Jurisdiction US or CA", "US", str.upper)
    rules = JURISDICTIONS[args.jurisdiction]
    print(f"  {rules.note}")
    args.tax_rate = _ask("Effective tax rate on capital gains", round(rules.default_tax_rate, 4),
                         float)
    args.realized_gains = _ask("Gains already realised this tax year", 0.0, float)
    args.confidence = _ask("Required confidence P(losses >= target)", 0.9, float)
    args.horizon_days = _ask("Trading days until you harvest", 40, int)
    args.target = _ask("Target: 'tax' (losses = rate x E[gains]), 'offset' (losses = E[gains]) "
                       "or an amount", "tax")
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

    r = sub.add_parser("run", help="optimise a portfolio CSV")
    r.add_argument("portfolio", help="CSV: account,ticker,shares,cost_basis,acquired,price[,drip]"
                                     " (+ optional factor,beta,idio_vol,wash_group,sector)")
    r.add_argument("--planned", help="CSV of planned buys: ticker,on,account")
    r.add_argument("--as-of")
    r.add_argument("--jurisdiction", default="US", choices=["US", "CA", "us", "ca"])
    r.add_argument("--tax-rate", type=float)
    r.add_argument("--confidence", type=float, default=0.9)
    r.add_argument("--horizon-days", type=int, default=40)
    r.add_argument("--realized-gains", type=float, default=0.0)
    r.add_argument("--target", default="tax", help="'tax', 'offset' or a fixed amount")
    common(r, "out")
    r.set_defaults(fn=cmd_run)

    i = sub.add_parser("interactive", help="type your portfolio in")
    common(i, "out")
    i.set_defaults(fn=cmd_interactive)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
