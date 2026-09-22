"""Checksum and format validators for the identifiers used in transaction reports."""

import re

_MIC = re.compile(r"^[A-Z0-9]{4}$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


def _to_digits(s: str) -> str:
    """Map A-Z to 10-35 and keep digits, as ISO 6166 / ISO 17442 require."""
    return "".join(str(int(c, 36)) for c in s)


def isin_valid(isin: str) -> bool:
    """ISO 6166: 2-letter country prefix, 9 alphanumerics, Luhn check digit."""
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
        return False
    total = 0
    for i, ch in enumerate(reversed(_to_digits(isin))):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            d = d - 9 if d > 9 else d
        total += d
    return total % 10 == 0


def lei_valid(lei: str) -> bool:
    """ISO 17442: 20 alphanumerics, ISO 7064 mod 97-10 (the whole string mod 97 == 1)."""
    if not re.fullmatch(r"[A-Z0-9]{18}[0-9]{2}", lei):
        return False
    return int(_to_digits(lei)) % 97 == 1


def mic_valid(mic: str) -> bool:
    """Format only (4 alphanumerics). Membership in the ISO 10383 list is not checked."""
    return bool(_MIC.fullmatch(mic))


def country_valid(code: str) -> bool:
    return bool(_COUNTRY.fullmatch(code))


def currency_valid(code: str) -> bool:
    return bool(_CURRENCY.fullmatch(code))
