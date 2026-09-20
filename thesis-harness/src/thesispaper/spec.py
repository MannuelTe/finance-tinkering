"""Thesis specification: dataclass plus loader/validator for theses/<slug>/thesis.yaml.

PURPOSE: single validated description of a thesis (universe, dates, costs, strategy, hypotheses).
INPUTS: slug + repo root (folder containing theses/), or a raw dict for tests.
OUTPUTS: `Thesis` dataclass; `SpecError` listing every problem found.

Keys: title, author, slug, summary, universe, benchmark, start, end, base_currency, costs_bps,
rebalance (daily|weekly|monthly), strategy {module, params}, hypotheses [{id, statement}],
sections, extra_sections, and optional data_source (yfinance|csv|synthetic), csv_files, seed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REBALANCE = ("daily", "weekly", "monthly")
DATA_SOURCES = ("yfinance", "csv", "synthetic")
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class SpecError(ValueError):
    """Raised when thesis.yaml is missing or invalid; message lists all problems."""


@dataclass(frozen=True)
class Hypothesis:
    id: str
    statement: str


@dataclass(frozen=True)
class Thesis:
    slug: str
    title: str
    author: str
    summary: str
    universe: list[str]
    benchmark: str
    start: str
    end: str | None
    base_currency: str
    costs_bps: float
    rebalance: str
    strategy_module: str
    strategy_params: dict[str, Any]
    hypotheses: list[Hypothesis]
    sections: list[str] = field(default_factory=list)
    extra_sections: list[str] = field(default_factory=list)
    data_source: str = "yfinance"
    csv_files: dict[str, str] = field(default_factory=dict)
    seed: int = 0
    directory: Path = Path(".")


def thesis_dir(slug: str, root: Path | None = None) -> Path:
    return Path(root or Path.cwd()) / "theses" / slug


def _date(v: Any) -> str | None:
    return None if v is None else str(v)


def parse_spec(d: dict[str, Any], directory: Path) -> Thesis:
    """Validate a raw mapping; raise SpecError listing all problems."""
    errs: list[str] = []
    for key in ("title", "slug", "summary", "universe", "benchmark", "start", "strategy"):
        if d.get(key) in (None, "", []):
            errs.append(f"missing required key: {key}")
    slug = str(d.get("slug", ""))
    if slug and not SLUG_RE.match(slug):
        errs.append(f"slug {slug!r} must match {SLUG_RE.pattern}")
    if slug and slug != directory.name:
        errs.append(f"slug {slug!r} does not match folder name {directory.name!r}")
    uni = d.get("universe") or []
    if not isinstance(uni, list) or not all(isinstance(t, str) for t in uni):
        errs.append("universe must be a list of ticker strings")
        uni = []
    reb = d.get("rebalance", "daily")
    if reb not in REBALANCE:
        errs.append(f"rebalance must be one of {REBALANCE}, got {reb!r}")
    src = d.get("data_source", "yfinance")
    if src not in DATA_SOURCES:
        errs.append(f"data_source must be one of {DATA_SOURCES}, got {src!r}")
    try:
        costs = float(d.get("costs_bps", 0.0))
        if costs < 0:
            errs.append("costs_bps must be >= 0")
    except (TypeError, ValueError):
        errs.append("costs_bps must be a number")
        costs = 0.0
    strat = d.get("strategy") or {}
    if not isinstance(strat, dict) or not strat.get("module"):
        errs.append("strategy.module is required (e.g. 'strategy.py' or 'builtin:constant_mix')")
        strat = {}
    params = strat.get("params") or {}
    if not isinstance(params, dict):
        errs.append("strategy.params must be a mapping")
        params = {}
    hyps: list[Hypothesis] = []
    for i, h in enumerate(d.get("hypotheses") or []):
        if not isinstance(h, dict) or not h.get("id") or not h.get("statement"):
            errs.append(f"hypotheses[{i}] needs id and statement")
        else:
            hyps.append(Hypothesis(str(h["id"]), str(h["statement"])))
    start, end = _date(d.get("start")), _date(d.get("end"))
    if start and end and end <= start:
        errs.append("end must be after start")
    if src == "csv" and not d.get("csv_files"):
        errs.append("data_source csv requires csv_files: {ticker: path}")
    if errs:
        raise SpecError("invalid thesis.yaml:\n  - " + "\n  - ".join(errs))
    return Thesis(
        slug=slug, title=str(d["title"]), author=str(d.get("author") or ""),
        summary=str(d["summary"]).strip(), universe=list(uni), benchmark=str(d["benchmark"]),
        start=str(start), end=end, base_currency=str(d.get("base_currency", "USD")),
        costs_bps=costs, rebalance=reb, strategy_module=str(strat["module"]),
        strategy_params=dict(params), hypotheses=hyps,
        sections=[str(s) for s in d.get("sections") or []],
        extra_sections=[str(s) for s in d.get("extra_sections") or []],
        data_source=src, csv_files={str(k): str(v) for k, v in (d.get("csv_files") or {}).items()},
        seed=int(d.get("seed", 0)), directory=directory,
    )


def load_spec(slug: str, root: Path | None = None) -> Thesis:
    path = thesis_dir(slug, root) / "thesis.yaml"
    if not path.exists():
        raise SpecError(f"{path} not found (run `thesispaper new {slug}`)")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise SpecError(f"{path} must contain a YAML mapping")
    return parse_spec(raw, path.parent)
