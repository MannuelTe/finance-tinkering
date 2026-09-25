"""Command-line interface for market-surveillance workflows."""

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from marketsurv.data.diagnostics import BLOCK, check_rows
from marketsurv.surveillance.pipeline import run_datapull_study

DEFAULT_RESULTS = Path("data/cache/event-study-results.csv")


def _validate_pull(args: argparse.Namespace) -> int:
    raw = pd.read_csv(args.input, low_memory=False)
    checks = check_rows(raw, min_obs=args.min_observations)
    clean = [check for check in checks if not check.issues]

    print(f"{len(clean)}/{len(checks)} rows passed all automated checks.")
    for check in checks:
        if not check.issues:
            continue
        print(f"\nrow {check.row}: {check.target} ({check.ticker})")
        print(
            f"  observations: price={check.price_obs}/{BLOCK}, "
            f"volume={check.volume_obs}/{BLOCK}, benchmark={check.bench_obs}/{BLOCK}"
        )
        for issue in check.issues:
            print(f"  - {issue}")
    return int(len(clean) != len(checks))


def _analyze(args: argparse.Namespace) -> int:
    run = run_datapull_study(args.input, output=args.output)
    weekend_count = int(run.deals["weekend_announce"].sum()) if not run.deals.empty else 0
    print(f"Usable takeovers: {len(run.deals):,}")
    print(f"Weekend announcements: {weekend_count:,}")
    print(f"Results: {args.output}")

    peak_counts = run.peak_offsets.value_counts().sort_index().astype(int).to_dict()
    print(f"Day-zero alignment (-2 to +2): {peak_counts}")
    print("\nAggregate screen results:")
    print(run.summary().round(3).to_string())

    if not run.results.empty:
        events = run.results[run.results["kind"] == "event"].sort_values("car_t", ascending=False)
        columns = ["target", "day0_date", "status", "car", "car_t", "volume_z", "flagged"]
        print("\nHighest-scoring events:")
        print(events[columns].head(args.limit).round(3).to_string(index=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the public command-line parser."""
    parser = argparse.ArgumentParser(
        prog="marketsurv",
        description="Market-surveillance analysis and transaction-report controls.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-pull", help="check a Bloomberg export before analysis"
    )
    validate_parser.add_argument("input", type=Path, help="wide Bloomberg CSV export")
    validate_parser.add_argument(
        "--min-observations",
        type=int,
        default=400,
        metavar="N",
        help="minimum observations per block (default: 400)",
    )
    validate_parser.set_defaults(handler=_validate_pull)

    analyze_parser = subparsers.add_parser(
        "analyze", help="run event and within-stock placebo screens"
    )
    analyze_parser.add_argument("input", type=Path, help="wide Bloomberg CSV export")
    analyze_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_RESULTS,
        help=f"result CSV (default: {DEFAULT_RESULTS})",
    )
    analyze_parser.add_argument(
        "--limit", type=int, default=10, help="number of high-scoring events to display"
    )
    analyze_parser.set_defaults(handler=_analyze)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "limit", 1) < 1:
        parser.error("--limit must be positive")
    try:
        return args.handler(args)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
