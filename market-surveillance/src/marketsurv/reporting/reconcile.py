"""Reconcile internal trade records against what an ARM acknowledged."""

import pandas as pd

KEY = "transaction_ref"
INTERNAL_COLUMNS = frozenset({KEY, "quantity", "price"})
ACK_COLUMNS = frozenset({KEY, "status", "quantity", "price"})


def _validate_input(frame: pd.DataFrame, required: frozenset[str], name: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{name} is missing required columns: {', '.join(sorted(missing))}")
    if frame[KEY].isna().any():
        raise ValueError(f"{name} contains a missing transaction reference")
    duplicates = frame[KEY][frame[KEY].duplicated()].dropna().unique()
    if len(duplicates):
        sample = ", ".join(map(str, duplicates[:5]))
        raise ValueError(f"{name} contains duplicate transaction references: {sample}")


def _different(left: object, right: object, tolerance: float) -> bool:
    if pd.isna(left) or pd.isna(right):
        return True
    return abs(left - right) > tolerance


def reconcile(internal: pd.DataFrame, ack: pd.DataFrame, tol: float = 1e-9) -> pd.DataFrame:
    """Return one row per break.

    internal: columns transaction_ref, quantity, price
    ack:      columns transaction_ref, status (ACPT/RJCT), quantity, price, [reason]
    Break types: missing_in_ack, unexpected_in_ack, rejected, quantity_mismatch, price_mismatch.
    """
    if tol < 0:
        raise ValueError("tol must be non-negative")
    _validate_input(internal, INTERNAL_COLUMNS, "internal")
    _validate_input(ack, ACK_COLUMNS, "ack")
    if ack["status"].isna().any():
        raise ValueError("ack contains a missing status")
    invalid_statuses = sorted(set(ack["status"].dropna()) - {"ACPT", "RJCT"})
    if invalid_statuses:
        raise ValueError(
            f"ack contains unsupported statuses: {', '.join(map(str, invalid_statuses))}"
        )
    m = internal.merge(
        ack,
        on=KEY,
        how="outer",
        suffixes=("_int", "_ack"),
        indicator=True,
        validate="one_to_one",
    )
    rows: list[dict[str, object]] = []
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
            if _different(r["quantity_int"], r["quantity_ack"], tol):
                rows.append(
                    {
                        KEY: ref,
                        "break": "quantity_mismatch",
                        "detail": f"{r['quantity_int']} vs {r['quantity_ack']}",
                    }
                )
            if _different(r["price_int"], r["price_ack"], tol):
                rows.append(
                    {
                        KEY: ref,
                        "break": "price_mismatch",
                        "detail": f"{r['price_int']} vs {r['price_ack']}",
                    }
                )
    return pd.DataFrame(rows, columns=[KEY, "break", "detail"])
