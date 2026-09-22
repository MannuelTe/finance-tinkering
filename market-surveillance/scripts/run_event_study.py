"""Run the pre-announcement screen on a datapull, with a within-stock placebo.

    uv run python scripts/run_event_study.py data/raw/datapull_3.csv

Placebo: the same screen on the same stocks at fake event days (offsets -60, -100, -140), each
far from the real announcement. Flags there estimate the false-positive rate. Results go to
data/cache/ (git-ignored: they contain per-deal vendor-derived values).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Work even when the editable install's .pth file is skipped (macOS "hidden" flag on Python 3.13).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marketsurv.data.datapull import OFFSETS, load_datapull
from marketsurv.surveillance.event_study import pre_event_screen

PLACEBO_OFFSETS = (-60, -100, -140)
OUT = Path(__file__).resolve().parents[1] / "data" / "cache"


def day0_diagnostic(deals: pd.DataFrame, series: dict[int, pd.DataFrame]) -> pd.Series:
    """Offset (-2..+2) with the largest absolute return, per deal. Should peak at 0 or +1."""
    pos0 = int(np.flatnonzero(OFFSETS == 0)[0])
    out = {}
    for i in deals["deal_id"]:
        r = series[i]["ret"].iloc[pos0 - 2 : pos0 + 3].abs().to_numpy()
        out[i] = int(np.nanargmax(r)) - 2 if np.isfinite(r).any() else np.nan
    return pd.Series(out)


def main(path: str) -> None:
    deals, series = load_datapull(path)
    print(f"{len(deals)} usable takeovers; weekend announce dates: {deals.weekend_announce.sum()}")

    peak = day0_diagnostic(deals, series)
    print("Offset of largest |return| within -2..+2:", peak.value_counts().sort_index().to_dict())

    rows = []
    for _, d in deals.iterrows():
        s = series[d.deal_id]
        for label, shift in [("event", 0), *[(f"placebo{p}", p) for p in PLACEBO_OFFSETS]]:
            anchor = s.index[int(np.flatnonzero(OFFSETS == 0)[0]) + shift]
            res = pre_event_screen(s, s["mkt"], anchor)
            if res is not None:
                rows.append({"deal_id": d.deal_id, "kind": label.rstrip("-0123456789"),
                             "anchor": anchor, **{k: v for k, v in res.__dict__.items()
                                                  if k != "event_date"}})
    res = pd.DataFrame(rows).merge(deals, on="deal_id")
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "event_study_results.csv", index=False)

    g = res.groupby("kind")
    print("\nScreen results (n, flag rate, car_t / volume_z median and 95th pct):")
    print(pd.DataFrame({
        "n": g.size(),
        "flag_rate": g["flagged"].mean().round(3),
        "car_t_med": g["car_t"].median().round(2), "car_t_p95": g["car_t"].quantile(.95).round(2),
        "volz_med": g["volume_z"].median().round(2), "volz_p95": g["volume_z"].quantile(.95).round(2),
        "car_med_%": (g["car"].median() * 100).round(2),
    }).to_string())

    ev = res[res.kind == "event"].sort_values("car_t", ascending=False)
    print("\nTop 10 flagged/highest-scoring events:")
    print(ev[["target", "day0_date", "status", "car", "car_t", "volume_z", "flagged"]]
          .head(10).round(3).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/raw/datapull_3.csv")
