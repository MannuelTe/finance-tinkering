"""PURPOSE: find the performance-measurement convention behind the paper's passive benchmarks.

Boukardagha (2026), arXiv:2603.04441v1 reports, out of sample:
    SPX Buy & Hold  Sharpe 1.18, max drawdown -14.62%
    Equal weight    Sharpe 1.59, max drawdown -9.87%
Passive benchmarks have no model parameters, so matching them only identifies *conventions*
(price data, return type, Sharpe definition, drawdown definition, window, rebalancing).

Public API
    apply_convention(returns, convention, rf_daily) -> dict   metrics of one daily series
    asset_returns(convention) -> DataFrame                    daily asset returns for a data convention
    portfolio_returns(weights, convention, lag=0) -> Series   w . r under the convention
    load_rf_daily(kind) -> Series                             daily T-bill rate (simple or log)
    main()                                                    full sweep -> results.json

Input `returns` of apply_convention must already be in the convention's return space
(`return_type` "simple" or "log"); `portfolio_returns` / `benchmark_returns` produce that.

Run:  PYTHONPATH=../../paper-replication/src ../../paper-replication/.venv/bin/python conventions.py
"""

from __future__ import annotations

import itertools
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
REPL = HERE.parents[1] / "paper-replication"

TARGETS = {
    "spx": {"sharpe": 1.18, "max_drawdown": -0.1462},
    "equal_weight": {"sharpe": 1.59, "max_drawdown": -0.0987},
    "hmm": {"sharpe": 2.18, "max_drawdown": -0.0543, "turnover": 0.0079},
    "knn": {"sharpe": 1.81, "max_drawdown": -0.1252, "turnover": 0.5665},
}
SLEEVES = ["SPX", "BOND", "GOLD", "OIL", "USD"]
REPL_TICKERS = {"SPX": "SPY", "BOND": "TLT", "GOLD": "GLD", "OIL": "USO", "USD": "UUP"}
MDD_WEIGHT = 10.0  # 1 pp of drawdown miss (0.01) costs the same as 0.1 of Sharpe miss

# Baseline = the replication's convention.
BASELINE = {
    "price_basis": "adj",        # adj (total return) | raw (unadjusted Close)
    "spx_instrument": "SPY",     # SPY | ^GSPC | ^SP500TR
    "other_assets": "etf",       # etf (TLT GLD USO UUP) | futures (TLT GC=F CL=F DX-Y.NYB)
    "return_type": "simple",     # simple | log  (log: portfolio return = w . log r, as the paper says)
    "ew_rebalance": "daily",     # daily | monthly | buy_hold
    "start": "2023-06-02",       # first return date included
    "end": "2026-02-20",         # last return date included
    "rf": "none",                # none | excess (num & denom on excess) | numerator (mean - rf) / std(r)
    "ann": 252,                  # 252 | 260 | 365
    "ddof": 1,                   # 0 | 1
    "freq": "daily",             # daily | monthly (sqrt(12) annualisation, 'ann' ignored)
    "mdd": "compound",           # compound (wealth=prod(1+r) or exp(cum log)) |
                                 # additive_rel ((1+cumsum)/cummax-1) | additive_abs (cumsum-cummax)
}


# ----------------------------------------------------------------------------- data
@lru_cache(maxsize=None)
def _calendar() -> pd.DatetimeIndex:
    prices = pd.read_csv(REPL / "data" / "prices.csv", index_col=0, parse_dates=True)
    return pd.DatetimeIndex(prices.dropna().index)


@lru_cache(maxsize=None)
def _prices(basis: str) -> pd.DataFrame:
    """Prices on the NYSE calendar of the replication. adj ETFs come from the replication cache."""
    cal = _calendar()
    fresh = pd.read_csv(DATA / ("yahoo_adjusted.csv" if basis == "adj" else "yahoo_raw.csv"),
                        index_col=0, parse_dates=True)
    fresh.index = pd.DatetimeIndex(fresh.index).tz_localize(None)
    out = fresh.reindex(fresh.index.union(cal)).ffill().reindex(cal)
    if basis == "adj":
        repl = pd.read_csv(REPL / "data" / "prices.csv", index_col=0, parse_dates=True).reindex(cal)
        out[list(REPL_TICKERS.values())] = repl[list(REPL_TICKERS.values())]
    return out


def tickers_for(convention: dict) -> dict[str, str]:
    t = dict(REPL_TICKERS)
    t["SPX"] = convention["spx_instrument"]
    if convention["other_assets"] == "futures":
        t.update({"GOLD": "GC=F", "OIL": "CL=F", "USD": "DX-Y.NYB"})
    return t


