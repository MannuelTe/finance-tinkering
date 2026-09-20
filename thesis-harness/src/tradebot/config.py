"""Runtime settings.

PURPOSE: typed configuration for broker, database, risk, notifications and runner.
INPUTS:  environment variables / .env (see .env.example).
OUTPUTS: the `settings` singleton.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Broker / IBKR Gateway
    ib_host: str = "127.0.0.1"
    ib_port: int = 4002
    ib_client_id: int = 1
    ib_mode: Literal["paper", "live"] = "paper"

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/tradebot"

    # Data store (parquet). Defaults to the container mount from docker-compose;
    # override to a local path (e.g. ./data) when running outside Docker.
    data_dir: str = "/data"

    # Account base currency. NAV, the notional cap and all sizing are in this currency; the
    # IBKR account must actually be denominated in it (checked at startup).
    base_currency: str = "CAD"

    # Risk
    # Per-order cap, in the account's base currency.
    max_notional: Decimal = Decimal(500)
    kill_switch: bool = False

    # Notifications
    telegram_token: str | None = None
    telegram_chat_id: str | None = None

    # Target portfolio for the runner, as "SYMBOL:WEIGHT,..." (weights are fractions of NAV).
    # Empty means the runner refuses to start. Symbols must be in tradebot.instruments.
    target_weights: str = ""

    # Runner
    poll_interval_seconds: int = 300


settings = Settings()
