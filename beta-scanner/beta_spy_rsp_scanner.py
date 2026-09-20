import csv
import logging
import time

import pandas as pd
import yfinance as yf

from beta_sp500 import betas_for_ticker, TIMEFRAMES

# Universe source (S&P 500 list from Wikipedia by default)
TICKER_SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# Medium market cap range (USD)
MIN_MARKET_CAP = 2_000_000_000
MAX_MARKET_CAP = 10_000_000_000

# Minimum difference between RSP beta and SPY beta
MIN_BETA_DIFF = 0.2

# Throttle between API calls to be polite
SLEEP_SECONDS = 0.2

RESULTS_PATH = "beta_spy_rsp_scan.csv"
LOG_PATH = "beta_spy_rsp_scan.log"


def load_ticker_universe():
    tables = pd.read_html(TICKER_SOURCE_URL)
    df = tables[0]
    tickers = df["Symbol"].tolist()
    names = dict(zip(df["Symbol"], df["Security"]))
    return tickers, names


def get_market_cap_and_name(ticker, fallback_name=None):
    info = yf.Ticker(ticker).info
    market_cap = info.get("marketCap")
    name = info.get("shortName") or fallback_name or ticker
    return market_cap, name


def in_midcap_range(market_cap):
    return market_cap is not None and MIN_MARKET_CAP <= market_cap <= MAX_MARKET_CAP


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH),
            logging.StreamHandler(),
        ],
    )


def write_header_if_needed(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            if f.readline():
                return
    except FileNotFoundError:
        pass

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "ticker",
                "company",
                "market_cap",
                "timeframe",
                "beta_spy",
                "beta_rsp",
                "beta_diff",
            ]
        )


def scan():
    tickers, name_map = load_ticker_universe()
    logging.info("Loaded %d tickers", len(tickers))

    write_header_if_needed(RESULTS_PATH)

    with open(RESULTS_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        for ticker in tickers:
            try:
                market_cap, name = get_market_cap_and_name(ticker, name_map.get(ticker))
            except Exception as exc:
                logging.warning("Failed to fetch info for %s: %s", ticker, exc)
                time.sleep(SLEEP_SECONDS)
                continue

            if not in_midcap_range(market_cap):
                time.sleep(SLEEP_SECONDS)
                continue

            for label, period, interval in TIMEFRAMES:
                try:
                    beta_spy, beta_rsp = betas_for_ticker(ticker, period, interval)
                except Exception as exc:
                    logging.warning("Failed beta calc for %s (%s): %s", ticker, label, exc)
                    continue

                beta_diff = beta_rsp - beta_spy
                if beta_rsp > beta_spy and beta_diff >= MIN_BETA_DIFF:
                    logging.info(
                        "Match %s (%s) %s: SPY=%.4f RSP=%.4f diff=%.4f",
                        ticker,
                        name,
                        label,
                        beta_spy,
                        beta_rsp,
                        beta_diff,
                    )
                    writer.writerow(
                        [
                            ticker,
                            name,
                            market_cap,
                            label,
                            f"{beta_spy:.4f}",
                            f"{beta_rsp:.4f}",
                            f"{beta_diff:.4f}",
                        ]
                    )

            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    setup_logging()
    scan()
