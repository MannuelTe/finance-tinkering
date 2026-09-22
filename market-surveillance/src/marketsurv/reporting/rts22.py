"""MiFIR RTS 22 transaction report: an equity-focused subset of the 65 fields, plus validation.

Field numbers follow Annex Table 2 of Commission Delegated Regulation (EU) 2017/590. This is a
learning implementation: verify against the current ESMA reporting instructions and XML schema
before relying on it. Not covered: derivatives fields (44-56), natural-person names/DOB
(9-11, 18-20), decision-maker blocks, and ISO 20022 XML serialisation.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal

from marketsurv import identifiers as ids

TRADING_CAPACITIES = {"DEAL", "MTCH", "AOTC"}
REPORT_STATUS = {"NEWT", "CANC"}
SHORT_SELLING = {"SESH", "SSEX", "SELL", "UNDI"}
WAIVERS = {"NLIQ", "OILQ", "PRIC", "SIZE", "ILQD"}
# Buyer/seller code: LEI for legal entities, "INTC" for aggregated internal client accounts,
# otherwise a national identifier for natural persons (format depends on nationality).
NON_LEI_CODES = {"INTC"}


@dataclass
class Issue:
    field_no: int
    field: str
    message: str


@dataclass
class TransactionReport:
    report_status: str  # 1
    transaction_ref: str  # 2
    executing_entity: str  # 4 (LEI)
    investment_firm_covered: bool  # 5
    submitting_entity: str  # 6 (LEI)
    buyer_id: str  # 7
    seller_id: str  # 16
    trading_datetime: datetime  # 28 (UTC)
    trading_capacity: str  # 29
    quantity: Decimal  # 30
    price: Decimal  # 33
    price_currency: str  # 34
    venue: str  # 36 (MIC, XOFF or XXXX)
    instrument_id: str  # 41 (ISIN)
    investment_decision_within_firm: str  # 57 (natural person / algo id)
    execution_within_firm: str  # 59
    short_selling_indicator: str | None = None  # 62
    waiver_indicator: str | None = None  # 61
    securities_financing: bool = False  # 65

    def to_dict(self) -> dict:
        return asdict(self)


def _is_lei_or_code(value: str, allow_national_id: bool) -> bool:
    if ids.lei_valid(value) or value in NON_LEI_CODES:
        return True
    return allow_national_id and 5 <= len(value) <= 35 and value.isalnum()


def validate(r: TransactionReport) -> list[Issue]:
    """Return all validation issues found; an empty list means the report passes."""
    out: list[Issue] = []

    def bad(no: int, name: str, msg: str) -> None:
        out.append(Issue(no, name, msg))

    if r.report_status not in REPORT_STATUS:
        bad(1, "report_status", f"must be one of {sorted(REPORT_STATUS)}")
    if not (1 <= len(r.transaction_ref) <= 52) or not r.transaction_ref.isalnum():
        bad(2, "transaction_ref", "1-52 alphanumeric characters")
    for no, name, val in [
        (4, "executing_entity", r.executing_entity),
        (6, "submitting_entity", r.submitting_entity),
    ]:
        if not ids.lei_valid(val):
            bad(no, name, "not a valid LEI (format or mod-97 checksum)")
    for no, name, val in [(7, "buyer_id", r.buyer_id), (16, "seller_id", r.seller_id)]:
        if not _is_lei_or_code(val, allow_national_id=True):
            bad(no, name, "expected LEI, INTC or a national identifier")
    if r.trading_datetime.tzinfo is None or r.trading_datetime.utcoffset() != UTC.utcoffset(None):
        bad(28, "trading_datetime", "must be timezone-aware UTC")
    elif r.trading_datetime > datetime.now(UTC):
        bad(28, "trading_datetime", "is in the future")
    if r.trading_capacity not in TRADING_CAPACITIES:
        bad(29, "trading_capacity", f"must be one of {sorted(TRADING_CAPACITIES)}")
    if r.quantity <= 0:
        bad(30, "quantity", "must be positive")
    if r.price <= 0:
        bad(33, "price", "must be positive")  # zero prices are legal for some instruments; not here
    if not ids.currency_valid(r.price_currency):
        bad(34, "price_currency", "must be a 3-letter ISO 4217 code")
    if not ids.mic_valid(r.venue):
        bad(36, "venue", "must be a 4-character MIC (or XOFF/XXXX)")
    if not ids.isin_valid(r.instrument_id):
        bad(41, "instrument_id", "not a valid ISIN (format or Luhn checksum)")
    if not r.investment_decision_within_firm:
        bad(57, "investment_decision_within_firm", "required")
    if not r.execution_within_firm:
        bad(59, "execution_within_firm", "required")
    if r.short_selling_indicator is not None and r.short_selling_indicator not in SHORT_SELLING:
        bad(62, "short_selling_indicator", f"must be one of {sorted(SHORT_SELLING)}")
    if r.waiver_indicator is not None and r.waiver_indicator not in WAIVERS:
        bad(61, "waiver_indicator", f"must be one of {sorted(WAIVERS)}")
    return out
