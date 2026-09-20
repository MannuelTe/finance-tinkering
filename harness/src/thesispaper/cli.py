"""`thesispaper` command line: new / check / run / build / all.

PURPOSE: stable CLI over the pipeline (see CONTRACT / AGENTS docs).
INPUTS: subcommand + <slug> (folder under theses/), optional --root (repo root, default cwd).
OUTPUTS: exit code 0 on success, 1 on a reported error (message on stderr).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from thesispaper import figures, latex, results
from thesispaper.backtest import lookahead_check
from thesispaper.data import load_prices, synthetic_prices
from thesispaper.spec import SpecError, Thesis, load_spec, thesis_dir
from thesispaper.strategy import load_strategy

THESIS_MD = "# {slug}\n\nDescribe the investment thesis here in plain language.\n"
YAML = """title: "{slug}"
author: ""
slug: {slug}
summary: >
  One paragraph summarising the thesis.
universe: [SPY, TLT]
benchmark: SPY
start: 2015-01-01
end: null
base_currency: USD
costs_bps: 5.0
rebalance: monthly
{data_source}strategy:
  module: strategy.py
  params:
    weights: {{SPY: 0.6, TLT: 0.4}}
hypotheses:
  - {{id: H1, statement: "State a testable hypothesis."}}
sections: []
extra_sections: []
"""
STRATEGY_PY = '''"""Thesis strategy: weights(history) -> target weights using ONLY rows of `history`."""

import pandas as pd


class Strategy:
    def __init__(self, params: dict) -> None:
        self.w = params.get("weights", {})

    def weights(self, history: pd.DataFrame) -> pd.Series:
        return pd.Series(self.w, dtype=float).reindex(history.columns).fillna(0.0)


def build(params: dict) -> Strategy:
    return Strategy(params)
'''


def cmd_new(slug: str, root: Path, synthetic: bool = False) -> None:
    d = thesis_dir(slug, root)
    if d.exists():
        raise SpecError(f"{d} already exists")
    d.mkdir(parents=True)
    (d / "thesis.md").write_text(THESIS_MD.format(slug=slug))
    src = "data_source: synthetic\n" if synthetic else ""
    (d / "thesis.yaml").write_text(YAML.format(slug=slug, data_source=src))
    (d / "strategy.py").write_text(STRATEGY_PY)
    print(f"scaffolded {d}")


def _synthetic_probe(spec: Thesis):
    return synthetic_prices(spec.universe, "2020-01-01", None, seed=1, n_years=1.0)


def cmd_check(spec: Thesis) -> None:
    load_strategy(spec)
    ok = lookahead_check(_synthetic_probe(spec), lambda: load_strategy(spec), spec.rebalance)
    if not ok:
        raise SpecError("no-lookahead smoke test FAILED: weights changed when future prices did")
    print(f"check ok: {spec.slug} (spec valid, strategy loads, no lookahead)")


def cmd_run(spec: Thesis) -> Path:
    prices = load_prices(spec)
    run = results.compute(spec, prices)
    jp, _ = results.write_outputs(spec, run.results)
    figures.make_all(run.bt.returns, run.bench_returns, run.sensitivity,
                     spec.directory / "figures", spec.benchmark)
    print(f"wrote {jp} and figures/")
    return jp


def cmd_build(spec: Thesis, root: Path) -> Path:
    if not (spec.directory / "numbers.tex").exists():
        raise SpecError("numbers.tex missing; run `thesispaper run` first")
    latex.write_paper(spec, root)
    pdf = latex.compile_pdf(spec)
    print(f"built {pdf}")
    return pdf


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="thesispaper", description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["new", "check", "run", "build", "all"])
    ap.add_argument("slug")
    ap.add_argument("--root", type=Path, default=Path.cwd(), help="repo root containing theses/")
    ap.add_argument("--synthetic", action="store_true", help="(new) use synthetic data_source")
    a = ap.parse_args(argv)
    try:
        if a.command == "new":
            cmd_new(a.slug, a.root, a.synthetic)
            return 0
        spec = load_spec(a.slug, a.root)
        if a.command in ("check", "all"):
            cmd_check(spec)
        if a.command in ("run", "all"):
            cmd_run(spec)
        if a.command in ("build", "all"):
            cmd_build(spec, a.root)
    except (SpecError, latex.TemplateError, FileNotFoundError, ValueError, AttributeError,
            TypeError, ImportError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
