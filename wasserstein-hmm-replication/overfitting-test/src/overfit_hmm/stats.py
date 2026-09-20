"""PURPOSE: statistical comparison of blocked-CV vs. baseline order selection across seeds.
INPUTS: results/multiseed/seed_*.csv from multiseed.py.
OUTPUTS: results/multiseed_stats.json and results/multiseed.png.

Two different sources of randomness, two tests:
  A. Seed noise (HMM initialization + random block layout): paired tests across seeds on the
     per-seed Sharpe difference. Answers "is the effect robust to the algorithm's own luck?".
  B. Market-sample noise (only one 2019-2026 history exists): a paired circular block
     bootstrap over days on the seed-averaged return difference. Answers "could the gap be
     a fluke of this particular history?".
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from .config import ROOT  # noqa: E402

RESULTS = ROOT / "results"
ANN = np.sqrt(252)


def sharpe(r: np.ndarray) -> float:
    return float(ANN * r.mean() / r.std(ddof=1))


def max_drawdown(r: np.ndarray) -> float:
    wealth = np.cumprod(1 + r)
    return float((wealth / np.maximum.accumulate(wealth) - 1).min())


def block_bootstrap_diff(
    a: np.ndarray, b: np.ndarray, block: int, draws: int, rng: np.random.Generator,
) -> np.ndarray:
    """Paired circular block bootstrap of Sharpe(b) - Sharpe(a): same resampled days for both."""
    n = len(a)
    n_blocks = int(np.ceil(n / block))
    out = np.empty(draws)
    for i in range(draws):
        starts = rng.integers(0, n, n_blocks)
        idx = ((starts[:, None] + np.arange(block)) % n).ravel()[:n]
        out[i] = sharpe(b[idx]) - sharpe(a[idx])
    return out


def main() -> None:
    files = sorted((RESULTS / "multiseed").glob("seed_*.csv"))
    runs = {int(f.stem.split("_")[1]): pd.read_csv(f, index_col=0, parse_dates=True) for f in files}
    per_seed = pd.DataFrame({
        s: {
            "sharpe_base": sharpe(r.baseline_ret.to_numpy()),
            "sharpe_blocked": sharpe(r.blocked_ret.to_numpy()),
            "mdd_base": max_drawdown(r.baseline_ret.to_numpy()),
            "mdd_blocked": max_drawdown(r.blocked_ret.to_numpy()),
            "turn_base": r.baseline_turnover.mean(), "turn_blocked": r.blocked_turnover.mean(),
            "k_switches_base": int((r.baseline_k.diff().abs() > 0).sum()),
            "k_switches_blocked": int((r.blocked_k.diff().abs() > 0).sum()),
            "k_mean_base": r.baseline_k.mean(), "k_mean_blocked": r.blocked_k.mean(),
        } for s, r in runs.items()
    }).T
    per_seed["d_sharpe"] = per_seed.sharpe_blocked - per_seed.sharpe_base
    d = per_seed.d_sharpe.to_numpy()

    # A. across seeds
    t_stat, t_p = stats.ttest_1samp(d, 0.0)
    w_stat, w_p = stats.wilcoxon(d)
    sem = d.std(ddof=1) / np.sqrt(len(d))
    across = {
        "n_seeds": len(d), "mean_d_sharpe": float(d.mean()), "std_d_sharpe": float(d.std(ddof=1)),
        "ci95_mean": [float(d.mean() - stats.t.ppf(0.975, len(d) - 1) * sem),
                      float(d.mean() + stats.t.ppf(0.975, len(d) - 1) * sem)],
        "share_seeds_blocked_better": float((d > 0).mean()),
        "paired_t": {"t": float(t_stat), "p": float(t_p)},
        "wilcoxon": {"stat": float(w_stat), "p": float(w_p)},
    }

    # B. over the market sample: ensemble-average the seeds, then bootstrap days
    base_idx = next(iter(runs.values())).index
    base = np.mean([r.baseline_ret.to_numpy() for r in runs.values()], axis=0)
    blocked = np.mean([r.blocked_ret.to_numpy() for r in runs.values()], axis=0)
    rng = np.random.default_rng(0)
    point = sharpe(blocked) - sharpe(base)
    boot = {}
    for block in (10, 20, 60):
        draws = block_bootstrap_diff(base, blocked, block, 4000, rng)
        centered = draws - draws.mean()
        boot[f"block_{block}"] = {
            "ci95": [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))],
            "p_two_sided": float(np.mean(np.abs(centered) >= abs(point))),
        }
    bootstrap = {"ensemble_sharpe_base": sharpe(base), "ensemble_sharpe_blocked": sharpe(blocked),
                 "point_diff": point, **boot}

    # C. where the gain comes from: ensemble Sharpe by year, paired-over-seeds test by period
    by_year = {}
    for year in sorted(set(base_idx.year)):
        mask = base_idx.year == year
        by_year[str(year)] = {"baseline": sharpe(base[mask]), "blocked": sharpe(blocked[mask])}
    by_period = {}
    for name, (lo, hi) in {"2019_2022": (2019, 2022), "2023_2026": (2023, 2026)}.items():
        diffs = np.array([
            sharpe(r.blocked_ret[(r.index.year >= lo) & (r.index.year <= hi)].to_numpy())
            - sharpe(r.baseline_ret[(r.index.year >= lo) & (r.index.year <= hi)].to_numpy())
            for r in runs.values()
        ])
        by_period[name] = {
            "mean_d_sharpe": float(diffs.mean()), "share_seeds_blocked_better": float((diffs > 0).mean()),
            "paired_t": float(diffs.mean() / (diffs.std(ddof=1) / np.sqrt(len(diffs)))),
        }
    summary = {
        "per_seed_means": per_seed.mean().to_dict(),
        "per_seed_extremes": {
            "sharpe_base_min": float(per_seed.sharpe_base.min()),
            "sharpe_base_max": float(per_seed.sharpe_base.max()),
            "d_sharpe_min": float(d.min()), "d_sharpe_max": float(d.max()),
        },
        "sample": {"oos_start": str(base_idx[0].date()), "oos_end": str(base_idx[-1].date()),
                   "oos_observations": len(base_idx)},
        "across_seeds": across, "market_bootstrap": bootstrap,
        "by_year_ensemble_sharpe": by_year, "by_period_across_seeds": by_period,
    }
    (RESULTS / "multiseed_stats.json").write_text(json.dumps(summary, indent=2, default=float) + "\n")
    per_seed.to_csv(RESULTS / "multiseed_per_seed.csv", index_label="seed")

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].boxplot([per_seed.sharpe_base, per_seed.sharpe_blocked], tick_labels=["baseline", "blocked CV"])
    for _, row in per_seed.iterrows():
        ax[0].plot([1, 2], [row.sharpe_base, row.sharpe_blocked], color="grey", alpha=0.3)
    ax[0].set_ylabel("Sharpe (2019-2026, gross)")
    ax[1].hist(d, bins=12)
    ax[1].axvline(0, color="k")
    ax[1].set_xlabel("blocked minus baseline Sharpe, per seed")
    fig.tight_layout()
    fig.savefig(RESULTS / "multiseed.png", dpi=130)
    print(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
