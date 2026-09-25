"""End-to-end workflow for the pre-announcement event study."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from marketsurv.data.datapull import OFFSETS, load_datapull
from marketsurv.surveillance.event_study import EventResult, pre_event_screen

DEFAULT_PLACEBO_OFFSETS = (-60, -100, -140)
DAY_ZERO_POSITION = int(np.flatnonzero(OFFSETS == 0)[0])
RESULT_COLUMNS = [
    "deal_id",
    "kind",
    "anchor",
    *[name for name in EventResult.__dataclass_fields__ if name != "event_date"],
]


@dataclass(frozen=True, slots=True)
class StudyRun:
    """Normalized inputs, alignment diagnostics and screen results for one run."""

    deals: pd.DataFrame
    peak_offsets: pd.Series
    results: pd.DataFrame

    def summary(self) -> pd.DataFrame:
        """Return aggregate metrics by real event and placebo observations."""
        if self.results.empty:
            return pd.DataFrame(
                columns=[
                    "n",
                    "flag_rate",
                    "car_t_median",
                    "car_t_p95",
                    "volume_z_median",
                    "volume_z_p95",
                    "car_median_pct",
                ]
            )
        grouped = self.results.groupby("kind", sort=False)
        return pd.DataFrame(
            {
                "n": grouped.size(),
                "flag_rate": grouped["flagged"].mean(),
                "car_t_median": grouped["car_t"].median(),
                "car_t_p95": grouped["car_t"].quantile(0.95),
                "volume_z_median": grouped["volume_z"].median(),
                "volume_z_p95": grouped["volume_z"].quantile(0.95),
                "car_median_pct": grouped["car"].median() * 100,
            }
        )


def _peak_offsets(deals: pd.DataFrame, series: dict[int, pd.DataFrame]) -> pd.Series:
    """Find the largest absolute return from offset -2 through +2 for each deal."""
    peaks: dict[int, float] = {}
    for deal_id in deals["deal_id"]:
        returns = series[deal_id]["ret"].iloc[DAY_ZERO_POSITION - 2 : DAY_ZERO_POSITION + 3]
        values = returns.abs().to_numpy()
        peaks[deal_id] = (
            float(np.nanargmax(values) - 2) if np.isfinite(values).any() else float("nan")
        )
    return pd.Series(peaks, name="peak_offset", dtype=float)


def run_datapull_study(
    path: str | Path,
    *,
    output: str | Path | None = None,
    placebo_offsets: Iterable[int] = DEFAULT_PLACEBO_OFFSETS,
) -> StudyRun:
    """Run the event and within-stock placebo screens for a Bloomberg export."""
    offsets = tuple(placebo_offsets)
    if any(offset >= 0 for offset in offsets):
        raise ValueError("placebo offsets must be negative")

    deals, series = load_datapull(path)
    rows: list[dict[str, object]] = []
    for deal in deals.itertuples(index=False):
        stock = series[deal.deal_id]
        anchors = (("event", 0), *(("placebo", offset) for offset in offsets))
        for kind, offset in anchors:
            position = DAY_ZERO_POSITION + offset
            if not 0 <= position < len(stock):
                continue
            anchor = stock.index[position]
            result = pre_event_screen(stock, stock["mkt"], anchor)
            if result is None:
                continue
            values = result.to_dict()
            values.pop("event_date")
            rows.append(
                {
                    "deal_id": deal.deal_id,
                    "kind": kind,
                    "anchor": anchor,
                    **values,
                }
            )

    result_frame = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    result_frame = result_frame.merge(deals, on="deal_id", how="left", validate="many_to_one")
    if output is not None:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        result_frame.to_csv(destination, index=False)

    return StudyRun(deals=deals, peak_offsets=_peak_offsets(deals, series), results=result_frame)