def asset_returns(convention: dict) -> pd.DataFrame:
    """Daily simple returns of the five sleeves (column names = SLEEVES) for a data convention."""
    t = tickers_for(convention)
    px = _prices(convention["price_basis"])[[t[s] for s in SLEEVES]]
    px.columns = SLEEVES
    return px.pct_change().iloc[1:]


@lru_cache(maxsize=None)
def load_rf_daily(kind: str = "simple", source: str = "DTB3") -> pd.Series:
    """Daily 3-month T-bill return on the NYSE calendar, compounded: (1+y)^(1/252)-1 or log(1+y)/252."""
    if source == "DTB3":
        y = pd.read_csv(DATA / "dtb3.csv", index_col=0, parse_dates=True).iloc[:, 0]
    else:
        y = pd.read_csv(DATA / "yahoo_raw.csv", index_col=0, parse_dates=True)["^IRX"]
    y = pd.to_numeric(y, errors="coerce") / 100.0
    cal = _calendar()
    y = y.reindex(y.index.union(cal)).ffill().reindex(cal)
    # the rate known at the previous close accrues over session t
    y = y.shift(1).bfill()
    return np.log1p(y) / 252 if kind == "log" else (1 + y) ** (1 / 252) - 1


def portfolio_returns(weights: pd.DataFrame, convention: dict, lag: int = 0) -> pd.Series:
    """w_t . r_t in the convention's return space; lag=1 applies weights decided for t on t+1."""
    r = asset_returns(convention)
    if convention["return_type"] == "log":
        r = np.log1p(r)
    w = weights.copy()
    w.columns = SLEEVES
    w = w.shift(lag).dropna()
    return (w * r.reindex(w.index)).sum(axis=1)


def benchmark_returns(convention: dict) -> dict[str, pd.Series]:
    """SPX and equal-weight daily returns (convention's return space) over the full calendar."""
    r = asset_returns(convention)
    log = convention["return_type"] == "log"
    spx = np.log1p(r["SPX"]) if log else r["SPX"]
    start = convention["start"]
    reb = convention["ew_rebalance"]
    if reb == "daily":
        ew = np.log1p(r).mean(axis=1) if log else r.mean(axis=1)
    else:
        # drifting weights from each rebalance date; returns in simple space first
        sub = r.loc[start:]
        if reb == "buy_hold":
            groups = pd.Series(0, index=sub.index)
        else:  # monthly: rebalance at the first session of each month
            groups = pd.Series(sub.index.to_period("M").astype(str), index=sub.index)
        parts = []
        for _, block in sub.groupby(groups.values, sort=False):
            growth = (1 + block).cumprod()
            wealth = growth.mean(axis=1)
            prev = wealth.shift(1).fillna(1.0)
            parts.append(wealth / prev - 1)
        ew_simple = pd.concat(parts).sort_index()
        ew = np.log1p(ew_simple) if log else ew_simple
    return {"spx": spx, "equal_weight": ew}


# ----------------------------------------------------------------------------- metrics
def _drawdown(r: np.ndarray, return_type: str, kind: str) -> float:
    if kind == "compound":
        wealth = np.exp(np.cumsum(r)) if return_type == "log" else np.cumprod(1 + r)
        wealth = np.concatenate([[1.0], wealth])
        return float((wealth / np.maximum.accumulate(wealth) - 1).min())
    cum = np.concatenate([[0.0], np.cumsum(r)])
    peak = np.maximum.accumulate(cum)
    if kind == "additive_rel":
        return float(((1 + cum) / (1 + peak) - 1).min())
    return float((cum - peak).min())  # additive_abs


