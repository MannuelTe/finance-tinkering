"""Turn the sweep logs into the tables and figures of FINDINGS.md.

    python -m ptune.analyze
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew, spearmanr

from .grid import BASE, GRID, key

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results"
FIG = ROOT / "figures"
PUBLISHED = {"sharpe": 2.18, "max_drawdown": -0.0543, "turnover": 0.0079}
KNN_PUBLISHED = {"sharpe": 1.81, "max_drawdown": -0.1252, "turnover": 0.5665}
MATCH = {"turnover": (0.0059, 0.0099), "max_drawdown": (-0.065, -0.043)}

# Reference palette (light mode), as elsewhere in the repo.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRIDC, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


def style():
    plt.rcParams.update({
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 9, "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 8,
        "ytick.labelsize": 8, "axes.grid": True, "grid.color": GRIDC, "grid.linewidth": 0.6,
        "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "legend.fontsize": 8,
        "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    })


def load_log() -> pd.DataFrame:
    rows = [json.loads(line) for line in (RES / "runs.jsonl").read_text().splitlines()]
    df = pd.DataFrame(rows).drop_duplicates("key", keep="last")
    t = pd.json_normalize(df["task"])
    t.columns = [c.replace("params.", "p.") for c in t.columns]
    return pd.concat([df.drop(columns="task").reset_index(drop=True), t], axis=1)


def daily(k: str) -> pd.DataFrame:
    return pd.read_csv(RES / "runs" / f"{k}.csv", index_col=0, parse_dates=True)


# ------------------------------------------------------------------ statistics
def sharpe(r: pd.Series, rf: pd.Series | None = None) -> float:
    x = r - (rf.reindex(r.index).fillna(0) if rf is not None else 0)
    return float(np.sqrt(252) * x.mean() / x.std(ddof=1))


def max_dd(r: pd.Series) -> float:
    w = (1 + r).cumprod()
    return float((w / w.cummax() - 1).min())


def deflated_sharpe(best: pd.Series, trial_sharpes_annual: np.ndarray) -> float:
    """Bailey & Lopez de Prado (2014): probability that the best of N trials has a true
    Sharpe above zero, after allowing for the maximum of N noisy Sharpes."""
    n = len(trial_sharpes_annual)
    t = len(best)
    sr = best.mean() / best.std(ddof=1)                     # per-day Sharpe of the chosen run
    var_sr = np.var(np.asarray(trial_sharpes_annual) / np.sqrt(252), ddof=1)
    g = 0.5772156649
    sr0 = np.sqrt(var_sr) * ((1 - g) * norm.ppf(1 - 1 / n) + g * norm.ppf(1 - 1 / (n * np.e)))
    g3, g4 = skew(best), kurtosis(best, fisher=False)
    z = (sr - sr0) * np.sqrt(t - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)
    return float(norm.cdf(z))


def lagged(frame: pd.DataFrame, asset_returns: pd.DataFrame) -> pd.Series:
    """Fill-timing variant: weights decided for day t earn day t+1's return."""
    w = frame.filter(like="w_").rename(columns=lambda c: c[2:])
    r = asset_returns.reindex(w.index)
    return (w.shift(1) * r[w.columns]).sum(axis=1).iloc[1:]


# ------------------------------------------------------------------ sections
def seed_spread(log):
    b = log[(log.tag == "baseline")]
    return b[["seed", "sharpe", "max_drawdown", "turnover"]].sort_values("seed")


def oat_table(log):
    base = log[log.tag == "baseline"]
    rows = [{"parameter": "(baseline, 20 seeds)", "value": "replication",
             "sharpe": base.sharpe.mean(), "sharpe_sd": base.sharpe.std(),
             "max_drawdown": base.max_drawdown.mean(), "turnover": base.turnover.mean(), "n": len(base)}]
    b5 = base[base.seed.isin([1, 2, 3, 4, 5])]
    for name in GRID:
        sub = log[log.tag == f"oat:{name}"]
        for v in GRID[name]:
            if v == BASE[name]:
                g = b5
            else:
                g = sub[sub[f"p.{name}"].apply(lambda x: x == v or (isinstance(x, list) and tuple(x) == v))]
            if g.empty:
                continue
            rows.append({"parameter": name, "value": str(v) + (" (repl.)" if v == BASE[name] else ""),
                         "sharpe": g.sharpe.mean(), "sharpe_sd": g.sharpe.std(),
                         "max_drawdown": g.max_drawdown.mean(), "turnover": g.turnover.mean(),
                         "n": len(g)})
    return pd.DataFrame(rows)


def joint(log):
    j = log[log.tag.str.startswith("joint:")].copy()
    j["draw"] = j.tag.str.split(":").str[1].astype(int)
    o = j[j.window == "oos"].set_index("draw")
    t = j[j.window == "tune"].set_index("draw")
    both = o[["key", "sharpe", "max_drawdown", "turnover"]].join(
        t[["sharpe", "max_drawdown", "turnover"]], rsuffix="_tune", how="inner")
    params = o[[c for c in o.columns if c.startswith("p.")]]
    return both.join(params), o


def knn_table(log):
    k = log[log.tag.str.startswith("knn:")].copy()
    k["parameter"] = k.tag.str.split(":").str[1]
    vals = []
    for _, r in k.iterrows():
        name = r["parameter"]
        vals.append("replication" if name == "baseline" else str(r.get(f"p.{name}")))
    k["value"] = vals
    return k[["parameter", "value", "sharpe", "max_drawdown", "turnover"]]


