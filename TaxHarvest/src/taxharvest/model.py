"""Return distributions F_P for the assets in a portfolio.

Every model is a *daily log-return* model over ``m`` assets and exposes

* ``sample_terminal(n, days, rng)`` -> (n, m) cumulative log returns at the horizon
* ``sample_paths(n, days, rng)``    -> (n, days, m) cumulative paths (small n; animations)
* ``daily_moments()``               -> (mean, cov) of one day's log return

Models: Gaussian, multivariate Student-t, a Gaussian hidden-Markov regime model learned from
history (EM mixture init + Baum-Welch, k by BIC; the learning component), and an iid bootstrap.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

import numpy as np
import pandas as pd

TRADING_DAYS = 252
RF = 0.03

# Illustrative annual factor assumptions (arithmetic mean, vol) and correlations. These are
# round numbers chosen to be plausible, not estimates; replace them or fit from history.
FACTORS = ["US_EQ", "CA_EQ", "INTL_EQ", "EM_EQ", "BOND", "GOLD"]
FACTOR_MU = np.array([0.070, 0.065, 0.065, 0.070, 0.040, 0.030])
FACTOR_VOL = np.array([0.16, 0.14, 0.15, 0.20, 0.06, 0.15])
FACTOR_CORR = np.array(
    [
        [1.00, 0.75, 0.80, 0.65, 0.05, 0.05],
        [0.75, 1.00, 0.70, 0.65, 0.05, 0.15],
        [0.80, 0.70, 1.00, 0.75, 0.05, 0.10],
        [0.65, 0.65, 0.75, 1.00, 0.00, 0.20],
        [0.05, 0.05, 0.05, 0.00, 1.00, 0.25],
        [0.05, 0.15, 0.10, 0.20, 0.25, 1.00],
    ]
)
# Sector factors: independent of the broad factors and of each other; annual vol.
SECTOR_VOL = {"TECH": 0.12, "HEALTH": 0.10, "ENERGY": 0.18, "FIN": 0.10, "CONS": 0.10,
              "COMM": 0.12, "CA_BANKS": 0.08, "CA_ENERGY": 0.16}


# ----------------------------------------------------------------------------- universe
@dataclass
class Universe:
    """Asset metadata: wash-sale identity group, factor exposure, listing."""

    table: pd.DataFrame  # indexed by ticker

    @classmethod
    def default(cls) -> Universe:
        with resources.files("taxharvest").joinpath("assets.csv").open() as fh:
            df = pd.read_csv(fh)
        return cls(df.set_index("ticker"))

    def add(self, ticker: str, *, factor="US_EQ", beta=1.0, idio_vol=0.25, wash_group=None,
            listing="US", name=None, sector="", sector_beta=0.0) -> None:
        self.table.loc[ticker.upper()] = {
            "name": name or ticker.upper(),
            "wash_group": wash_group or ticker.upper(),
            "factor": factor,
            "beta": beta,
            "idio_vol": idio_vol,
            "listing": listing,
            "sector": sector,
            "sector_beta": sector_beta,
        }

    def __contains__(self, ticker: str) -> bool:
        return ticker in self.table.index

    def group(self, ticker: str) -> str:
        return self.table.at[ticker, "wash_group"]

    def factor_model(self, tickers: list[str]) -> GaussianModel:
        t = self.table.loc[tickers]
        B = np.zeros((len(tickers), len(FACTORS)))
        for i, (f, b) in enumerate(zip(t["factor"], t["beta"])):
            B[i, FACTORS.index(f)] = b
        F = FACTOR_CORR * np.outer(FACTOR_VOL, FACTOR_VOL)
        sectors = list(SECTOR_VOL)
        S = np.zeros((len(tickers), len(sectors)))
        for i, (sec, sb) in enumerate(zip(t["sector"].fillna(""), t["sector_beta"].fillna(0))):
            if sec:
                S[i, sectors.index(sec)] = sb
        sv = np.array([SECTOR_VOL[k] for k in sectors])
        cov_a = B @ F @ B.T + (S * sv**2) @ S.T + np.diag(t["idio_vol"].to_numpy() ** 2)
        mu_a = RF + B @ (FACTOR_MU - RF)
        # arithmetic annual -> daily log drift
        mu_d = (mu_a - 0.5 * np.diag(cov_a)) / TRADING_DAYS
        return GaussianModel(mu_d, cov_a / TRADING_DAYS, tickers=list(tickers))


# ----------------------------------------------------------------------------- models
class ReturnModel:
    tickers: list[str]

    def sample_daily(self, n: int, rng: np.random.Generator) -> np.ndarray:
        raise NotImplementedError

    def daily_moments(self) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError

    def sample_terminal(self, n: int, days: int, rng: np.random.Generator) -> np.ndarray:
        out = np.zeros((n, len(self.tickers)))
        for _ in range(days):
            out += self.sample_daily(n, rng)
        return out

    def sample_paths(self, n: int, days: int, rng: np.random.Generator) -> np.ndarray:
        steps = np.stack([self.sample_daily(n, rng) for _ in range(days)], axis=1)
        return np.cumsum(steps, axis=1)

    def subset(self, tickers: list[str]) -> ReturnModel:
        raise NotImplementedError

    def _idx(self, tickers):
        return [self.tickers.index(t) for t in tickers]


@dataclass
class GaussianModel(ReturnModel):
    mu: np.ndarray
    cov: np.ndarray
    tickers: list[str]

    def sample_daily(self, n, rng):
        return rng.multivariate_normal(self.mu, self.cov, size=n, method="cholesky")

    def sample_terminal(self, n, days, rng):  # exact, no loop
        return rng.multivariate_normal(days * self.mu, days * self.cov, size=n, method="cholesky")

    def daily_moments(self):
        return self.mu, self.cov

    def subset(self, tickers):
        ix = self._idx(tickers)
        return GaussianModel(self.mu[ix], self.cov[np.ix_(ix, ix)], list(tickers))


@dataclass
class StudentTModel(ReturnModel):
    """Multivariate t with the given daily mean/covariance (so moments match the Gaussian)."""

    mu: np.ndarray
    cov: np.ndarray
    df: float
    tickers: list[str]

    def sample_daily(self, n, rng):
        scale = self.cov * (self.df - 2) / self.df
        z = rng.multivariate_normal(np.zeros(len(self.mu)), scale, size=n, method="cholesky")
        w = np.sqrt(self.df / rng.chisquare(self.df, size=n))
        return self.mu + z * w[:, None]

    def daily_moments(self):
        return self.mu, self.cov

    def subset(self, tickers):
        ix = self._idx(tickers)
        return StudentTModel(self.mu[ix], self.cov[np.ix_(ix, ix)], self.df, list(tickers))


@dataclass
class RegimeModel(ReturnModel):
    """Gaussian mixture components with Markov switching between them day to day.

    With ``transition`` = rows equal to ``weights`` this is an iid GMM; persistence in the
    transition matrix is what produces crash clusters over multi-week horizons.
    """

    weights: np.ndarray  # (k,) stationary / initial probabilities
    means: np.ndarray  # (k, m)
    covs: np.ndarray  # (k, m, m)
    transition: np.ndarray  # (k, k)
    tickers: list[str]

    def _draw(self, states, rng):
        out = np.empty((len(states), self.means.shape[1]))
        for k in range(len(self.weights)):
            sel = states == k
            if sel.any():
                out[sel] = rng.multivariate_normal(self.means[k], self.covs[k], size=sel.sum(),
                                                   method="cholesky")
        return out

    def _step(self, states, rng):
        cum = np.cumsum(self.transition[states], axis=1)
        return (rng.random(len(states))[:, None] > cum).sum(axis=1).clip(max=len(self.weights) - 1)

    def sample_daily(self, n, rng):
        states = rng.choice(len(self.weights), size=n, p=self.weights)
        return self._draw(states, rng)

    def sample_terminal(self, n, days, rng):
        states = rng.choice(len(self.weights), size=n, p=self.weights)
        out = np.zeros((n, self.means.shape[1]))
        for _ in range(days):
            out += self._draw(states, rng)
            states = self._step(states, rng)
        return out

    def sample_paths(self, n, days, rng):
        states = rng.choice(len(self.weights), size=n, p=self.weights)
        steps = []
        for _ in range(days):
            steps.append(self._draw(states, rng))
            states = self._step(states, rng)
        return np.cumsum(np.stack(steps, axis=1), axis=1)

    def daily_moments(self):
        w = self.weights
        mu = w @ self.means
        cov = sum(w[k] * (self.covs[k] + np.outer(self.means[k] - mu, self.means[k] - mu))
                  for k in range(len(w)))
        return mu, cov

    def subset(self, tickers):
        ix = self._idx(tickers)
        return RegimeModel(self.weights, self.means[:, ix], self.covs[:, ix][:, :, ix],
                           self.transition, list(tickers))


@dataclass
class BootstrapModel(ReturnModel):
    history: np.ndarray  # (T, m) daily log returns
    tickers: list[str]

    def sample_daily(self, n, rng):
        return self.history[rng.integers(0, len(self.history), size=n)]

    def daily_moments(self):
        return self.history.mean(0), np.cov(self.history, rowvar=False)

    def subset(self, tickers):
        return BootstrapModel(self.history[:, self._idx(tickers)], list(tickers))


# ----------------------------------------------------------------------------- learning
@dataclass
class GMMFit:
    weights: np.ndarray
    means: np.ndarray
    covs: np.ndarray
    loglik: float
    bic: float
    resp: np.ndarray  # (T, k) posterior regime probabilities
    transition: np.ndarray | None = None


def _logpdf(X, mean, cov):
    m = X.shape[1]
    L = np.linalg.cholesky(cov)
    z = np.linalg.solve(L, (X - mean).T)
    return -0.5 * (z**2).sum(0) - np.log(np.diag(L)).sum() - 0.5 * m * np.log(2 * np.pi)


def fit_gmm(X: np.ndarray, k: int, rng: np.random.Generator, iters=300, tol=1e-7,
            reg=1e-8) -> GMMFit:
    """Full-covariance Gaussian mixture by EM (k-means++ style init)."""
    T, m = X.shape
    centers = [X[rng.integers(T)]]
    for _ in range(1, k):
        d2 = np.min([((X - c) ** 2).sum(1) for c in centers], axis=0)
        centers.append(X[rng.choice(T, p=d2 / d2.sum())])
    means = np.array(centers)
    base = np.cov(X, rowvar=False) + reg * np.eye(m)
    covs = np.repeat(base[None], k, axis=0)
    weights = np.full(k, 1 / k)
    prev = -np.inf
    for _ in range(iters):
        logp = np.stack([np.log(weights[j]) + _logpdf(X, means[j], covs[j]) for j in range(k)], 1)
        mx = logp.max(1, keepdims=True)
        ll_rows = mx[:, 0] + np.log(np.exp(logp - mx).sum(1))
        resp = np.exp(logp - ll_rows[:, None])
        ll = ll_rows.sum()
        nk = resp.sum(0) + 1e-12
        weights = nk / T
        means = (resp.T @ X) / nk[:, None]
        for j in range(k):
            d = X - means[j]
            covs[j] = (resp[:, j, None] * d).T @ d / nk[j] + reg * np.eye(m)
        if ll - prev < tol * abs(ll):
            break
        prev = ll
    n_params = (k - 1) + k * m + k * m * (m + 1) / 2
    return GMMFit(weights, means, covs, ll, -2 * ll + n_params * np.log(T), resp)


def fit_hmm(X: np.ndarray, init: GMMFit, iters=100, tol=1e-7, reg=1e-8) -> GMMFit:
    """Gaussian HMM by Baum-Welch (scaled forward-backward), initialised from a GMM.

    Returns a GMMFit whose ``transition`` attribute holds the learned Markov matrix and whose
    BIC counts the extra k(k-1) transition parameters.
    """
    T, m = X.shape
    k = len(init.weights)
    pi, means, covs = init.weights.copy(), init.means.copy(), init.covs.copy()
    A = np.full((k, k), 0.1 / max(k - 1, 1)) + np.eye(k) * (0.9 - 0.1 / max(k - 1, 1))
    if k == 1:
        A = np.ones((1, 1))
    prev = -np.inf
    for _ in range(iters):
        logb = np.stack([_logpdf(X, means[j], covs[j]) for j in range(k)], 1)
        mx = logb.max(1, keepdims=True)
        B = np.exp(logb - mx)
        alpha = np.empty((T, k))
        c = np.empty(T)
        a = pi * B[0]
        c[0] = a.sum()
        alpha[0] = a / c[0]
        for t in range(1, T):
            a = (alpha[t - 1] @ A) * B[t]
            c[t] = a.sum()
            alpha[t] = a / c[t]
        beta = np.ones((T, k))
        for t in range(T - 2, -1, -1):
            beta[t] = A @ (B[t + 1] * beta[t + 1]) / c[t + 1]
        gamma = alpha * beta
        gamma /= gamma.sum(1, keepdims=True)
        xi = (alpha[:-1, :, None] * A[None] * (B[1:] * beta[1:])[:, None, :]
              / c[1:, None, None])
        ll = np.log(c).sum() + mx.sum()
        pi = gamma[0] + 1e-12
        pi /= pi.sum()
        A = xi.sum(0) + 1e-6
        A /= A.sum(1, keepdims=True)
        nk = gamma.sum(0) + 1e-12
        means = (gamma.T @ X) / nk[:, None]
        for j in range(k):
            d = X - means[j]
            covs[j] = (gamma[:, j, None] * d).T @ d / nk[j] + reg * np.eye(m)
        if ll - prev < tol * abs(ll):
            break
        prev = ll
    n_params = (k - 1) + k * (k - 1) + k * m + k * m * (m + 1) / 2
    fit = GMMFit(nk / T, means, covs, ll, -2 * ll + n_params * np.log(T), gamma)
    fit.transition = A
    return fit


def fit_regime_model(history: pd.DataFrame, k_max=4, restarts=3, seed=0,
                     verbose=False) -> tuple[RegimeModel, list[GMMFit]]:
    """Learn F from daily log returns: Gaussian HMM for k = 1..k_max, pick k by BIC.

    Each k starts from the best of ``restarts`` EM-fitted Gaussian mixtures, then Baum-Welch
    learns the regime-switching matrix jointly with the emissions. (Counting transitions
    from hard mixture labels instead underestimates persistence badly: calm-looking crisis
    days get relabelled and break the runs.)
    """
    X = history.to_numpy()
    rng = np.random.default_rng(seed)
    fits = []
    for k in range(1, k_max + 1):
        gmm = min((fit_gmm(X, k, rng) for _ in range(restarts)), key=lambda f: f.bic)
        best = fit_hmm(X, gmm)
        fits.append(best)
        if verbose:
            print(f"  k={k}: loglik={best.loglik:,.0f}  BIC={best.bic:,.0f}")
    best = min(fits, key=lambda f: f.bic)
    # order regimes by volatility so regime 0 is always the calm one
    order = np.argsort([np.trace(c) for c in best.covs])
    P = best.transition[np.ix_(order, order)]
    # stationary distribution of P as the starting mix
    w, v = np.linalg.eig(P.T)
    stat = np.real(v[:, np.argmin(np.abs(w - 1))])
    stat = stat / stat.sum()
    model = RegimeModel(stat, best.means[order], best.covs[order], P, list(history.columns))
    return model, fits


def prices_to_log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return np.log(prices).diff().dropna(how="any")