def apply_convention(returns: pd.Series, convention: dict, rf_daily: pd.Series | None) -> dict:
    """Sharpe, max drawdown, annualised return/vol of a daily return series under a convention.

    `returns` must be in the convention's return space (simple or log). The window
    [start, end] is applied here; rf_daily must be in the same return space.
    """
    c = {**BASELINE, **convention}
    r = returns.loc[c["start"]:c["end"]].dropna()
    rf = (rf_daily.reindex(r.index).ffill().bfill()
          if (rf_daily is not None and c["rf"] != "none") else pd.Series(0.0, index=r.index))
    log = c["return_type"] == "log"
    if c["freq"] == "monthly":
        key = r.index.to_period("M")
        agg = (lambda s: s.groupby(key).sum()) if log else (lambda s: (1 + s).groupby(key).prod() - 1)
        rr, rff, ann = agg(r), agg(rf), 12
    else:
        rr, rff, ann = r, rf, c["ann"]
    ex = rr - rff
    num = ex.mean() if c["rf"] != "none" else rr.mean()
    den = ex.std(ddof=c["ddof"]) if c["rf"] == "excess" else rr.std(ddof=c["ddof"])
    return {
        "sharpe": float(np.sqrt(ann) * num / den),
        "max_drawdown": _drawdown(r.to_numpy(), c["return_type"], c["mdd"]),
        "annualized_return": float(rr.mean() * ann),
        "annualized_volatility": float(rr.std(ddof=c["ddof"]) * np.sqrt(ann)),
        "n_obs": int(len(r)),
    }


def score(res: dict) -> float:
    """|dSharpe_SPX| + |dSharpe_EW| + 10*(|dMDD_SPX| + |dMDD_EW|), MDD in fractions."""
    s = 0.0
    for k in ("spx", "equal_weight"):
        s += abs(res[k]["sharpe"] - TARGETS[k]["sharpe"])
        s += MDD_WEIGHT * abs(res[k]["max_drawdown"] - TARGETS[k]["max_drawdown"])
    return s


def matches_all(res: dict, sh_tol: float = 0.03, dd_tol: float = 0.005) -> bool:
    return all(abs(res[k]["sharpe"] - TARGETS[k]["sharpe"]) <= sh_tol
               and abs(res[k]["max_drawdown"] - TARGETS[k]["max_drawdown"]) <= dd_tol
               for k in ("spx", "equal_weight"))


def evaluate_benchmarks(convention: dict) -> dict:
    c = {**BASELINE, **convention}
    rf = load_rf_daily("log" if c["return_type"] == "log" else "simple")
    series = benchmark_returns(c)
    out = {k: apply_convention(v, c, rf) for k, v in series.items()}
    out["score"] = score(out)
    return out


# ----------------------------------------------------------------------------- sweep
GRID = {
    "price_basis": ["adj", "raw"],
    "spx_instrument": ["SPY", "^GSPC", "^SP500TR"],
    "other_assets": ["etf", "futures"],
    "return_type": ["simple", "log"],
    "ew_rebalance": ["daily", "monthly", "buy_hold"],
    "start": ["2023-06-01", "2023-06-02", "2023-06-05", "2023-06-06"],
    "end": ["2026-02-13", "2026-02-18", "2026-02-19", "2026-02-20"],  # data end 2026-02-20
}
METRIC_GRID = {
    "rf": ["none", "excess", "numerator"],
    "ann": [252, 260, 365],
    "ddof": [0, 1],
    "freq": ["daily", "monthly"],
    "mdd": ["compound", "additive_rel", "additive_abs"],
}


def _fmt(res: dict) -> dict:
    return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in res.items()}


def run_grid() -> list[dict]:
    rows = []
    rf_cache = {k: load_rf_daily(k) for k in ("simple", "log")}
    data_keys = list(GRID)
    for combo in itertools.product(*GRID.values()):
        dc = dict(zip(data_keys, combo))
        if dc["spx_instrument"] == "^SP500TR" and dc["price_basis"] == "raw":
            continue  # identical to adj (index level is not adjusted)
        c0 = {**BASELINE, **dc}
        series = benchmark_returns(c0)
        rf = rf_cache["log" if c0["return_type"] == "log" else "simple"]
        for mc in itertools.product(*METRIC_GRID.values()):
            m = dict(zip(METRIC_GRID, mc))
            if m["freq"] == "monthly" and m["ann"] != 252:
                continue  # annualisation factor is sqrt(12) for monthly
            c = {**c0, **m}
            res = {k: apply_convention(v, c, rf) for k, v in series.items()}
            rows.append({"convention": c, "spx": _fmt(res["spx"]),
                         "equal_weight": _fmt(res["equal_weight"]),
                         "score": round(score(res), 5), "matches_all": matches_all(res)})
    rows.sort(key=lambda r: r["score"])
    return rows


def sensitivity() -> list[dict]:
    """Move one dimension at a time away from the replication baseline."""
    out = [{"dimension": "baseline", "value": "-", **_flat(evaluate_benchmarks(BASELINE))}]
    for dim, values in {**GRID, **METRIC_GRID}.items():
        for v in values:
            if v == BASELINE[dim]:
                continue
            out.append({"dimension": dim, "value": v, **_flat(evaluate_benchmarks({dim: v}))})
    return out


