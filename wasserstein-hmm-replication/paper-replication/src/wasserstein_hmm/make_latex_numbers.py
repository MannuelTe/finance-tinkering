"""PURPOSE: generate LaTeX macros for every empirical/configuration number in the paper.
INPUTS: results.json from the replication.
OUTPUTS: numbers.tex consumed by the standalone LaTeX paper.
"""

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def command(name: str, value: Any) -> str:
    return f"\\newcommand{{\\{name}}}{{{value}}}"


def number(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def percent(value: float, digits: int = 2) -> str:
    return f"{100 * value:.{digits}f}\\%"


def main() -> None:
    result = json.loads((ROOT / "results" / "results.json").read_text())
    published = result["published"]
    reproduced = result["reproduced"]
    config = result["config"]
    sample = result["sample"]
    prefixes = {
        "wasserstein_hmm": "HMM",
        "knn": "KNN",
        "equal_weight": "Equal",
        "spx": "SPX",
    }
    lines = ["% Generated from results.json by make_latex_numbers.py; do not edit."]
    for key, prefix in prefixes.items():
        lines.extend([
            command(f"Pub{prefix}Sharpe", number(published[key]["sharpe"])),
            command(f"Pub{prefix}MaxDD", percent(published[key]["max_drawdown"])),
            command(f"Rep{prefix}Sharpe", number(reproduced[key]["sharpe"])),
            command(f"Rep{prefix}MaxDD", percent(reproduced[key]["max_drawdown"])),
            command(f"Rep{prefix}Return", percent(reproduced[key]["total_return"])),
            command(f"Rep{prefix}Vol", percent(reproduced[key]["annualized_volatility"])),
        ])
        if "turnover" in published[key]:
            lines.extend([
                command(f"Pub{prefix}Turnover", number(published[key]["turnover"], 4)),
                command(f"Rep{prefix}Turnover", number(reproduced[key]["turnover"], 4)),
                command(f"Rep{prefix}TurnoverQ", number(reproduced[key]["turnover_q95"], 4)),
            ])
    for key, prefix in (("wasserstein_hmm_net_5bps", "HMMNet"), ("knn_net_5bps", "KNNNet")):
        lines.extend([
            command(f"Rep{prefix}Sharpe", number(reproduced[key]["sharpe"])),
            command(f"Rep{prefix}MaxDD", percent(reproduced[key]["max_drawdown"])),
            command(f"Rep{prefix}Return", percent(reproduced[key]["total_return"])),
        ])
    lines.extend([
        command("PriceStart", sample["price_start"]),
        command("PriceEnd", sample["price_end"]),
        command("OOSStart", sample["oos_start"]),
        command("OOSEnd", sample["oos_end"]),
        command("OOSObs", sample["oos_observations"]),
        command("VolWindow", config["volatility_window"]),
        command("MomWindow", config["momentum_window"]),
        command("TemplateCount", config["template_count"]),
        command("ValidationDays", config["validation_days"]),
        command("RefitFrequency", config["refit_frequency"]),
        command("OrderFrequency", config["order_selection_frequency"]),
        command("KNNNeighbors", config["knn_neighbors"]),
        command("RiskAversion", number(config["risk_aversion"], 1)),
        command("TurnoverPenalty", number(config["turnover_penalty"], 4)),
        command("MaxWeight", percent(config["max_weight"], 0)),
        command("RealizedCost", number(config["realized_cost_bps"], 0)),
        command("RandomSeed", config["random_seed"]),
        command("CandidateStates", "2--6"),
        command("HMMSharpeGap", number(reproduced["wasserstein_hmm"]["sharpe"] - published["wasserstein_hmm"]["sharpe"])),
        command("HMMDDGap", percent(reproduced["wasserstein_hmm"]["max_drawdown"] - published["wasserstein_hmm"]["max_drawdown"])),
        command("TurnoverRatio", number(reproduced["knn"]["turnover"] / reproduced["wasserstein_hmm"]["turnover"], 1)),
    ])
    for ticker, value in result["average_weights"]["wasserstein_hmm"].items():
        lines.append(command(f"Avg{ticker}Weight", percent(value)))
    (ROOT / "paper" / "numbers.tex").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
