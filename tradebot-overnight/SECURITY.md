# Security and responsible publication

This project can connect to a brokerage account and database. A secret leak or configuration
mistake can therefore have financial consequences even when the code is intended for paper
trading.

## Secrets

Keep all real values in `.env`, which is ignored by Git. `.env.example` must contain placeholders
only. In particular, never commit or paste:

- Interactive Brokers usernames, passwords, account numbers, session files, or 2FA material;
- PostgreSQL passwords or connection strings containing them;
- Telegram bot tokens or chat identifiers;
- VNC passwords, private keys, cookies, logs, screenshots, or database/data volumes.

Before every public push, inspect staged files and run a secret scanner such as
[`gitleaks`](https://github.com/gitleaks/gitleaks):

```bash
git diff --cached --name-only
git diff --cached
gitleaks git --redact
```

The final manual review matters: automated scanners can miss credentials and can also flag the
intentional dummy account `DU1234567` used by tests and examples.

If a credential ever enters Git history, assume it is compromised. Revoke or rotate it first,
then clean the history. Deleting the working-tree file is not sufficient.

## Broker safety

- Use a dedicated IBKR paper account and keep `IB_MODE=paper`.
- Keep the kill switch engaged except during a supervised paper test.
- Confirm account type, account base currency, contract resolution, market hours, open orders,
  order type, quantity, and the per-order notional cap.
- The strategy is not validated for live trading. Late-fill persistence, cancellation handling,
  automatic FX cash conversion, slippage, commissions, tax, and emergency recovery are incomplete
  or deliberately out of scope.

## Reporting a vulnerability

Do not open a public issue containing credentials, account details, proprietary market data, or
an exploitable broker-control path. Contact the repository owner privately and include only the
minimum information needed to reproduce the problem.
