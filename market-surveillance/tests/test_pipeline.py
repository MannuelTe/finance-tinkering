import numpy as np
import pandas as pd

from marketsurv.data.datapull import BLOCK, META_COLUMNS
from marketsurv.surveillance.pipeline import run_datapull_study


def test_pipeline_runs_events_and_placebos_and_writes_output(tmp_path):
    rng = np.random.default_rng(42)
    market_return = rng.normal(0, 0.008, BLOCK)
    stock_return = 0.0002 + 1.1 * market_return + rng.normal(0, 0.006, BLOCK)
    price = 100 * np.cumprod(1 + stock_return)
    benchmark = 100 * np.cumprod(1 + market_return)
    volume = np.exp(rng.normal(13, 0.25, BLOCK))
    metadata = [
        "M&A",
        "3/23/2026",
        "Target",
        "Acquirer",
        None,
        100.0,
        "Cash",
        None,
        "Completed",
        "AAA IM",
        "BBB IM",
        "",
    ]
    columns = [*META_COLUMNS, *[f"c{i}" for i in range(3 * BLOCK)]]
    source = tmp_path / "pull.csv"
    pd.DataFrame([[*metadata, *price, *volume, *benchmark]], columns=columns).to_csv(
        source, index=False
    )
    output = tmp_path / "results" / "study.csv"

    run = run_datapull_study(source, output=output)

    assert output.is_file()
    assert len(run.deals) == 1
    assert run.results["kind"].value_counts().to_dict() == {"placebo": 3, "event": 1}
    assert set(run.summary().index) == {"event", "placebo"}
