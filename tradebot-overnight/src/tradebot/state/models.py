from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OrderRecord(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    order_type: Mapped[str] = mapped_column(String, default="MKT")
    status: Mapped[str] = mapped_column(String, default="submitted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    fills: Mapped[list[FillRecord]] = relationship(back_populates="order")


class FillRecord(Base):
    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[OrderRecord] = relationship(back_populates="fills")


class PositionRecord(Base):
    __tablename__ = "positions"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    avg_price: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NavSnapshot(Base):
    __tablename__ = "nav_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nav: Mapped[float] = mapped_column(Float, nullable=False)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OvernightDay(Base):
    """One row per trading day of the overnight strategy. It is the idempotency record: the
    random decision time is drawn once and stored, and every order is preceded by a
    'submitting' status so a crash or restart can never place the same order twice."""

    __tablename__ = "overnight_days"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    decision_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action: Mapped[str | None] = mapped_column(String)  # PLAN_BUY_CLOSE | STAY_CASH | MISSED
    qty: Mapped[int | None] = mapped_column(Integer)  # planned shares
    entry_status: Mapped[str] = mapped_column(String, default="none")
    entry_filled: Mapped[float] = mapped_column(Float, default=0.0)
    exit_status: Mapped[str] = mapped_column(String, default="none")
    exit_filled: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str | None] = mapped_column(String)
