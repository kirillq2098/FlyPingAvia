from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    watches: Mapped[list["Watch"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Watch(Base):
    __tablename__ = "watches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))
    origin_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    destination_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # Коды для поиска через запятую (город + аэропорты)
    origin_search: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    destination_search: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_price: Mapped[float] = mapped_column(Float)
    depart_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    last_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_origin_airport: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    last_destination_airport: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_alert_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="watches")

    @property
    def origin_label(self) -> str:
        if self.origin_name:
            return f"{self.origin_name} ({self.origin})"
        return self.origin

    @property
    def destination_label(self) -> str:
        if self.destination_name:
            return f"{self.destination_name} ({self.destination})"
        return self.destination

    @property
    def origin_codes(self) -> list[str]:
        if self.origin_search:
            return [c.strip().upper() for c in self.origin_search.split(",") if c.strip()]
        return [self.origin.upper()]

    @property
    def destination_codes(self) -> list[str]:
        if self.destination_search:
            return [c.strip().upper() for c in self.destination_search.split(",") if c.strip()]
        return [self.destination.upper()]

    @property
    def route_label(self) -> str:
        date_part = self.depart_date.isoformat() if self.depart_date else "любая дата"
        return f"{self.origin_label} → {self.destination_label} ({date_part})"
