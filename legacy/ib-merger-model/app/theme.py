"""Validated chart palette and formatting helpers.

Palette slots come from the data-viz reference instance and were checked with
the six-check validator against the Streamlit surface (#ffffff light):

  3-slot, all-pairs   worst CVD dE 9.2 · worst normal-vision dE 24.0   PASS
  5-slot, adjacent    worst CVD dE 9.1 · worst normal-vision dE 19.6   PASS

Three slots sit below 3:1 contrast on white, so the relief rule applies: every
chart in this app ships either direct value labels or an adjacent table view.
"""

# Categorical slots, in fixed order. Never cycle, never reassign by rank.
SERIES = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
]

# Only the first three validate under the all-pairs rule (scatter, heat cells,
# small multiples). Past three, fold to "Other" or facet.
SERIES_ALLPAIRS = SERIES[:3]

# Sequential ramp for magnitude (one hue, light to dark).
SEQ_BLUE = [
    "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
    "#2a78d6", "#256abf", "#184f95", "#0d366b",
]

# Status colors are reserved. Never reused as a series color; always paired
# with an icon or label so state is never carried by hue alone.
STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

# Chart chrome.
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# Stable entity -> color maps, so a filter that drops a series never repaints
# the survivors.
BANK_COLORS = {
    "Aareland Regionalbank (A)": SERIES[0],
    "Novafin Kreditbank (B)": SERIES[1],
    "Banca Alpina (C)": SERIES[2],
}

CLIENT_COLORS = {
    "Privatkunden (individuals)": SERIES[0],
    "Firmenkunden (companies)": SERIES[1],
}

# Four Swiss economic regions.
REGION_COLORS = {
    "Romandie": SERIES[0],
    "Mittelland": SERIES[1],
    "Alpen": SERIES[2],
    "Tessin": SERIES[3],
}

# Swiss GAAP vs the IFRS 9 shadow. Two series, so the first two slots.
BASIS_COLORS = {
    "Swiss GAAP": SERIES[0],
    "IFRS 9 (shadow)": SERIES[1],
}


def money(value: float, unit: str = "m") -> str:
    """Format a CHF millions figure for display."""
    if abs(value) >= 1000:
        return f"CHF {value / 1000:,.2f}bn"
    return f"CHF {value:,.1f}{unit}"


def pct(value: float, places: int = 2) -> str:
    """Format a decimal fraction as a percentage."""
    return f"{value * 100:.{places}f}%"


def bps(value: float) -> str:
    """Format a decimal fraction difference as basis points."""
    return f"{value * 10000:+,.0f}bp"


def rag(ratio: float, floor: float, target: float) -> str:
    """Return a status key for a capital ratio against its floor and target."""
    if ratio < floor:
        return "critical"
    if ratio < target:
        return "warning"
    return "good"
