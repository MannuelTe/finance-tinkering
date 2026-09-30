import numpy as np
import pandas as pd
from scipy.stats import norm

from ptune import analyze, grid


def test_grid_is_preregistered_shape():
    tasks = grid.oat_tasks()
    assert sum(t["tag"] == "baseline" for t in tasks) == 20
    # every OAT task changes exactly one parameter, to a value different from the baseline
    for t in tasks:
        if t["tag"] != "baseline":
            ((name, value),) = t["params"].items()
            assert value != grid.BASE[name]
    joint = grid.joint_tasks()
    assert len(joint) == 2 * grid.N_JOINT
    assert joint == grid.joint_tasks()  # deterministic


def test_config_for_splits_engine_switches():
    config, extra = grid.config_for({"cov_type": "diag", "risk_aversion": 5.0})
    assert extra == {"cov_type": "diag", "mixture_cov": False, "outcome": "simple",
                     "regime_cov": "diag", "assets": "repl"}
    assert config.risk_aversion == 5.0


def test_deflated_sharpe_penalises_many_trials():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.001, 0.01, 700))
    few = analyze.deflated_sharpe(r, np.array([1.0, 1.2, 1.4]))
    many = analyze.deflated_sharpe(r, rng.normal(1.0, 0.6, 500))
    assert 0 <= many < few <= 1


def test_lagged_returns_shift_weights_one_day():
    idx = pd.bdate_range("2024-01-01", periods=4)
    frame = pd.DataFrame({"w_A": [1, 0, 1, 0], "w_B": [0, 1, 0, 1]}, index=idx, dtype=float)
    rets = pd.DataFrame({"A": [0.1, 0.2, 0.3, 0.4], "B": [-0.1, -0.2, -0.3, -0.4]}, index=idx)
    out = analyze.lagged(frame, rets)
    assert list(out.round(3)) == [0.2, -0.3, 0.4]
