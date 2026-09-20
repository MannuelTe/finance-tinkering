from __future__ import annotations

# Sleeve: heavy on European ETFs, mixing market-cap and equal-weight indices, skewed to US
# infrastructure and Canada + EU energy/capital projects. Weights inside the sleeve (sum 1.0)
# are a first draft, not a validated allocation.
SLEEVE: dict[str, float] = {
    "EXSA": 0.20,  # STOXX Europe 600, market-cap
    "MEEQ": 0.20,  # MSCI Europe Equal Weight (listed only since 2025-03)
    "PAVE": 0.20,  # US infrastructure development
    "EXH1": 0.15,  # STOXX Europe 600 Oil & Gas
    "XUT": 0.15,  # Canadian utilities (capital-projects tilt)
    "XDEW": 0.10,  # S&P 500 Equal Weight
}

# The same sleeve with the Europe equal-weight fund folded into the Europe cap-weight one, so the
# history reaches back to 2021 (MEEQ only lists from 2025-03). Used by long-window backtests.
SLEEVE_LONG: dict[str, float] = {k: v for k, v in SLEEVE.items() if k != "MEEQ"}
SLEEVE_LONG["EXSA"] += SLEEVE["MEEQ"]

CLASSIC: dict[str, float] = {"SPY": 0.6, "TLT": 0.4}

# EUR-hedged share classes standing in for the unhedged USD holdings.
HEDGED_EQUIVALENT: dict[str, str] = {"SPY": "IUSE", "TLT": "DTLE"}

SLEEVE_SHARE = 0.5
HEDGE_SHARE = 0.05  # fraction of the *whole portfolio* moved into hedged share classes


def blended_weights(
    sleeve: dict[str, float] = SLEEVE,
    sleeve_share: float = SLEEVE_SHARE,
    hedge_share: float = HEDGE_SHARE,
) -> dict[str, float]:
    """Sleeve + classic 60/40, with `hedge_share` of the whole portfolio moved from the
    unhedged classic holdings into their EUR-hedged equivalents (pro rata, so the 60/40 ratio
    is preserved)."""
    classic_share = 1.0 - sleeve_share
    if hedge_share > classic_share:
        raise ValueError(f"hedge_share {hedge_share} exceeds the classic share {classic_share}")

    weights = {symbol: w * sleeve_share for symbol, w in sleeve.items()}
    hedge_fraction = hedge_share / classic_share
    for symbol, w in CLASSIC.items():
        total = w * classic_share
        hedged = total * hedge_fraction
        weights[symbol] = weights.get(symbol, 0.0) + total - hedged
        if hedged:
            hedge_symbol = HEDGED_EQUIVALENT[symbol]
            weights[hedge_symbol] = weights.get(hedge_symbol, 0.0) + hedged
    return weights
