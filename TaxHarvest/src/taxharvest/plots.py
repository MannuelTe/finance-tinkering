"""Matplotlib figures and GIF animations for a harvest plan."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.ticker import FuncFormatter, PercentFormatter

from .engine import HarvestPlan
from .robustness import wilson

# Reference palette (light mode): categorical slots 1-3, status, ink and chrome.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE_LIGHT = "#9ec5f4"


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 9, "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.spines.top": False,
        "axes.spines.right": False, "legend.frameon": False, "legend.fontsize": 8,
        "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "text.color": INK, "lines.linewidth": 2,
    })


def money(cur=""):
    def f(v, _=None):
        a = abs(v)
        s = f"{a / 1e6:.1f}M" if a >= 1e6 else f"{a / 1e3:.0f}k" if a >= 1e4 else (
            f"{a / 1e3:.1f}k" if a >= 1e3 else f"{a:.0f}")
        return ("-" if v < 0 else "") + cur + s
    return FuncFormatter(f)


def _cur(plan):
    return plan.problem.rules.symbol


def _short(reason: str) -> str:
    r = reason.split(";")[0]
    if r.startswith("sheltered"):
        return "sheltered acct"
    if r.startswith("DRIP"):
        return "DRIP on"
    if r.startswith("planned buy"):
        return "planned buy in window"
    if "bought" in r:
        return "recent buy in window"
    return r[:24]


def _hist(ax, data, color, label, bins, alpha=0.85):
    ax.hist(data, bins=bins, color=color, alpha=alpha, label=label, edgecolor=SURFACE,
            linewidth=0.6)


# ----------------------------------------------------------------------------- static
def plan_overview(plan: HarvestPlan, path: Path, title: str = ""):
    style()
    cur = _cur(plan)
    df = plan.trades()
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 0.32 * len(df) + 2.6),
                               gridspec_kw={"width_ratios": [1.15, 1]})
    y = np.arange(len(df))[::-1]
    full = plan.lot_losses.mean(1)
    # show the *unscreened* expected loss for blocked lots so the user sees what the rule costs
    raw = [plan.lot_losses[i].mean() if st.eligible else _raw_expected(plan, i)
           for i, st in enumerate(plan.status)]
    for yi, (_, r), rv, fv in zip(y, df.iterrows(), raw, full):
        if r.eligible:
            a.barh(yi, fv, color=BLUE_LIGHT, height=0.62)
            a.barh(yi, r["E[loss]"], color=BLUE, height=0.62)
        else:
            a.barh(yi, rv, color="none", edgecolor=MUTED, hatch="////", height=0.62, lw=0.6)
            a.text(rv + full.max() * 0.02, yi, _short(r.why_not), va="center", fontsize=7,
                   color=CRITICAL)
    a.set_yticks(y, _lot_labels(plan), fontsize=8)
    a.xaxis.set_major_formatter(money(cur))
    a.set_xlabel("expected loss at harvest date if the whole lot is sold")
    a.grid(axis="y", visible=False)
    a.set_title("Candidate lots and expected actual sales")
    from matplotlib.patches import Patch
    a.legend(handles=[Patch(color=BLUE, label="expected loss actually realized"),
                      Patch(color=BLUE_LIGHT, label="eligible loss capacity"),
                      Patch(facecolor="none", edgecolor=MUTED, hatch="////",
                            label="blocked by wash-sale / superficial-loss screen")],
             loc="lower right")

    L, K = plan.losses, plan.loss_target
    bins = np.linspace(0, np.quantile(L, 0.995) * 1.05 + 1, 60)
    _hist(b, L[L < K], ORANGE, f"L < K  ({np.mean(L < K):.1%})", bins)
    _hist(b, L[L >= K], BLUE, f"L ≥ K  ({np.mean(L >= K):.1%})", bins)
    b.axvline(K, color=INK, lw=1.5)
    b.axvline(L.mean(), color=INK2, lw=1.2, ls="--")
    ymax = b.get_ylim()[1]
    b.text(K, ymax * 0.97, f"loss needed = {cur}{K:,.0f} ", fontsize=8, va="top", ha="right",
           color=INK)
    b.text(L.mean(), ymax * 0.97, f" E[capacity] = {cur}{L.mean():,.0f}", fontsize=8, va="top",
           color=INK2)
    b.xaxis.set_major_formatter(money(cur))
    b.set_xlabel("potential loss from selected lots before the execution cap")
    b.set_ylabel("scenarios")
    b.set_title(f"Tax-saving goal: P(save ≥ goal) = {plan.confidence:.1%} "
                f"(target {plan.problem.confidence:.0%})")
    b.legend(loc="upper left", bbox_to_anchor=(0, 0.88))
    if title:
        fig.suptitle(title, x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _lot_labels(plan) -> list[str]:
    """'TICKER  account', plus the purchase month where a ticker/account pair repeats."""
    lots = plan.problem.portfolio.lots
    keys = [(lot.ticker, lot.account) for lot in lots]
    return [f"{lot.ticker}  {lot.account}" + (f"  {lot.acquired:%Y-%m}" if keys.count(k) > 1 else "")
            for lot, k in zip(lots, keys)]


def _raw_expected(plan, i):
    lot = plan.problem.portfolio.lots[i]
    if not hasattr(plan, "_raw_cache"):
        from .engine import simulate
        plan._raw_cache = simulate(plan.problem, n=4000,
                                   rng=np.random.default_rng(0)).raw_losses.mean(1)
    return plan._raw_cache[i] if lot.taxable else max(-lot.unrealized, 0)


def tax_impact(plan: HarvestPlan, path: Path):
    style()
    cur = _cur(plan)
    before = plan.problem.tax_rate * np.clip(plan.gains, 0, None)
    saved = plan.tax_savings
    after = before - saved
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(14, 4))
    a.bar(["No harvest", "With plan"], [before.mean(), after.mean()],
          color=[MUTED, BLUE], width=0.5)
    for i, amount in enumerate((before.mean(), after.mean())):
        a.text(i, amount, f"{cur}{amount:,.0f}", ha="center", va="bottom", fontsize=9)
    a.set_ylim(0, max(before.mean(), 1) * 1.2)
    a.set_title("Expected capital-gains tax due")
    a.yaxis.set_major_formatter(money(cur))
    a.grid(axis="x", visible=False)

    bins = np.linspace(0, max(plan.target, float(saved.max()), 1) * 1.05, 50)
    b.hist(saved, bins=bins, weights=np.full(len(saved), 100 / len(saved)), color=AQUA,
           edgecolor=SURFACE, linewidth=0.5)
    b.axvline(plan.target, color=INK, lw=1.2, ls="--")
    b.set_xlabel("tax saved")
    b.set_ylabel("percent of scenarios")
    label_cur = cur.replace("$", r"\$")
    b.set_title(f"Tax-saving goal {label_cur}{plan.target:,.0f}; "
                f"E = {label_cur}{saved.mean():,.0f}")
    b.xaxis.set_major_formatter(money(cur))

    order = np.argsort(plan.port_pnl)
    pct = np.linspace(0, 100, len(order))
    c.plot(pct, _smooth(saved[order]), color=BLUE, label="tax saved")
    c.axhline(plan.target, color=INK, lw=1, ls="--", label="goal")
    c.set_xlabel("scenario percentile of P's horizon P&L (bad → good)")
    c.yaxis.set_major_formatter(money(cur))
    c.set_ylim(0, max(plan.target, float(saved.max()), 1) * 1.08)
    c.set_title("Tax savings across market outcomes")
    c.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _smooth(v, w=None):
    w = w or max(len(v) // 50, 1)
    k = np.ones(w) / w
    return np.convolve(np.pad(v, (w // 2, w - 1 - w // 2), mode="edge"), k, mode="valid")


def frontier(rows: list[dict], path: Path, cur="$", target_conf=None):
    style()
    alpha = np.array([r["alpha"] for r in rows])
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.8))
    series = [("sub-portfolio value", "Candidate pool at current prices", BLUE),
              ("E[loss realized]", "Expected loss actually realized", ORANGE),
              ("E[tax saved]", "Expected tax saved", AQUA)]
    for ax, (key, title, col) in zip(axes, series):
        ax.plot(alpha, [r[key] for r in rows], color=col, marker="o", ms=4)
        ax.set_title(title)
        ax.yaxis.set_major_formatter(money(cur))
        ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.set_xlabel("confidence P(tax saved ≥ goal)")
        if target_conf:
            ax.axvline(target_conf, color=MUTED, lw=1, ls=":")
    axes[1].axhline(rows[0]["loss needed for goal"], color=INK, lw=1, ls="--")
    axes[1].text(alpha[0], rows[0]["loss needed for goal"], " loss needed", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def robustness(rob: dict, path: Path, alpha: float):
    style()
    fig, ax = plt.subplots(2, 2, figsize=(13, 8.5))

    a = ax[0, 0]
    methods = list(rob["seeds"].keys())
    colors = [BLUE, ORANGE, AQUA, "#4a3aa7"]
    for k, m in enumerate(methods):
        v = np.array(rob["seeds"][m])
        jitter = np.random.default_rng(k).uniform(-0.15, 0.15, len(v))
        a.scatter(np.full(len(v), k) + jitter, v, s=14, color=colors[k], alpha=0.7)
        a.plot([k - 0.28, k + 0.28], [v.mean()] * 2, color=INK, lw=2)
        a.text(k + 0.3, v.mean(), f"{v.mean():.1%}", va="center", fontsize=8)
    a.axhline(alpha, color=CRITICAL, lw=1, ls="--")
    a.text(-0.45, alpha, f"target {alpha:.0%}", va="bottom", fontsize=8, color=CRITICAL)
    a.set_xticks(range(len(methods)), methods)
    a.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    a.set_ylabel("out-of-sample P(tax saved ≥ goal)")
    a.set_title(f"Re-optimised on {rob['n_seeds']} independent scenario sets")

    b = ax[0, 1]
    N = np.array(rob["convergence"]["N"])
    mu = np.array(rob["convergence"]["mean"])
    sd = np.array(rob["convergence"]["sd"])
    b.fill_between(N, mu - 2 * sd, mu + 2 * sd, color=BLUE_LIGHT, alpha=0.6, lw=0,
                   label="±2 sd across seeds")
    b.plot(N, mu, color=BLUE, marker="o", ms=4, label="mean")
    b.axhline(alpha, color=CRITICAL, lw=1, ls="--")
    b.set_xscale("log")
    b.yaxis.set_major_formatter(PercentFormatter(1, decimals=1))
    b.set_xlabel("scenarios used in the optimisation (N)")
    b.set_ylabel("out-of-sample P(tax saved ≥ goal)")
    b.set_title("Sample-average approximation converges in N")
    b.legend(loc="lower right")

    c = ax[1, 0]
    v = np.array(rob["param"])
    c.hist(v, bins=30, color=BLUE, edgecolor=SURFACE)
    c.axvline(alpha, color=CRITICAL, lw=1, ls="--")
    c.axvline(np.median(v), color=INK, lw=1.2)
    c.text(np.median(v), c.get_ylim()[1] * 0.95,
           f"  median {np.median(v):.1%}\n  P(conf ≥ {alpha - 0.05:.0%}) = "
           f"{np.mean(v >= alpha - 0.05):.0%}", va="top", fontsize=8)
    c.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    c.set_xlabel("P(tax saved ≥ goal) when the true μ, Σ differ from the estimates")
    c.set_ylabel("parameter draws")
    c.set_title(f"Estimation error: μ, Σ drawn from {rob['est_years']}y sampling distribution")

    d = ax[1, 1]
    names = list(rob["misspec"].keys())
    vals = [rob["misspec"][n]["confidence"] for n in names]
    lo = [rob["misspec"][n]["ci"][0] for n in names]
    hi = [rob["misspec"][n]["ci"][1] for n in names]
    yy = np.arange(len(names))[::-1]
    d.barh(yy, vals, color=[BLUE] + [ORANGE] * (len(names) - 1), height=0.55)
    d.errorbar(vals, yy, xerr=[np.array(vals) - lo, np.array(hi) - vals], fmt="none",
               ecolor=INK, capsize=3, lw=1)
    for yi, v_ in zip(yy, vals):
        d.text(v_ + 0.01, yi + 0.3, f"{v_:.1%}", va="center", fontsize=8)
    d.axvline(alpha, color=CRITICAL, lw=1, ls="--")
    d.set_yticks(yy, names, fontsize=8)
    d.set_xlim(0, 1.08)
    d.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    d.set_xlabel("P(tax saved ≥ goal), 200k fresh scenarios, 95% Wilson CI")
    d.set_title("Plan built on the base model, tested under other F")
    d.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def learned_fit(history, fits, fitted, gauss, path: Path, weights):
    style()
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(14, 4))
    ks = np.arange(1, len(fits) + 1)
    bic = np.array([f.bic for f in fits])
    a.plot(ks, bic - bic.min(), color=BLUE, marker="o")
    a.set_xticks(ks)
    a.set_xlabel("number of regimes k")
    a.set_ylabel("BIC − min BIC")
    a.set_title(f"Model selection: k = {int(ks[bic.argmin()])} by BIC")

    r = history.to_numpy() @ weights
    rng = np.random.default_rng(3)
    sim_f = fitted.sample_daily(200_000, rng) @ weights
    sim_g = gauss.sample_daily(200_000, rng) @ weights
    bins = np.linspace(np.quantile(r, 0.001), np.quantile(r, 0.999), 80)
    b.hist(r, bins=bins, density=True, color=MUTED, alpha=0.5, label="history")
    for s, col, lab in [(sim_f, BLUE, "fitted regime model"), (sim_g, ORANGE, "Gaussian")]:
        h, e = np.histogram(s, bins=bins, density=True)
        b.plot(0.5 * (e[1:] + e[:-1]), h, color=col, label=lab)
    b.set_yscale("log")
    b.set_xlabel("daily portfolio log return")
    b.set_title("Daily returns of P (log density)")
    b.xaxis.set_major_formatter(PercentFormatter(1, decimals=1))
    b.legend()

    q = np.linspace(0.001, 0.1, 60)
    c.plot(q, np.quantile(r, q), color=MUTED, label="history")
    c.plot(q, np.quantile(sim_f, q), color=BLUE, label="fitted regime model")
    c.plot(q, np.quantile(sim_g, q), color=ORANGE, label="Gaussian")
    c.set_xscale("log")
    c.xaxis.set_major_formatter(PercentFormatter(1, decimals=1))
    c.yaxis.set_major_formatter(PercentFormatter(1, decimals=1))
    c.set_xlabel("tail probability")
    c.set_ylabel("daily return quantile")
    c.set_title("Left tail: the Gaussian is too thin")
    c.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------------- animations
def animate_loss_fan(plan: HarvestPlan, path: Path, n=3000, frames=None, seed=5):
    """Harvestable loss of S as the harvest date approaches: histogram + quantile fan."""
    style()
    cur = _cur(plan)
    pr = plan.problem
    p = pr.portfolio
    days = pr.horizon_days
    rng = np.random.default_rng(seed)
    paths = pr.model.sample_paths(n, days, rng)  # (n, days, m)
    col = {t: k for k, t in enumerate(pr.model.tickers)}
    idx = np.array([col[lot.ticker] for lot in p.lots])
    sh = np.array([lot.shares for lot in p.lots])
    bs = np.array([lot.cost_basis for lot in p.lots])
    p0 = np.array([lot.price for lot in p.lots])
    elig = np.array([s.eligible for s in plan.status], float)
    prices = p0[None, None] * np.exp(paths[:, :, idx])  # (n, days, lots)
    L = (np.clip(bs - prices, 0, None) * sh * elig * plan.x).sum(-1)  # (n, days)
    L0 = float((np.clip(bs - p0, 0, None) * sh * elig * plan.x).sum())
    L = np.hstack([np.full((n, 1), L0), L])
    t = np.arange(days + 1)
    qs = np.quantile(L, [0.05, 0.25, 0.5, 0.75, 0.95], axis=0)
    K = plan.loss_target
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw={"width_ratios": [1.3, 1]})
    hi = np.quantile(L, 0.995)
    bins = np.linspace(0, hi, 50)
    frames = frames or list(range(0, days + 1, max(days // 40, 1))) + [days] * 8

    def draw(k):
        a.clear(), b.clear()
        a.fill_between(t[:k + 1], qs[0, :k + 1], qs[4, :k + 1], color=BLUE_LIGHT, alpha=0.5,
                       lw=0, label="5–95%")
        a.fill_between(t[:k + 1], qs[1, :k + 1], qs[3, :k + 1], color=BLUE_LIGHT, lw=0,
                       label="25–75%")
        a.plot(t[:k + 1], qs[2, :k + 1], color=BLUE, label="median")
        for j in range(12):
            a.plot(t[:k + 1], L[j, :k + 1], color=MUTED, lw=0.6, alpha=0.6)
        a.axhline(K, color=INK, lw=1.2, ls="--")
        a.text(0.5, K, " loss needed", va="bottom", fontsize=8)
        a.set_xlim(0, days)
        a.set_ylim(0, hi)
        a.yaxis.set_major_formatter(money(cur))
        a.set_xlabel("trading days from today")
        a.set_title("Harvestable loss of S if sold on day t")
        a.legend(loc="upper left")
        Lk = L[:, k]
        b.hist(Lk[Lk < K], bins=bins, color=ORANGE, edgecolor=SURFACE, lw=0.5)
        b.hist(Lk[Lk >= K], bins=bins, color=BLUE, edgecolor=SURFACE, lw=0.5)
        b.axvline(K, color=INK, lw=1.2, ls="--")
        b.set_xlim(0, hi)
        b.set_ylim(0, n * 0.25)
        b.xaxis.set_major_formatter(money(cur))
        b.set_title(f"day {k}:  P(tax saved ≥ goal) = {np.mean(Lk >= K):.1%}")
        b.set_xlabel("loss L")
        fig.tight_layout()

    anim = FuncAnimation(fig, draw, frames=frames)
    anim.save(path, writer=PillowWriter(fps=8), dpi=80)
    plt.close(fig)


def animate_mc_convergence(plan: HarvestPlan, path: Path, total=100_000, seed=9):
    """Running Monte Carlo estimate of P(tax saved >= goal) with a Wilson band as samples accumulate."""
    from .engine import evaluate
    style()
    cur = _cur(plan)
    result = evaluate(plan, total, np.random.default_rng(seed))
    L = result["losses"]
    hit = (result["tax_savings"] >= plan.target).astype(float)
    ns = np.unique(np.geomspace(20, total, 45).astype(int))
    est = np.cumsum(hit)[ns - 1] / ns
    lo, hi = wilson(est, ns)
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.2))
    bins = np.linspace(0, np.quantile(L, 0.995), 50)
    frames = list(range(len(ns))) + [len(ns) - 1] * 8

    def draw(k):
        a.clear(), b.clear()
        a.fill_between(ns[:k + 1], lo[:k + 1], hi[:k + 1], color=BLUE_LIGHT, lw=0,
                       label="95% Wilson interval")
        a.plot(ns[:k + 1], est[:k + 1], color=BLUE, marker="o", ms=3, label="estimate")
        a.axhline(plan.problem.confidence, color=CRITICAL, lw=1, ls="--", label="target")
        a.set_xscale("log")
        a.set_xlim(15, total * 1.2)
        a.set_ylim(max(0, plan.problem.confidence - 0.3), 1.0)
        a.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        a.set_xlabel("fresh Monte Carlo scenarios")
        a.set_title(f"P(tax saved ≥ goal) = {est[k]:.2%}  [{lo[k]:.2%}, {hi[k]:.2%}]  n = {ns[k]:,}")
        a.legend(loc="lower right")
        s = L[:ns[k]]
        b.hist(s[s < plan.loss_target], bins=bins, color=ORANGE, edgecolor=SURFACE, lw=0.5)
        b.hist(s[s >= plan.loss_target], bins=bins, color=BLUE, edgecolor=SURFACE, lw=0.5)
        b.axvline(plan.loss_target, color=INK, lw=1.2, ls="--")
        b.xaxis.set_major_formatter(money(cur))
        b.set_title("Out-of-sample loss distribution")
        b.set_xlabel("loss L")
        fig.tight_layout()

    FuncAnimation(fig, draw, frames=frames).save(path, writer=PillowWriter(fps=7), dpi=80)
    plt.close(fig)


def animate_frontier(plans: list[HarvestPlan], path: Path):
    """How S changes as the required confidence rises."""
    style()
    cur = _cur(plans[0])
    tick = _lot_labels(plans[0])
    elig = np.array([s.eligible for s in plans[0].status])
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 0.26 * len(tick) + 2.5),
                               gridspec_kw={"width_ratios": [1, 1.2]})
    y = np.arange(len(tick))[::-1]
    hi = max(np.quantile(pl.losses, 0.995) for pl in plans) + 1
    bins = np.linspace(0, hi, 50)
    frames = list(range(len(plans))) + [len(plans) - 1] * 6

    def draw(k):
        pl = plans[k]
        a.clear(), b.clear()
        a.barh(y, np.where(elig, 1, 0), color=GRID, height=0.62)
        a.barh(y, pl.x, color=BLUE, height=0.62)
        a.set_yticks(y, tick, fontsize=7)
        a.set_xlim(0, 1)
        a.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        a.set_xlabel("fraction of lot in S")
        a.grid(axis="y", visible=False)
        a.set_title(f"confidence {pl.problem.confidence:.0%}: S = {cur}"
                    f"{pl.subportfolio_value:,.0f}")
        L = pl.losses
        b.hist(L[L < pl.loss_target], bins=bins, color=ORANGE, edgecolor=SURFACE, lw=0.5)
        b.hist(L[L >= pl.loss_target], bins=bins, color=BLUE, edgecolor=SURFACE, lw=0.5)
        b.axvline(pl.loss_target, color=INK, lw=1.2, ls="--")
        b.axvline(L.mean(), color=INK2, lw=1, ls=":")
        b.set_xlim(0, hi)
        b.xaxis.set_major_formatter(money(cur))
        b.set_title(f"P(tax saved ≥ goal) = {pl.confidence:.1%},  E[loss sold] = {cur}{pl.expected_loss:,.0f}")
        b.set_xlabel("loss L")
        fig.tight_layout()

    FuncAnimation(fig, draw, frames=frames).save(path, writer=PillowWriter(fps=4), dpi=80)
    plt.close(fig)



def nominal_vs_robust(nom: HarvestPlan, rob: HarvestPlan, mis_nom: dict, mis_rob: dict,
                      amb_names: list[str], path: Path):
    style()
    cur = _cur(nom)
    alpha = nom.problem.confidence
    names = list(mis_nom)
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 0.55 * len(names) + 2.2),
                               gridspec_kw={"width_ratios": [2.2, 1]})
    y = np.arange(len(names))[::-1]
    h = 0.36
    for off, mis, col, lab in [(h / 2, mis_nom, BLUE, "nominal plan"),
                               (-h / 2, mis_rob, ORANGE, "robust plan")]:
        v = np.array([mis[n]["confidence"] for n in names])
        a.barh(y + off, v, height=h - 0.04, color=col, label=lab)
        for yi, vi in zip(y + off, v):
            a.text(vi + 0.005, yi, f"{vi:.1%}", va="center", fontsize=7, color=INK2)
    a.axvline(alpha, color=CRITICAL, lw=1, ls="--")
    a.set_yticks(y, names, fontsize=8)
    a.set_xlim(max(0, min(min(m["confidence"] for m in mis_nom.values()) - 0.1, alpha - 0.2)),
               1.02)
    a.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    a.set_xlabel("out-of-sample P(tax saved ≥ goal)")
    a.grid(axis="y", visible=False)
    a.set_title("Confidence when F is not what the optimiser assumed")
    a.legend(loc="lower right")
    a.text(0.0, -0.12 - 0.02 * len(names),
           "robust plan's ambiguity set: " + ", ".join(amb_names), transform=a.transAxes,
           fontsize=7, color=MUTED)

    vals = [nom.subportfolio_value, rob.subportfolio_value]
    b.bar([0, 1], vals, color=[BLUE, ORANGE], width=0.55)
    for k, v in enumerate(vals):
        b.text(k, v, f"{cur}{v:,.0f}", ha="center", va="bottom", fontsize=8)
    b.set_xticks([0, 1], ["nominal", "robust"])
    b.yaxis.set_major_formatter(money(cur))
    b.set_title("Price of robustness: candidate pool")
    b.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def backtest(bt: dict, path: Path, cur="$", title: str = ""):
    """Rules on the same price paths: how often each meets the goal, how much it sells, and
    how many paths sell before the deadline."""
    style()
    days = bt["_meta"]["days"]
    order = ["one-shot", "daily", "weekly", "sell now"]

    def family(name):
        return next((f for f in order if name.startswith(f)), "sell now")

    rules = sorted(((k, v) for k, v in bt.items() if not k.startswith("_")),
                   key=lambda kv: (order.index(family(kv[0])), kv[0]))
    color = {"one-shot": ORANGE, "daily": BLUE, "weekly": AQUA, "sell now": MUTED}

    def label(name, r):
        every = r.get("every", 1)
        n = len(range(0, days, every)) + 1 if family(name) in ("daily", "weekly") else 1
        return f"{name}  ({n} review{'s' if n > 1 else ''})"

    y = np.arange(len(rules))[::-1]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(14, 0.42 * len(rules) + 2.4),
                                  gridspec_kw={"width_ratios": [1, 1, 1.25]})
    met = np.array([r["P(goal met)"] for _, r in rules])
    cols = [color[family(k)] for k, _ in rules]
    lo = min(met.min() - 0.02, 0.86)
    a.hlines(y, lo, met, color=GRID, lw=2, zorder=1)
    a.scatter(met, y, s=64, color=cols, edgecolor=SURFACE, linewidth=2, zorder=3)
    for yi, m in zip(y, met):
        a.text(m - 0.004, yi + 0.28, f"{m:.1%}", ha="right", fontsize=7.5, color=INK2)
    a.set_yticks(y, [label(k, r) for k, r in rules], fontsize=8.5)
    a.set_xlim(lo, 1.005)
    a.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    a.set_xlabel("share of paths that meet the goal")
    a.set_title("Goal met")
    a.grid(axis="y", visible=False)

    sold = [r["E[market value sold]"] for _, r in rules]
    b.barh(y, sold, color=cols, height=0.62)
    for yi, v in zip(y, sold):
        b.text(v, yi, f" {cur}{v / 1000:,.1f}k", va="center", fontsize=7.5, color=INK2)
    b.set_yticks(y, [])
    b.set_xlim(0, max(sold) * 1.18)
    b.xaxis.set_major_formatter(money(cur))
    b.set_xlabel("average market value sold and replaced")
    b.set_title("Turnover")
    b.grid(axis="y", visible=False)

    t = np.arange(days)
    for name, r in rules:
        f = family(name)
        if f not in ("daily", "weekly"):
            continue
        d = r["first_sale_day"]
        share = [np.mean((d >= 0) & (d <= k)) for k in t]
        c.step(t, share, where="post", color=color[f], lw=2,
               ls="-" if name.endswith("95%") else "--", label=name)
    c.set_xlim(0, days - 1)
    c.set_ylim(0, None)
    c.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    c.set_xlabel("trading days from today")
    c.set_ylabel("share of paths that have sold")
    c.set_title(f"Early sales (the rest sell on day {days})")
    c.legend(loc="upper left")
    if title:
        fig.suptitle(title, x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _story_path(weekly: dict, one_shot: dict, K: float, days: int) -> int:
    """A path where the one-shot plan misses and the review sells mid-way: the clearest story."""
    first = weekly["first_sale_day"]
    got = one_shot["trace"]["harvested"][:, -1]
    ok = np.flatnonzero((got < K - 1) & (first >= days // 4) & (first <= 3 * days // 4))
    if not len(ok):
        ok = np.flatnonzero(got < K - 1) if np.any(got < K - 1) else np.arange(len(got))
    return int(ok[np.argmin(got[ok])])


def animate_review_story(weekly: dict, one_shot: dict, K: float, days: int, path: Path,
                         cur="$", trigger=0.95, every=5):
    """One simulated path, day by day: the weekly review locks in, the one-shot plan misses."""
    style()
    i = _story_path(weekly, one_shot, K, days)
    wt, ot = weekly["trace"], one_shot["trace"]
    avail, locked = wt["available"][i], wt["harvested"][i]
    shot, wait = ot["available"][i], wt["wait"][i]
    sale = int(weekly["first_sale_day"][i])
    got = ot["harvested"][i, -1]
    t = np.arange(days + 1)
    reviews = [d for d in t if d % every == 0 or d == days]
    top = max(np.nanmax(avail), np.nanmax(shot), K) * 1.15
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw={"width_ratios": [1.6, 1]})
    frames = list(t) + [days] * 14

    def draw(k):
        a.clear(), b.clear()
        pre = t <= min(k, sale)
        a.plot(t[pre], avail[pre], color=BLUE, lw=2, label="loss available to sell (all eligible lots)")
        a.plot(t[:k + 1], shot[:k + 1], color=ORANGE, lw=2, label="loss in the one-shot plan's candidates")
        a.step(t[:k + 1], locked[:k + 1], where="post", color=AQUA, lw=2.5,
               label="loss locked in by the weekly review")
        a.axhline(K, color=INK, lw=1, ls="--")
        a.text(0.3, K, f" loss needed {cur}{K:,.0f}", va="bottom", fontsize=8, color=INK)
        for d in reviews:
            a.axvline(d, color=GRID, lw=0.8, zorder=0)
        if k >= sale:
            a.scatter([sale], [locked[sale]], s=70, color=AQUA, edgecolor=SURFACE, lw=2, zorder=4)
            a.annotate(f"sold on day {sale}", (sale, locked[sale]), xytext=(6, 8),
                       textcoords="offset points", fontsize=8, color=INK2)
        if k == days:
            a.scatter([days], [got], s=70, color=ORANGE, edgecolor=SURFACE, lw=2, zorder=4)
            a.annotate(f"one-shot plan sells {cur}{got:,.0f}\nand misses the goal", (days, got),
                       xytext=(-10, 22), textcoords="offset points", ha="right", fontsize=8,
                       color=INK2)
        a.set_xlim(0, days + 0.5)
        a.set_ylim(0, top)
        a.yaxis.set_major_formatter(money(cur))
        a.set_xlabel("trading days from today (grey lines: weekly reviews)")
        a.legend(loc="upper right", fontsize=8)

        seen = [d for d in reviews if d <= k and not np.isnan(wait[d])]
        b.axhline(trigger, color=INK, lw=1, ls="--")
        b.text(days, trigger, f"sell below {trigger:.0%} ", va="top", ha="right", fontsize=8,
               color=INK)
        if seen:
            v = wait[seen]
            b.plot(seen, v, color=MUTED, lw=1, zorder=1)
            b.scatter(seen, v, s=60, zorder=3, edgecolor=SURFACE, lw=2,
                      color=[AQUA if x < trigger else BLUE for x in v])
            for d, x in zip(seen, v):
                b.annotate("sell" if x < trigger else "hold", (d, x), xytext=(0, 8),
                           textcoords="offset points", ha="center", fontsize=7.5, color=INK2)
        b.set_xlim(-2, days + 1)
        b.set_ylim(min(0.5, np.nanmin(wait) - 0.05), 1.05)
        b.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        b.set_xlabel("review day")
        b.set_title("Chance that waiting to the deadline is enough")
        if k < sale:
            state = f"hold (P = {wait[max(seen)]:.0%})" if seen else "hold"
        elif k < days:
            state = f"sold on day {sale}, goal locked in"
        else:
            state = f"deadline: review met the goal, one-shot plan got {got / K:.0%} of it"
        a.set_title(f"Day {k}: {state}")
        fig.tight_layout()

    FuncAnimation(fig, draw, frames=frames).save(path, writer=PillowWriter(fps=5), dpi=80)
    plt.close(fig)


def animate_review_paths(weekly: dict, one_shot: dict, K: float, days: int, path: Path,
                         cur="$", trigger=0.95, n=60):
    """Many paths at once: where the weekly review locks in, and what the one-shot plan misses."""
    style()
    wt = weekly["trace"]
    avail = wt["available"][:n]
    first = weekly["first_sale_day"][:n]
    met = wt["harvested"][:n, -1] >= K - 0.01
    shot_met = one_shot["trace"]["harvested"][:n, -1] >= K - 0.01
    t = np.arange(days + 1)
    top = np.nanquantile(avail, 0.99) * 1.1
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw={"width_ratios": [1.8, 1]})
    frames = list(t) + [days] * 14

    def draw(k):
        a.clear(), b.clear()
        for j in range(n):
            stop = min(k, first[j]) if first[j] >= 0 else k
            a.plot(t[:stop + 1], avail[j, :stop + 1], color=BLUE, lw=0.7, alpha=0.35)
        done = (first >= 0) & (first <= k)
        early = done & (first < days)
        a.scatter(first[early], avail[early, first[early]], s=28, color=AQUA, edgecolor=SURFACE,
                  lw=1, zorder=3, label="review sells early")
        if k == days:
            last = done & (first == days)
            a.scatter(first[last], avail[last, days], s=28, color=BLUE, edgecolor=SURFACE,
                      lw=1, zorder=3, label="sold on the deadline")
        a.axhline(K, color=INK, lw=1, ls="--")
        a.text(0.3, K, f" loss needed {cur}{K:,.0f}", va="bottom", fontsize=8, color=INK)
        a.set_xlim(0, days + 0.5)
        a.set_ylim(0, top)
        a.yaxis.set_major_formatter(money(cur))
        a.set_xlabel("trading days from today")
        a.set_title(f"{n} simulated paths, weekly review at {trigger:.0%}: day {k}")
        a.legend(loc="upper left", fontsize=8)

        rows = [("sold early", int(early.sum()), AQUA),
                ("still holding" if k < days else "sold on the deadline",
                 int(n - early.sum()), BLUE)]
        if k == days:
            rows += [("review met the goal", int(met.sum()), AQUA),
                     ("one-shot plan met it", int(shot_met.sum()), ORANGE)]
        y = np.arange(len(rows))[::-1]
        b.barh(y, [r[1] for r in rows], color=[r[2] for r in rows], height=0.6)
        for yi, (lab, v, _) in zip(y, rows):
            b.text(v + 0.8, yi, f"{v}", va="center", fontsize=9, color=INK)
        b.set_yticks(y, [r[0] for r in rows], fontsize=9)
        b.set_xlim(0, n * 1.12)
        b.set_ylim(-0.6, 3.6)
        b.set_xlabel("paths")
        b.grid(axis="y", visible=False)
        b.set_title("Tally")
        fig.tight_layout()

    FuncAnimation(fig, draw, frames=frames).save(path, writer=PillowWriter(fps=5), dpi=80)
    plt.close(fig)
