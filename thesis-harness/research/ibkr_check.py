"""Read-only IBKR smoke test: connection, account, and every portfolio symbol. Places no orders.

Usage (gateway up, port published on the host):
    uv run python research/ibkr_check.py
"""

from __future__ import annotations

import sys

from tradebot.broker.ibkr import IBKRBroker, contract_for
from tradebot.config import settings
from tradebot.instruments import INSTRUMENTS
from tradebot.portfolio import parse_weights


def main() -> int:
    broker = IBKRBroker()
    print(f"connecting to {settings.ib_host}:{settings.ib_port} (mode={settings.ib_mode}) ...")
    broker.connect()
    ib = broker.ib
    accounts = ib.managedAccounts()
    print(f"connected. accounts: {[a[:2] + '***' for a in accounts]}")

    if settings.ib_mode == "paper" and not all(a.startswith("DU") for a in accounts):
        print("REFUSING TO CONTINUE: IB_MODE=paper but the account is not a paper (DU...) account")
        broker.disconnect()
        return 2

    rows = [r for r in ib.accountSummary() if r.tag == "NetLiquidation"]
    for r in rows:
        print(f"NetLiquidation: {r.value} {r.currency}")
    print(f"base currency setting: {settings.base_currency}")
    print(f"open positions: {[(p.symbol, p.qty) for p in broker.positions()]}")

    failures = 0
    print("\nsymbol   conId      exchange   ccy   last(native)  fx->base  last(base)")
    for symbol in parse_weights(settings.target_weights):
        contract = contract_for(symbol)
        if not (ib.qualifyContracts(contract) and contract.conId):
            failures += 1
            print(f"{symbol:8} NOT RESOLVED as {INSTRUMENTS[symbol]}; candidates:")
            for m in ib.reqMatchingSymbols(symbol)[:8]:
                c = m.contract
                print(f"           {c.symbol} | {c.primaryExchange} | {c.currency} | {m.derivativeSecTypes} | {c.secType}")
            continue
        try:
            price = broker.price(symbol)
            fx = broker.fx_rate(contract.currency, settings.base_currency)
        except Exception as exc:  # noqa: BLE001 - a smoke test reports every failure and moves on
            failures += 1
            print(f"{symbol:8} {contract.conId:<10} {contract.primaryExchange:10} {contract.currency:5} ERROR {exc}")
            continue
        base = f"{price * fx:.2f}" if price is not None else "-"
        print(
            f"{symbol:8} {contract.conId:<10} {contract.primaryExchange:10} {contract.currency:5} "
            f"{price if price is not None else '-':<13} {fx:<9.4f} {base}"
        )
        if price is None:
            failures += 1

    try:
        broker.check_setup(parse_weights(settings.target_weights))
        print("\ncheck_setup(): OK")
    except RuntimeError as exc:
        failures += 1
        print(f"\ncheck_setup(): FAILED\n{exc}")

    broker.disconnect()
    print(f"\n{'ALL GOOD' if failures == 0 else f'{failures} problem(s) above'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
