from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd

from marketsurv.reporting.reconcile import reconcile
from marketsurv.reporting.rts22 import TransactionReport, validate

LEI = "HWUPKR0MPOU8FGXBT394"


def make(**over) -> TransactionReport:
    base = dict(  # noqa: C408
        report_status="NEWT", transaction_ref="TRX0001", executing_entity=LEI,
        investment_firm_covered=True, submitting_entity=LEI, buyer_id=LEI, seller_id="INTC",
        trading_datetime=datetime(2026, 1, 5, 10, 30, tzinfo=UTC),
        trading_capacity="DEAL", quantity=Decimal(100), price=Decimal("12.5"),
        price_currency="EUR", venue="XETR", instrument_id="DE000BAY0017",
        investment_decision_within_firm="ALGO1", execution_within_firm="ALGO1",
    )
    base.update(over)
    return TransactionReport(**base)


def test_valid_report_passes():
    assert validate(make()) == []


def test_each_defect_is_reported_on_its_field():
    r = make(instrument_id="DE000BAY0018", quantity=Decimal(0), venue="xetr",
             trading_datetime=datetime(2026, 1, 5, 10, 30), trading_capacity="XXXX")  # noqa: DTZ001 (naive on purpose)
    assert {i.field_no for i in validate(r)} == {41, 30, 36, 28, 29}


def test_reconcile_finds_all_break_types():
    internal = pd.DataFrame({"transaction_ref": ["A", "B", "C", "D"],
                             "quantity": [1.0, 2.0, 3.0, 4.0], "price": [10.0] * 4})
    ack = pd.DataFrame({"transaction_ref": ["B", "C", "D", "E"],
                        "status": ["ACPT", "RJCT", "ACPT", "ACPT"],
                        "quantity": [2.0, 3.0, 5.0, 1.0], "price": [10.0] * 4,
                        "reason": ["", "bad LEI", "", ""]})
    out = reconcile(internal, ack).set_index("transaction_ref")["break"].to_dict()
    assert out == {"A": "missing_in_ack", "C": "rejected", "D": "quantity_mismatch",
                   "E": "unexpected_in_ack"}
