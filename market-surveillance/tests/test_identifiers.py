from marketsurv import identifiers as ids


def test_isin():
    assert ids.isin_valid("US0378331005")  # Apple
    assert ids.isin_valid("DE000BAY0017")  # Bayer
    assert not ids.isin_valid("US0378331006")
    assert not ids.isin_valid("US037833100")


def test_lei():
    assert ids.lei_valid("HWUPKR0MPOU8FGXBT394")  # Apple Inc.
    assert not ids.lei_valid("HWUPKR0MPOU8FGXBT395")
    assert not ids.lei_valid("SHORT")


def test_mic_and_codes():
    assert ids.mic_valid("XLON") and ids.mic_valid("XOFF")
    assert not ids.mic_valid("xlon")
    assert ids.currency_valid("EUR") and not ids.currency_valid("EU")
