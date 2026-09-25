"""Lots, accounts and portfolio parsing (CSV or free text)."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

# Tokens that mark a tax-sheltered account. Losses there are not deductible, but purchases there
# still count for the US wash-sale rule (Rev. Rul. 2008-5) and, on the conservative CRA reading,
# for the Canadian superficial-loss rule.
SHELTERED_TOKENS = ("ira", "roth", "401k", "403b", "hsa", "rrsp", "rrif", "tfsa", "resp", "fhsa", "lira")

COLUMNS = ["account", "ticker", "shares", "cost_basis", "acquired", "price", "drip"]


def is_sheltered(account: str) -> bool:
    a = account.lower()
    return any(tok in a for tok in SHELTERED_TOKENS)


@dataclass(frozen=True)
class Lot:
    ticker: str
    shares: float
    cost_basis: float  # per share
    acquired: date
    price: float  # current price per share
    account: str = "taxable"
    drip: bool = False

    @property
    def value(self) -> float:
        return self.shares * self.price

    @property
    def basis_total(self) -> float:
        return self.shares * self.cost_basis

    @property
    def unrealized(self) -> float:
        return self.value - self.basis_total

    @property
    def taxable(self) -> bool:
        return not is_sheltered(self.account)


@dataclass(frozen=True)
class PlannedBuy:
    """A purchase already scheduled (payroll contribution, rebalance, spouse's plan...)."""

    ticker: str
    on: date
    account: str = "taxable"


@dataclass
class Portfolio:
    lots: list[Lot]
    as_of: date
    planned_buys: list[PlannedBuy] = field(default_factory=list)

    @property
    def tickers(self) -> list[str]:
        return sorted({lot.ticker for lot in self.lots})

    @property
    def value(self) -> float:
        return sum(lot.value for lot in self.lots)

    def frame(self) -> pd.DataFrame:
        rows = [
            {
                "account": lot.account,
                "ticker": lot.ticker,
                "shares": lot.shares,
                "cost_basis": lot.cost_basis,
                "acquired": lot.acquired,
                "price": lot.price,
                "value": lot.value,
                "unrealized": lot.unrealized,
                "taxable": lot.taxable,
                "drip": lot.drip,
            }
            for lot in self.lots
        ]
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------ parsing
    @classmethod
    def from_frame(cls, df: pd.DataFrame, as_of: date, planned: pd.DataFrame | None = None):
        df = df.copy()
        df.columns = [c.strip().lower() for c in df.columns]
        missing = {"ticker", "shares", "cost_basis", "acquired", "price"} - set(df.columns)
        if missing:
            raise ValueError(f"portfolio is missing columns: {sorted(missing)}")
        if "account" not in df:
            df["account"] = "taxable"
        if "drip" not in df:
            df["drip"] = False
        lots = [
            Lot(
                ticker=str(r.ticker).strip().upper(),
                shares=float(r.shares),
                cost_basis=float(r.cost_basis),
                acquired=pd.Timestamp(r.acquired).date(),
                price=float(r.price),
                account=str(r.account).strip() or "taxable",
                drip=_truthy(r.drip),
            )
            for r in df.itertuples(index=False)
        ]
        buys = []
        if planned is not None and len(planned):
            planned = planned.rename(columns=str.lower)
            buys = [
                PlannedBuy(str(r.ticker).upper(), pd.Timestamp(r.on).date(),
                           str(getattr(r, "account", "taxable")))
                for r in planned.itertuples(index=False)
            ]
        return cls(lots=lots, as_of=as_of, planned_buys=buys)

    @classmethod
    def from_csv(cls, path, as_of: date, planned_path=None):
        planned = pd.read_csv(planned_path) if planned_path else None
        return cls.from_frame(pd.read_csv(path), as_of, planned)

    @classmethod
    def from_text(cls, text: str, as_of: date):
        """Parse whitespace/comma separated lines.

        ``TICKER SHARES COST_BASIS ACQUIRED PRICE [ACCOUNT] [drip]``
        e.g. ``VOO 40 610.5 2026-02-03 548.2 taxable``. A line starting with ``buy`` is a
        planned purchase: ``buy TICKER DATE [ACCOUNT]``.
        """
        lots, buys = [], []
        for raw in text.strip().splitlines():
            line = raw.split("#", 1)[0].replace(",", " ").strip()
            if not line:
                continue
            parts = line.split()
            if parts[0].lower() == "buy":
                acct = parts[3] if len(parts) > 3 else "taxable"
                buys.append(PlannedBuy(parts[1].upper(), pd.Timestamp(parts[2]).date(), acct))
                continue
            if len(parts) < 5:
                raise ValueError(f"need TICKER SHARES BASIS DATE PRICE, got: {raw!r}")
            lots.append(
                Lot(
                    ticker=parts[0].upper(),
                    shares=float(parts[1]),
                    cost_basis=float(parts[2]),
                    acquired=pd.Timestamp(parts[3]).date(),
                    price=float(parts[4]),
                    account=parts[5] if len(parts) > 5 else "taxable",
                    drip=len(parts) > 6 and _truthy(parts[6]),
                )
            )
        return cls(lots=lots, as_of=as_of, planned_buys=buys)

    def to_csv(self) -> str:
        buf = io.StringIO()
        self.frame()[COLUMNS].to_csv(buf, index=False)
        return buf.getvalue()


def _truthy(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y", "drip"}
    return bool(pd.notna(v) and v)
