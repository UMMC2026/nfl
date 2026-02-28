"""UFA database models and subscription tiers.

Several runtime components (Telegram bot, API, and results tracker) expect
`ufa.models.user` to provide:

- Plan/subscription tiers (PlanTier)
- SQLAlchemy ORM models (User, Plan, Subscription, Signal, SignalView, DailyMetrics)
- Seed helper (seed_plans)

The unit tests in ./tests also import PlanTier for signal shaping.
"""

from __future__ import annotations

from enum import Enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ufa.db import Base


class PlanTier(str, Enum):
    """Subscription tiers for payload shaping and feature gating."""

    FREE = "FREE"
    STARTER = "STARTER"
    PRO = "PRO"
    WHALE = "WHALE"

    @classmethod
    def from_value(cls, value: str | None) -> "PlanTier":
        if value is None:
            return cls.FREE
        s = str(value).strip().upper()
        for tier in cls:
            if tier.value == s:
                return tier
        return cls.FREE


class SignalResult(str, Enum):
    PENDING = "PENDING"
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"
    VOID = "VOID"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(64))
    display_name: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subscription: Mapped[Optional["Subscription"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[PlanTier] = mapped_column(SAEnum(PlanTier), nullable=False, index=True)

    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    daily_signals: Mapped[int] = mapped_column(Integer, default=0)  # -1 = unlimited
    max_parlays: Mapped[int] = mapped_column(Integer, default=0)    # -1 = unlimited

    can_view_probabilities: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_ollama_notes: Mapped[bool] = mapped_column(Boolean, default=False)

    max_subscribers: Mapped[Optional[int]] = mapped_column(Integer)
    current_subscribers: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_subscription_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    signals_viewed_today: Mapped[int] = mapped_column(Integer, default=0)
    parlays_viewed_today: Mapped[int] = mapped_column(Integer, default=0)
    last_reset_date: Mapped[date] = mapped_column(Date, default=date.today)

    user: Mapped[User] = relationship(back_populates="subscription")
    plan: Mapped[Plan] = relationship()

    def reset_daily_limits(self) -> None:
        today = date.today()
        if self.last_reset_date != today:
            self.signals_viewed_today = 0
            self.parlays_viewed_today = 0
            self.last_reset_date = today


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player: Mapped[str] = mapped_column(String(128), default="")
    team: Mapped[Optional[str]] = mapped_column(String(16))
    stat: Mapped[str] = mapped_column(String(64), default="")
    line: Mapped[float] = mapped_column(Float, default=0.0)
    direction: Mapped[str] = mapped_column(String(16), default="")
    tier: Mapped[Optional[str]] = mapped_column(String(16))
    probability: Mapped[Optional[float]] = mapped_column(Float)

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    result: Mapped[SignalResult] = mapped_column(SAEnum(SignalResult), default=SignalResult.PENDING)
    graded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class SignalView(Base):
    __tablename__ = "signal_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    signal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("signals.id"))
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyMetrics(Base):
    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, default=date.today, unique=True, index=True)
    total_wins: Mapped[int] = mapped_column(Integer, default=0)
    total_losses: Mapped[int] = mapped_column(Integer, default=0)
    total_picks: Mapped[int] = mapped_column(Integer, default=0)


def seed_plans(db) -> None:
    """Ensure baseline plans exist.

    Safe to call on startup.
    """
    existing = {p.tier for p in db.query(Plan).all()}

    def add_if_missing(tier: PlanTier, **kwargs):
        if tier in existing:
            return
        db.add(Plan(tier=tier, **kwargs))

    add_if_missing(
        PlanTier.FREE,
        name="Free",
        price_cents=0,
        daily_signals=0,
        max_parlays=0,
        can_view_probabilities=False,
        can_view_ollama_notes=False,
        is_active=True,
    )
    add_if_missing(
        PlanTier.STARTER,
        name="Starter",
        price_cents=1999,
        daily_signals=5,
        max_parlays=1,
        can_view_probabilities=True,
        can_view_ollama_notes=False,
        is_active=True,
    )
    add_if_missing(
        PlanTier.PRO,
        name="Pro",
        price_cents=4999,
        daily_signals=15,
        max_parlays=3,
        can_view_probabilities=True,
        can_view_ollama_notes=True,
        is_active=True,
    )
    add_if_missing(
        PlanTier.WHALE,
        name="Whale",
        price_cents=19999,
        daily_signals=-1,
        max_parlays=-1,
        can_view_probabilities=True,
        can_view_ollama_notes=True,
        is_active=True,
    )

    db.commit()

