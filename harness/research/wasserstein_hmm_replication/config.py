"""PURPOSE: explicit assumptions and published targets for the clean-room replication.
INPUTS: none.
OUTPUTS: immutable ReplicationConfig and paper target constants.
"""

from dataclasses import asdict, dataclass

ASSET_LABELS = {
    "SPY": "SPX",
    "TLT": "BOND",
    "GLD": "GOLD",
    "USO": "OIL",
    "UUP": "USD",
}

PUBLISHED = {
    "wasserstein_hmm": {"sharpe": 2.18, "max_drawdown": -0.0543, "turnover": 0.0079},
    "knn": {"sharpe": 1.81, "max_drawdown": -0.1252, "turnover": 0.5665},
    "equal_weight": {"sharpe": 1.59, "max_drawdown": -0.0987},
    "spx": {"sharpe": 1.18, "max_drawdown": -0.1462},
}


@dataclass(frozen=True)
class ReplicationConfig:
    tickers: tuple[str, ...] = tuple(ASSET_LABELS)
    data_start: str = "2005-01-01"
    data_end_exclusive: str = "2026-02-21"
    oos_start: str = "2023-06-02"
    oos_end: str = "2026-02-20"
    volatility_window: int = 60
    momentum_window: int = 20
    candidate_states: tuple[int, ...] = (2, 3, 4, 5, 6)
    template_count: int = 6
    validation_days: int = 126
    refit_frequency: int = 10
    order_selection_frequency: int = 63
    hmm_iterations: int = 50
    complexity_penalty: float = 0.002
    template_smoothing: float = 0.05
    covariance_shrinkage: float = 0.10
    knn_neighbors: int = 50
    risk_aversion: float = 3.0
    turnover_penalty: float = 0.0001
    max_weight: float = 0.60
    realized_cost_bps: float = 5.0
    random_seed: int = 7

    def as_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["tickers"] = list(self.tickers)
        value["candidate_states"] = list(self.candidate_states)
        return value

