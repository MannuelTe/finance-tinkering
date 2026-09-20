import yfinance as yf
import pandas as pd

# Configuration
ASSET_TICKER = "ASML"
MARKET_TICKER = "SPY"  # S&P 500 proxy
EQUAL_WEIGHT_TICKER = "RSP"  # S&P 500 Equal Weight proxy

TIMEFRAMES = [
    ("5y_monthly", "5y", "1mo"),
    ("2y_weekly", "2y", "1wk"),
]


def download_returns(tickers, period, interval):
    data = yf.download(tickers, period=period, interval=interval, progress=False)["Close"]
    returns = data.pct_change().dropna(how="all")
    return returns


def beta(asset_returns, market_returns):
    aligned = pd.concat([asset_returns, market_returns], axis=1).dropna()
    if aligned.empty:
        return float("nan")
    cov = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
    var = aligned.iloc[:, 1].var()
    return cov / var if var != 0 else float("nan")


def betas_for_ticker(asset_ticker, period, interval):
    tickers = [asset_ticker, MARKET_TICKER, EQUAL_WEIGHT_TICKER]
    returns = download_returns(tickers, period, interval)

    asset = returns[asset_ticker]
    market = returns[MARKET_TICKER]
    equal_weight = returns[EQUAL_WEIGHT_TICKER]

    beta_vs_spy = beta(asset, market)
    beta_vs_rsp = beta(asset, equal_weight)
    return beta_vs_spy, beta_vs_rsp


def run_for_timeframe(label, period, interval):
    beta_vs_spy, beta_vs_rsp = betas_for_ticker(ASSET_TICKER, period, interval)

    print(f"\n=== {label} ===")
    print(f"{ASSET_TICKER} beta vs SPY: {beta_vs_spy:.4f}")
    print(f"{ASSET_TICKER} beta vs RSP: {beta_vs_rsp:.4f}")


if __name__ == "__main__":
    for label, period, interval in TIMEFRAMES:
        run_for_timeframe(label, period, interval)
