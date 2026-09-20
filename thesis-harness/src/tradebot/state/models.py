"""SQLAlchemy models for orders, fills, positions and NAV snapshots.

PURPOSE: SQLAlchemy models for orders, fills, positions and NAV snapshots.
INPUTS:  -
OUTPUTS: declarative Base and tables (schema managed by Alembic migrations).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
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