def _flat(res: dict) -> dict:
    return {"spx_sharpe": round(res["spx"]["sharpe"], 3),
            "spx_mdd": round(res["spx"]["max_drawdown"], 4),
            "ew_sharpe": round(res["equal_weight"]["sharpe"], 3),
            "ew_mdd": round(res["equal_weight"]["max_drawdown"], 4),
            "score": round(res["score"], 3)}


def window_search(convention: dict, top: int = 10) -> list[dict]:
    """Search start in 2023 and end in 2025-09..2026-02 with all other dimensions fixed (looser fit)."""
    c = {**BASELINE, **convention}
    cal = _calendar()
    starts = [d for d in cal if pd.Timestamp("2023-01-01") <= d <= pd.Timestamp("2023-12-29")]
    ends = [d for d in cal if pd.Timestamp("2025-09-01") <= d]  # calendar ends 2026-02-20
    rf = load_rf_daily("log" if c["return_type"] == "log" else "simple")
    rows = []
    for s in starts[::1]:
        cs = {**c, "start": str(s.date())}
        series = benchmark_returns(cs)  # buy-and-hold/monthly paths depend on the start
        for e in ends[::1]:
            ce = {**cs, "end": str(e.date())}
            res = {k: apply_convention(v, ce, rf) for k, v in series.items()}
            rows.append({"start": ce["start"], "end": ce["end"], **_flat({**res, "score": score(res)})})
    rows.sort(key=lambda r: r["score"])
    return rows[:top]


def strategy_numbers(conventions: list[dict]) -> list[dict]:
    out = []
    for name in ("hmm", "knn"):
        daily = pd.read_csv(REPL / "results" / f"{name}_daily.csv", index_col=0, parse_dates=True)
        w = daily.filter(like="weight_")
        for i, conv in enumerate(conventions):
            c = {**BASELINE, **conv}
            rf = load_rf_daily("log" if c["return_type"] == "log" else "simple")
            for lag in (0, 1):
                # lag=1 needs weights one day earlier: shift the saved weights forward.
                r = portfolio_returns(w, c, lag=lag)
                res = apply_convention(r, c, rf)
                to = daily["turnover"].mean()
                out.append({"strategy": name, "convention_rank": i, "lag": lag,
                            "sharpe": round(res["sharpe"], 3),
                            "max_drawdown": round(res["max_drawdown"], 4),
                            "n_obs": res["n_obs"], "turnover": round(float(to), 4),
                            "convention": c})
    return out


def _first(rows: list[dict], **fixed) -> dict:
    return next(r for r in rows if all(r["convention"][k] == v for k, v in fixed.items()))


def main() -> None:
    rows = run_grid()
    top = rows[:10]
    picks = {
        "A_best_overall": _first(rows),
        "B_best_daily_sharpe_no_rf": _first(rows, freq="daily", rf="none"),
        "C_paper_stated_log_daily_rebalanced": _first(rows, freq="daily", rf="none", return_type="log",
                                                      ew_rebalance="daily"),
    }
    chosen = [p["convention"] for p in picks.values()] + [dict(BASELINE)]
    sharpe_only = [r for r in rows if all(abs(r[k]["sharpe"] - TARGETS[k]["sharpe"]) <= 0.03
                                          for k in ("spx", "equal_weight"))]
    result = {
        "targets": TARGETS,
        "scoring": "score = |dSharpe_SPX| + |dSharpe_EW| + 10*(|dMDD_SPX| + |dMDD_EW|), MDD as fraction",
        "n_conventions": len(rows),
        "n_matching_all": sum(r["matches_all"] for r in rows),
        "n_matching_both_sharpes_0.03": len(sharpe_only),
        "most_negative_ew_mdd_in_grid": min(r["equal_weight"]["max_drawdown"] for r in rows),
        "top": top,
        "picks": picks,
        "sensitivity": sensitivity(),
        "window_search": {name: window_search(p["convention"]) for name, p in picks.items()
                          if not name.startswith("A")},
        "strategies": strategy_numbers(chosen),
        "strategy_convention_names": list(picks) + ["D_baseline_replication"],
        "grid": rows,
    }
    (HERE / "results.json").write_text(json.dumps(result, indent=1, default=str))
    for name, r in picks.items():
        print(name, round(r["score"], 3), r["convention"], r["spx"], r["equal_weight"])
    for r in result["strategies"]:
        print({k: v for k, v in r.items() if k != "convention"})


if __name__ == "__main__":
    main()
