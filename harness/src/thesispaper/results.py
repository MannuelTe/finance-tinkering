"""Run the analysis and write results.json + numbers.tex (the only source of numbers in a paper).

PURPOSE: compute every headline number once; the paper cites them only through LaTeX macros.
INPUTS: `Thesis`, price panel (universe + benchmark).
OUTPUTS: `Run` (in-memory series), results.json, numbers.tex in theses/<slug>/.

results.json schema (schema_version 1):
  slug, title, hypotheses [{id, statement}] (passthrough)
  sample   {start, end, n_obs, years, periods_per_year}
  config   {costs_bps, rebalance, universe, benchmark, base_currency, data_source,
            strategy {module, params}}
  strategy / benchmark  {total_return, cagr, vol, sharpe, max_drawdown}   (benchmark: same keys)
  average_turnover      mean daily turnover of the strategy
  estimation {mle {mu, var, se_mu, se_var} (daily, net returns),
              kelly {full, fraction, cap, fractional}}
  bootstrap  {n_boot, mean_block, seed, alpha, sharpe {low, high}, mean {low, high}} (annualised)
  sensitivity {costs_bps [..], sharpe [..], cagr [..]}
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from thesispaper import metrics as m
from thesispaper.backtest import BacktestResult, run
from thesispaper.spec import Thesis
from thesispaper.strategy import load_strategy

SENS_COSTS = [0.0, 5.0, 10.0, 25.0, 50.0, 100.0]
KELLY_FRACTION, KELLY_CAP = 0.5, 1.0

# LaTeX macro name -> (dotted path in results.json, format kind). Templates may rely on these.
NUMBER_MACROS: dict[str, tuple[str, str]] = {
    "CAGR": ("strategy.cagr", "pct"),
    "Vol": ("strategy.vol", "pct"),
    "Sharpe": ("strategy.sharpe", "num"),
    "MaxDD": ("strategy.max_drawdown", "pct"),
    "TotalReturn": ("strategy.total_return", "pct"),
    "BenchCAGR": ("benchmark.cagr", "pct"),
    "BenchVol": ("benchmark.vol", "pct"),
    "BenchSharpe": ("benchmark.sharpe", "num"),
    "BenchMaxDD": ("benchmark.max_drawdown", "pct"),
    "BenchTotalReturn": ("benchmark.total_return", "pct"),
    "NObs": ("sample.n_obs", "int"),
    "YearsSample": ("sample.years", "num"),
    "StartDate": ("sample.start", "str"),
    "EndDate": ("sample.end", "str"),
    "CostBps": ("config.costs_bps", "g"),
    "AvgTurnover": ("average_turnover", "pct"),
    "SharpeCILow": ("bootstrap.sharpe.low", "num"),
    "SharpeCIHigh": ("bootstrap.sharpe.high", "num"),
    "MeanCILow": ("bootstrap.mean.low", "pct"),
    "MeanCIHigh": ("bootstrap.mean.high", "pct"),
    "MuDaily": ("estimation.mle.mu", "sci"),
    "MuDailySE": ("estimation.mle.se_mu", "sci"),
    "VarDaily": ("estimation.mle.var", "sci"),
    "KellyFull": ("estimation.kelly.full", "num"),
    "KellyFrac": ("estimation.kelly.fractional", "num"),
    "KellyFraction": ("estimation.kelly.fraction", "num"),
    "KellyCap": ("estimation.kelly.cap", "num"),
    "NBoot": ("bootstrap.n_boot", "int"),
}


@dataclass(frozen=True)
class Run:
    results: dict[str, Any]
    bt: BacktestResult
    bench_returns: pd.Series
    sensitivity: dict[str, list[float]]


def _perf(r: pd.Series) -> dict[str, float]:
    return {
        "total_return": m.total_return(r), "cagr": m.cagr(r), "vol": m.ann_vol(r),
        "sharpe": m.sharpe(r), "max_drawdown": m.max_drawdown(r),
    }


def compute(spec: Thesis, prices: pd.DataFrame, n_boot: int = 1000) -> Run:
    bt = run(prices[spec.universe], load_strategy(spec), spec.costs_bps, spec.rebalance)
    r = bt.returns
    bench = m.simple_returns(prices[spec.benchmark]).reindex(r.index)
    costs = sorted({*SENS_COSTS, spec.costs_bps})
    sens = {"costs_bps": costs, "sharpe": [], "cagr": []}
    for c in costs:
        rc = run(prices[spec.universe], load_strategy(spec), c, spec.rebalance).returns
        sens["sharpe"].append(m.sharpe(rc))
        sens["cagr"].append(m.cagr(rc))
    mle = m.gaussian_mle(r)
    block = 10
    lo_s, hi_s = m.bootstrap_ci(r, "sharpe", n_boot, block, 0.05, spec.seed)
    lo_m, hi_m = m.bootstrap_ci(r, "mean", n_boot, block, 0.05, spec.seed)
    res: dict[str, Any] = {
        "schema_version": 1, "slug": spec.slug, "title": spec.title,
        "hypotheses": [asdict(h) for h in spec.hypotheses],
        "sample": {
            "start": str(prices.index[0].date()), "end": str(prices.index[-1].date()),
            "n_obs": len(r), "years": len(r) / m.PPY, "periods_per_year": m.PPY,
        },
        "config": {
            "costs_bps": spec.costs_bps, "rebalance": spec.rebalance,
            "universe": spec.universe, "benchmark": spec.benchmark,
            "base_currency": spec.base_currency, "data_source": spec.data_source,
            "strategy": {"module": spec.strategy_module, "params": spec.strategy_params},
        },
        "strategy": _perf(r), "benchmark": _perf(bench),
        "average_turnover": float(bt.turnover.mean()),
        "estimation": {
            "mle": {"mu": mle.mu, "var": mle.var, "se_mu": mle.se_mu, "se_var": mle.se_var},
            "kelly": {
                "full": m.kelly(mle.mu, mle.var), "fraction": KELLY_FRACTION, "cap": KELLY_CAP,
                "fractional": m.fractional_kelly(mle.mu, mle.var, KELLY_FRACTION, KELLY_CAP),
            },
        },
        "bootstrap": {
            "n_boot": n_boot, "mean_block": block, "seed": spec.seed, "alpha": 0.05,
            "sharpe": {"low": lo_s, "high": hi_s}, "mean": {"low": lo_m, "high": hi_m},
        },
        "sensitivity": sens,
    }
    return Run(res, bt, bench, sens)


def _get(d: dict[str, Any], path: str) -> Any:
    for key in path.split("."):
        d = d[key]
    return d


def _fmt(v: Any, kind: str) -> str:
    if kind == "pct":
        return f"{v * 100:.2f}\\%"
    return {
        "num": lambda: f"{v:.2f}", "int": lambda: f"{int(v)}", "g": lambda: f"{v:g}",
        "sci": lambda: f"{v:.3e}", "str": lambda: str(v),
    }[kind]()


def numbers_tex(results: dict[str, Any]) -> str:
    lines = ["% generated by thesispaper from results.json; do not edit"]
    for name, (path, kind) in NUMBER_MACROS.items():
        lines.append(f"\\newcommand{{\\{name}}}{{{_fmt(_get(results, path), kind)}}}")
    return "\n".join(lines) + "\n"


def write_outputs(spec: Thesis, results: dict[str, Any]) -> tuple[Path, Path]:
    jp, tp = spec.directory / "results.json", spec.directory / "numbers.tex"
    jp.write_text(json.dumps(results, indent=2, default=float) + "\n")
    tp.write_text(numbers_tex(results))
    return jp, tp