# ------------------------------------------------------------------ figures
def fig_oat(tab, base_sd, out):
    style()
    t = tab[tab.parameter != "(baseline, 20 seeds)"]
    params = list(dict.fromkeys(t.parameter))
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(params) + 1))
    b = tab.iloc[0]
    ax.axvspan(b.sharpe - 2 * base_sd / np.sqrt(5), b.sharpe + 2 * base_sd / np.sqrt(5),
               color=MUTED, alpha=0.15, lw=0, label="baseline ± 2 s.e. (5-seed mean)")
    ax.axvline(b.sharpe, color=MUTED, lw=1)
    ax.axvline(PUBLISHED["sharpe"], color=ORANGE, lw=1.5, ls="--", label="published 2.18")
    for i, p in enumerate(params):
        g = t[t.parameter == p]
        ax.plot([g.sharpe.min(), g.sharpe.max()], [i, i], color=AXIS, lw=2, zorder=1)
        repl = g[g.value.str.endswith("(repl.)")]
        other = g[~g.value.str.endswith("(repl.)")]
        ax.scatter(other.sharpe, [i] * len(other), color=BLUE, s=28, zorder=2)
        ax.scatter(repl.sharpe, [i] * len(repl), color=INK, s=28, marker="D", zorder=3)
        best = g.loc[g.sharpe.idxmax()]
        ax.annotate(best.value.replace(" (repl.)", ""), (best.sharpe, i), xytext=(5, 0),
                    textcoords="offset points", va="center", fontsize=7, color=INK2)
    ax.set_yticks(range(len(params)), params)
    ax.invert_yaxis()
    ax.set_xlabel("Test-window Sharpe, mean of 5 seeds (dots: grid values; diamond: replication value; label: best value)")
    ax.set_title("One parameter at a time")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def fig_joint(both, out):
    style()
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.8))
    a.hist(both.sharpe, bins=30, color=BLUE, alpha=0.8, edgecolor="white")
    for v, c, lab in ((PUBLISHED["sharpe"], ORANGE, "published HMM 2.18"),
                      (1.59, INK, "replication 1.59"), (1.68, MUTED, "equal weight 1.68")):
        a.axvline(v, color=c, lw=1.5, ls="--", label=lab)
    lo, hi = np.percentile(both.sharpe, [5, 95])
    a.axvspan(lo, hi, color=BLUE, alpha=0.08, lw=0)
    a.set_title(f"200 joint draws: test-window Sharpe (90% range {lo:.2f} to {hi:.2f})")
    a.set_xlabel("Sharpe (gross, no risk-free)")
    a.legend(loc="upper left")
    rho = spearmanr(both.sharpe_tune, both.sharpe).statistic
    b.scatter(both.sharpe_tune, both.sharpe, s=14, color=BLUE, alpha=0.7, lw=0)
    b.set_xlabel("Sharpe on the tuning window (2019 to May 2023)")
    b.set_ylabel("Sharpe on the test window (June 2023 to 2026)")
    b.set_title(f"Does tuning carry over? Spearman ρ = {rho:.2f}")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main():
    FIG.mkdir(exist_ok=True)
    log = load_log()
    out = {}
    seeds = seed_spread(log)
    out["baseline_seeds"] = seeds.describe().to_dict()
    tab = oat_table(log)
    out["oat"] = tab.to_dict("records")
    fig_oat(tab, seeds.sharpe.std(), FIG / "oat.png")
    both, oos = joint(log)
    if len(both):
        r1 = {m: dict(zip(["p5", "p50", "p95"], np.percentile(both[m], [5, 50, 95]).tolist()))
              for m in ("sharpe", "max_drawdown", "turnover")}
        r1["share_sharpe_ge_2.18"] = float((both.sharpe >= 2.18).mean())
        r1["max_sharpe"] = float(both.sharpe.max())
        r1["n"] = len(both)
        out["R1"] = r1
        m = both[both.turnover.between(*MATCH["turnover"]) & both.max_drawdown.between(*MATCH["max_drawdown"])]
        out["R2"] = {"n_match": len(m), "sharpe": m.sharpe.describe().to_dict(),
                     "draws": m.drop(columns=["key"]).reset_index().to_dict("records")}
        pick = both.sharpe_tune.idxmax()
        chosen = both.loc[pick]
        out["R3"] = {"draw": int(pick), "tune_sharpe": float(chosen.sharpe_tune),
                     "oos_sharpe": float(chosen.sharpe), "oos_mdd": float(chosen.max_drawdown),
                     "oos_turnover": float(chosen.turnover),
                     "params": {c[2:]: chosen[c] for c in both.columns if c.startswith("p.")},
                     "spearman_tune_vs_oos": float(spearmanr(both.sharpe_tune, both.sharpe).statistic)}
        best = both.sharpe.idxmax()
        out["best_oos_draw"] = {"draw": int(best), "sharpe": float(both.loc[best].sharpe),
                                "deflated_sharpe_prob": deflated_sharpe(
                                    daily(both.loc[best].key)["gross"], both.sharpe.to_numpy()),
                                "params": {c[2:]: both.loc[best][c] for c in both.columns if c.startswith("p.")}}
        fig_joint(both, FIG / "joint.png")
        both.drop(columns=["key"]).to_csv(RES / "joint_draws.csv")
    out["knn"] = knn_table(log).to_dict("records")
    (RES / "analysis.json").write_text(json.dumps(out, indent=1, default=str))
    pd.set_option("display.width", 200, "display.float_format", "{:.4f}".format)
    print(seeds.describe().loc[["mean", "std", "min", "max"]])
    print(tab.to_string(index=False))
    for k in ("R1", "R3", "best_oos_draw"):
        print(k, json.dumps(out.get(k), indent=1, default=str)[:1500])
    if "R2" in out:
        print("R2 matches:", out["R2"]["n_match"], out["R2"]["sharpe"])
    print(knn_table(log).to_string(index=False))


if __name__ == "__main__":
    main()
