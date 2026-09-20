"""PURPOSE: momentum tilt between SPY and TLT around a static 60/40 mix.
INPUTS: history (DataFrame, adjusted closes, rows up to and including the decision date).
OUTPUTS: target weights (pd.Series indexed by ticker, sum <= 1). Uses only past data.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class MomentumTilt:
    lookback: int = 126
    tilt: float = 0.20
    base_equity: float = 0.60

    def weights(self, history: pd.DataFrame) -> pd.Series:
        base = pd.Series({"SPY": self.base_equity, "TLT": 1.0 - self.base_equity})
        if len(history) <= self.lookback:
            return base
        window = history[["SPY", "TLT"]].iloc[-self.lookback - 1 :]
        mom = window.iloc[-1] / window.iloc[0] - 1.0
        leader = "SPY" if mom["SPY"] >= mom["TLT"] else "TLT"
        laggard = "TLT" if leader == "SPY" else "SPY"
        shift = min(self.tilt, base[laggard])
        w = base.copy()
        w[leader] += shift
        w[laggard] -= shift
        return w


def build(params: dict[str, Any]) -> MomentumTilt:
    return MomentumTilt(
        lookback=int(params.get("lookback", 126)),
        tilt=float(params.get("tilt", 0.20)),
        base_equity=float(params.get("base_equity", 0.60)),
    )
