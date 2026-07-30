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
    return_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    adults: Mapped[int] = mapped_column(Integer, default=1)
    children: Mapped[int] = mapped_column(Integer, default=0)
    infants: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    # CS-07 MVP: ширина окна вокруг depart_date (0 | 1 | 3 | 7)
    flexibility_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_origin_airport: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    last_destination_airport: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_alert_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="watches")
    alert_events: Mapped[list["AlertEvent"]] = relationship(
        back_populates="watch",
        cascade="all, delete-orphan",
    )

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
    def is_round_trip(self) -> bool:
        return self.return_date is not None

    @property
    def passengers_label(self) -> str:
        parts = [f"взр. {self.adults}"]
        if self.children:
            parts.append(f"дет. {self.children}")
        if self.infants:
            parts.append(f"мл. {self.infants}")
        return ", ".join(parts)

    @property
    def route_label(self) -> str:
        months = (
            "янв", "фев", "мар", "апр", "мая", "июн",
            "июл", "авг", "сен", "окт", "ноя", "дек",
        )

        def _d(value: Optional[date]) -> str:
            if not value:
                return "любая дата"
            return f"{value.day} {months[value.month - 1]}"

        if self.is_round_trip:
            date_part = f"{_d(self.depart_date)} → {_d(self.return_date)}, туда-обратно"
        else:
            date_part = f"{_d(self.depart_date)}, в одну сторону"
        return f"{self.origin_label} → {self.destination_label} ({date_part}; {self.passengers_label})"


class AlertEvent(Base):
    """Факт успешной отправки алерта (для NSM Alerted Watchers и аналитики)."""

    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watch_id: Mapped[int] = mapped_column(
        ForeignKey("watches.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    price: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    watch: Mapped[Watch] = relationship(back_populates="alert_events")
