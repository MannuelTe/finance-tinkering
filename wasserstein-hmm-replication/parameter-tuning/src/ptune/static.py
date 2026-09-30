"""Exploratory (added after the sweep results): does the model's timing add anything over
holding its own average allocation?

    python -m ptune.static

For every joint draw (replication data) and E4 draw (paper data mapping), the "static twin"
holds that draw's average test-window weights every day. Also scores fixed allocations:
equal weight and the paper's reported average HMM allocation.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .analyze import PAPER_ALLOC, RES, daily, load_log, sharpe
from .data import prices


def asset_returns(assets: str) -> pd.DataFrame:
    p = prices(assets)
    return np.log(p).diff() if assets == "paper" else p.pct_change()


def twins(log: pd.DataFrame, prefix: str, assets: str, window: str) -> pd.DataFrame:
    r = asset_returns(assets)
    rows = []
    for _, row in log[log.tag.str.startswith(prefix) & (log.window == window)].iterrows():
        f = daily(row.key)
        w = f.filter(like="w_").rename(columns=lambda c: c[2:])
        rr = r.reindex(w.index)[w.columns]
        rows.append({"tag": row.tag, "penalty": row["p.turnover_penalty"],
                     "sharpe": sharpe(f["gross"]), "turnover": f["turnover"].mean(),
                     "static_avg": sharpe((rr * w.mean()).sum(axis=1)),
                     "static_day1": sharpe((rr * w.iloc[0]).sum(axis=1))})
    out = pd.DataFrame(rows)
    out["timing"] = out.sharpe - out.static_avg
    return out


def main():
    log = load_log()
    res = {}
    for name, prefix, assets, window in (("joint", "joint:", "repl", "oos"),
                                         ("E4", "E4:", "paper", "paper_oos")):
        t = twins(log, prefix, assets, window)
        t.to_csv(RES / f"static_twins_{name}.csv", index=False)
        t["band"] = pd.cut(t.turnover, [-1, 1e-3, 5e-3, 2e-2, 1],
                           labels=["<0.001", "0.001-0.005", "0.005-0.02", ">0.02"])
        g = t.groupby("band", observed=True)[["sharpe", "static_avg", "static_day1", "timing"]]
        res[name] = {"by_turnover": g.mean().round(3).join(g.size().rename("n")).reset_index()
                     .to_dict("records"),
                     "timing_mean": float(t.timing.mean()),
                     "share_timing_positive": float((t.timing > 0).mean()),
                     "corr_sharpe_static": float(t[["sharpe", "static_avg"]].corr().iloc[0, 1])}
    r = asset_returns("paper").loc["2023-06-05":"2026-02-19"]
    fixed = {"equal weight": {a: 0.2 for a in r.columns}, "paper average HMM": PAPER_ALLOC,
             "paper average renormalised": {a: v / sum(PAPER_ALLOC.values())
                                            for a, v in PAPER_ALLOC.items()}}
    res["fixed_paper_data"] = {k: sharpe((r * pd.Series(w)).sum(axis=1)) for k, w in fixed.items()}
    res["asset_sharpes_paper_data"] = {a: sharpe(r[a]) for a in r.columns}
    (RES / "static.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
