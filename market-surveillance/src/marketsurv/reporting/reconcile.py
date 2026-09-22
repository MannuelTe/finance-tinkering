"""Reconcile internal trade records against what an ARM acknowledged."""

import pandas as pd

KEY = "transaction_ref"


def reconcile(internal: pd.DataFrame, ack: pd.DataFrame, tol: float = 1e-9) -> pd.DataFrame:
    """Return one row per break.

    internal: columns transaction_ref, quantity, price
    ack:      columns transaction_ref, status (ACPT/RJCT), quantity, price, [reason]
    Break types: missing_in_ack, unexpected_in_ack, rejected, quantity_mismatch, price_mismatch.
    """
    m = internal.merge(ack, on=KEY, how="outer", suffixes=("_int", "_ack"), indicator=True)
    rows: list[dict] = []
    for _, r in m.iterrows():
        ref = r[KEY]
        if r["_merge"] == "left_only":
            rows.append({KEY: ref, "break": "missing_in_ack", "detail": ""})
        elif r["_merge"] == "right_only":
            rows.append({KEY: ref, "break": "unexpected_in_ack", "detail": ""})
        else:
            if r["status"] == "RJCT":
                rows.append({KEY: ref, "break": "rejected", "detail": r.get("reason", "")})
                continue
            if abs(r["quantity_int"] - r["quantity_ack"]) > tol:
                rows.append({KEY: ref, "break": "quantity_mismatch",
                             "detail": f"{r['quantity_int']} vs {r['quantity_ack']}"})
            if abs(r["price_int"] - r["price_ack"]) > tol:
                rows.append({KEY: ref, "break": "price_mismatch",
                             "detail": f"{r['price_int']} vs {r['price_ack']}"})
    return pd.DataFrame(rows, columns=[KEY, "break", "detail"])
