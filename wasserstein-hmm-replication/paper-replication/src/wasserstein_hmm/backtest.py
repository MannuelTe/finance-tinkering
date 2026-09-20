"""PURPOSE: strictly causal Wasserstein-HMM, KNN, and passive benchmark backtests.
INPUTS: adjusted prices and an explicit replication configuration.
OUTPUTS: daily returns, weights, turnover, regime/order paths, and summary metrics.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from sklearn.preprocessing import StandardScaler

from .config import ReplicationConfig
from .data import market_data
from .models import fit_regime_model, initialize_templates, select_order
from .optimize import solve_mvo


@dataclass(frozen=True)
class Backtest:
    gross_returns: pd.Series
    net_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    regimes: pd.Series | None = None
    orders: pd.Series | None = None


def _summarize_arrays(
    dates: list[pd.Timestamp], gross: list[float], weights: list[np.ndarray],
    turnover: list[float], columns: pd.Index, config: ReplicationConfig,
    regimes: list[int] | None = None, orders: list[int] | None = None,
) -> Backtest:
    index = pd.DatetimeIndex(dates, name="date")
    gross_s = pd.Series(gross, index=index, name="gross_return")
    turn_s = pd.Series(turnover, index=index, name="turnover")
    net = gross_s - turn_s * config.realized_cost_bps / 1e4
    return Backtest(
        gross_s, net.rename("net_return"), pd.DataFrame(weights, index=index, columns=columns), turn_s,
        pd.Series(regimes, index=index, name="regime") if regimes is not None else None,
        pd.Series(orders, index=index, name="hmm_order") if orders is not None else None,
    )


def run_hmm(
    prices: pd.DataFrame, config: ReplicationConfig, selector=select_order,
) -> tuple[Backtest, dict[str, object]]:
    outcomes, features = market_data(prices, config)
    oos = features.loc[config.oos_start:config.oos_end]
    pre = features.index < oos.index[0]
    bank = initialize_templates(features.loc[pre].to_numpy(), outcomes.loc[pre].to_numpy(), config)
    previous = np.full(len(prices.columns), 1 / len(prices.columns))
    fitted = None
    current_k = config.template_count
    dates: list[pd.Timestamp] = []
    gross: list[float] = []
    weights: list[np.ndarray] = []
    turnover: list[float] = []
    regimes: list[int] = []
    orders: list[int] = []
    selections: dict[str, object] = {}
    for step, date in enumerate(oos.index):
        history = features.index < date
        x_hist = features.loc[history].to_numpy()
        y_hist = outcomes.loc[history].to_numpy()
        select_now = fitted is None or step % config.order_selection_frequency == 0
        refit_now = fitted is None or step % config.refit_frequency == 0 or select_now
        if refit_now:
            if select_now:
                scaler = StandardScaler().fit(x_hist)
                current_k, scores = selector(scaler.transform(x_hist), config)
                selections[str(date.date())] = {"selected": current_k, "scores": scores}
            fitted = fit_regime_model(x_hist, y_hist, current_k, bank, config)
        probs = fitted.filter(features.loc[date].to_numpy())
        if len(probs) < config.template_count:
            probs = np.pad(probs, (0, config.template_count - len(probs)))
        mean = probs @ bank.return_means
        covariance = np.tensordot(probs, bank.return_covariances, axes=(0, 0))
        target = solve_mvo(
            mean, covariance, previous, config.risk_aversion,
            config.turnover_penalty, config.max_weight,
        )
        turn = 0.5 * np.abs(target - previous).sum()
        dates.append(date)
        gross.append(float(target @ outcomes.loc[date].to_numpy()))
        weights.append(target.copy())
        turnover.append(float(turn))
        regimes.append(int(np.argmax(probs)))
        orders.append(current_k)
        previous = target
    return _summarize_arrays(
        dates, gross, weights, turnover, prices.columns, config, regimes, orders,
    ), selections


def run_knn(prices: pd.DataFrame, config: ReplicationConfig) -> Backtest:
    outcomes, features = market_data(prices, config)
    oos = features.loc[config.oos_start:config.oos_end]
    previous = np.full(len(prices.columns), 1 / len(prices.columns))
    dates: list[pd.Timestamp] = []
    gross: list[float] = []
    weights: list[np.ndarray] = []
    turnover: list[float] = []
    for date in oos.index:
        history = features.index < date
        x_hist = features.loc[history].to_numpy()
        y_hist = outcomes.loc[history].to_numpy()
        scaler = StandardScaler().fit(x_hist)
        train = scaler.transform(x_hist)
        query = scaler.transform(features.loc[[date]].to_numpy())[0]
        count = min(config.knn_neighbors, len(train))
        nearest = np.argpartition(np.square(train - query).sum(axis=1), count - 1)[:count]
        local = y_hist[nearest]
        mean = local.mean(axis=0)
        covariance = LedoitWolf().fit(local).covariance_
        target = solve_mvo(
            mean, covariance, previous, config.risk_aversion,
            config.turnover_penalty, config.max_weight,
        )
        turn = 0.5 * np.abs(target - previous).sum()
        dates.append(date)
        gross.append(float(target @ outcomes.loc[date].to_numpy()))
        weights.append(target.copy())
        turnover.append(float(turn))
        previous = target
    return _summarize_arrays(dates, gross, weights, turnover, prices.columns, config)


def passive_returns(prices: pd.DataFrame, config: ReplicationConfig) -> dict[str, pd.Series]:
    returns = prices.pct_change().loc[config.oos_start:config.oos_end]
    return {"equal_weight": returns.mean(axis=1), "spx": returns[config.tickers[0]]}


def metrics(returns: pd.Series, turnover: pd.Series | None = None) -> dict[str, float]:
    clean = returns.dropna()
    wealth = (1 + clean).cumprod()
    downside = clean[clean < 0].std(ddof=1)
    result = {
        "total_return": float(wealth.iloc[-1] - 1),
        "sharpe": float(np.sqrt(252) * clean.mean() / clean.std(ddof=1)),
        "sortino": float(np.sqrt(252) * clean.mean() / downside) if downside > 0 else float("nan"),
        "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
        "annualized_return": float(clean.mean() * 252),
        "annualized_volatility": float(clean.std(ddof=1) * np.sqrt(252)),
    }
    if turnover is not None:
        result["turnover"] = float(turnover.mean())
        result["turnover_q95"] = float(turnover.quantile(0.95))
    return result
