"""Strategy protocol, built-ins and loader for theses/<slug>/strategy.py.

PURPOSE: a strategy maps price HISTORY to TARGET WEIGHTS; the backtest guarantees no lookahead.
INPUTS: `weights(history)`: history = price DataFrame up to and including the last known close
(the backtest passes prices strictly BEFORE the return day being earned).
OUTPUTS: pd.Series of target weights indexed by ticker, each >= 0, sum <= 1 (rest is cash).
A thesis strategy module must expose `build(params: dict) -> Strategy`.
Built-ins: `builtin:buy_hold` (weights drift), `builtin:constant_mix` (rebalance to weights).
"""

from __future__ import annotations

import importlib.util
import sys
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from thesispaper.spec import Thesis


@runtime_checkable
class Strategy(Protocol):
    def weights(self, history: pd.DataFrame) -> pd.Series: ...


def _target(history: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
    w = params.get("weights")
    if w:
        return pd.Series(w, dtype=float).reindex(history.columns).fillna(0.0)
    return pd.Series(1.0 / history.shape[1], index=history.columns)


class ConstantMix:
    """Always target the same weights (params.weights, default equal weight, fully invested)."""

    def __init__(self, params: dict[str, Any]) -> None:
        self.params = params

    def weights(self, history: pd.DataFrame) -> pd.Series:
        return _target(history, self.params)


class BuyHold:
    """Initial weights left to drift with prices since the start of history."""

    def __init__(self, params: dict[str, Any]) -> None:
        self.params = params

    def weights(self, history: pd.DataFrame) -> pd.Series:
        w0 = _target(history, self.params)
        value = w0 * history.iloc[-1] / history.iloc[0]
        return value / (value.sum() + (1.0 - w0.sum()))


BUILTINS = {"constant_mix": ConstantMix, "buy_hold": BuyHold}


def load_strategy(spec: Thesis) -> Strategy:
    """Instantiate the thesis strategy (fresh object each call)."""
    mod = spec.strategy_module
    if mod.startswith("builtin:"):
        name = mod.split(":", 1)[1]
        if name not in BUILTINS:
            raise ValueError(f"unknown builtin strategy {name!r}; have {sorted(BUILTINS)}")
        return BUILTINS[name](spec.strategy_params)
    path = spec.directory / mod
    if not path.exists():
        raise FileNotFoundError(f"strategy module not found: {path}")
    mspec = importlib.util.spec_from_file_location(f"thesis_{spec.slug}_strategy", path)
    if mspec is None or mspec.loader is None:
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(mspec)
    sys.modules[mspec.name] = module  # needed by @dataclass + postponed annotations
    mspec.loader.exec_module(module)
    if not hasattr(module, "build"):
        raise AttributeError(f"{path} must define build(params: dict) -> Strategy")
    strat = module.build(dict(spec.strategy_params))
    if not callable(getattr(strat, "weights", None)):
        raise TypeError(f"{path}: build() must return an object with weights(history)")
    return strat
