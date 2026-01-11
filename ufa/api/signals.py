"""
Signals API endpoint with subscription-gated access and exposure-safe parlays.
"""
import json
from pathlib import Path
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from ufa.db import SessionLocal
from ufa.models.user import User, Plan, Signal, SignalView, PlanTier
from ufa.api.auth import (
    get_current_user, 
    get_current_user_optional,
    get_user_tier,
    check_daily_limit,
    increment_usage,
)
from ufa.signals.shaper import SignalShaper
from engine.exposure import ExposureGovernor, ExposureConfig, Signal as ExposureSignal

router = APIRouter(prefix="/signals", tags=["signals"])

SIGNALS_FILE = Path("output/signals_latest.json")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SignalOut(BaseModel):
    player: str
    team: str
    stat: str
    line: float
    direction: str
    tier: str
    probability: Optional[float] = None
    stability_score: Optional[float] = None
    stability_class: Optional[str] = None
    edge: Optional[float] = None
    ollama_notes: Optional[str] = None
    delayed: bool = False
    delayed_until: Optional[str] = None
    message: Optional[str] = None


class ParlayLeg(BaseModel):
    player: str
    team: str
    stat: str
    line: float
    direction: str
    probability: float


class ParlayOut(BaseModel):
    leg_count: int
    base_probability: float
    adjusted_probability: float
    diversity_score: float
    unique_teams: int
    legs: List[ParlayLeg]


class SignalsResponse(BaseModel):
    date: str
    total_signals: int
    signals_shown: int
    signals: List[SignalOut]
    remaining_today: int
    tier: str


class ParlaysResponse(BaseModel):
    parlays: List[ParlayOut]
    remaining_today: int


def load_signals() -> list[dict]:
    """Load latest signals from file."""
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Try alternate paths
    output_dir = Path("output")
    if output_dir.exists():
        json_files = sorted(output_dir.glob("signals_*.json"), reverse=True)
        if json_files:
            with open(json_files[0], "r", encoding="utf-8") as f:
                return json.load(f)
    
    return []


def filter_signals_for_tier(signals: list[dict], tier: PlanTier, limit: int) -> list[dict]:
    """Filter signals based on user tier and limit."""
    if tier == PlanTier.FREE:
        # Free users only see SLAM signals
        slam_signals = [s for s in signals if s.get("tier") == "SLAM"]
        return slam_signals[:limit]
    elif tier == PlanTier.STARTER:
        # Starter sees SLAM and STRONG
        good_signals = [s for s in signals if s.get("tier") in ["SLAM", "STRONG"]]
        return good_signals[:limit]
    else:
        # Pro and Whale see all
        return signals[:limit]


def format_signal_for_tier(signal: dict, tier: PlanTier, plan: Plan) -> SignalOut:
    """Format signal with tier-appropriate fields using SignalShaper."""
    shaped = SignalShaper.shape(signal, tier)
    
    # Convert to SignalOut, only including fields that are present
    return SignalOut(
        player=shaped.get("player", ""),
        team=shaped.get("team", ""),
        stat=shaped.get("stat", ""),
        line=shaped.get("line", 0),
        direction=shaped.get("direction", ""),
        tier=shaped.get("tier", ""),
        probability=shaped.get("probability"),
        stability_score=shaped.get("stability_score"),
        stability_class=shaped.get("stability_class"),
        edge=shaped.get("edge"),
        ollama_notes=shaped.get("ollama_notes"),
        delayed=shaped.get("delayed", False),
        delayed_until=shaped.get("delayed_until"),
        message=shaped.get("message"),
    )


@router.get("/", response_model=SignalsResponse)
async def get_signals(
    user: User = Depends(check_daily_limit("signals")),
    db: Session = Depends(get_db),
):
    """Get today's signals based on subscription tier."""
    tier = get_user_tier(user, db)
    
    plan = None
    limit = 1
    if user.subscription:
        plan = db.execute(
            select(Plan).where(Plan.id == user.subscription.plan_id)
        ).scalar_one_or_none()
        
        if plan:
            # Calculate remaining
            used = user.subscription.signals_viewed_today
            limit = plan.daily_signals if plan.daily_signals != -1 else 100
            remaining = max(0, limit - used) if limit != -1 else 100
        else:
            remaining = 0
    else:
        remaining = 0
    
    # Load and filter signals
    all_signals = load_signals()
    filtered = filter_signals_for_tier(all_signals, tier, remaining)
    
    # Format for response
    formatted = [
        format_signal_for_tier(s, tier, plan) for s in filtered
    ]
    
    # Track views and increment usage
    for _ in filtered:
        increment_usage(user, "signals", db)
    
    # Recalculate remaining after increment
    user.subscription.reset_daily_limits() if user.subscription else None
    new_remaining = (
        max(0, limit - user.subscription.signals_viewed_today) 
        if user.subscription and limit != -1 
        else 0
    )
    
    return SignalsResponse(
        date=date.today().isoformat(),
        total_signals=len(all_signals),
        signals_shown=len(formatted),
        signals=formatted,
        remaining_today=new_remaining if limit != -1 else 999,
        tier=tier.value,
    )


@router.get("/parlays", response_model=ParlaysResponse)
async def get_safe_parlays(
    legs: int = 3,
    top_n: int = 3,
    user: User = Depends(check_daily_limit("parlays")),
    db: Session = Depends(get_db),
):
    """Get exposure-safe parlay suggestions."""
    tier = get_user_tier(user, db)
    
    # Only paid users can access parlays
    if tier == PlanTier.FREE:
        raise HTTPException(
            status_code=403,
            detail="Parlay suggestions require a paid subscription. Upgrade to access!",
        )
    
    # Load signals
    all_signals = load_signals()
    if not all_signals:
        raise HTTPException(status_code=404, detail="No signals available")
    
    # Convert to exposure Signal objects
    exposure_signals = [
        ExposureSignal(
            player=s.get("player", ""),
            team=s.get("team", ""),
            opponent=s.get("opponent", ""),
            stat=s.get("stat", ""),
            line=s.get("line", 0),
            direction=s.get("direction", "higher"),
            probability=s.get("probability", 0),
            tier=s.get("tier", ""),
        )
        for s in all_signals
    ]
    
    # Find optimal parlays
    governor = ExposureGovernor()
    optimal = governor.find_optimal_parlays(
        exposure_signals,
        leg_count=legs,
        top_n=top_n,
        min_probability=0.4,
    )
    
    if not optimal:
        raise HTTPException(
            status_code=404, 
            detail=f"No valid {legs}-leg parlays found with current signals",
        )
    
    # Format response
    parlays = [
        ParlayOut(
            leg_count=p["leg_count"],
            base_probability=p["base_probability"],
            adjusted_probability=p["adjusted_probability"],
            diversity_score=p["diversity_score"],
            unique_teams=p["unique_teams"],
            legs=[
                ParlayLeg(
                    player=leg["player"],
                    team=leg["team"],
                    stat=leg["stat"],
                    line=leg["line"],
                    direction=leg["direction"],
                    probability=leg["probability"],
                )
                for leg in p["legs"]
            ],
        )
        for p in optimal
    ]
    
    # Increment usage
    increment_usage(user, "parlays", db)
    
    # Get remaining
    plan = db.execute(
        select(Plan).where(Plan.id == user.subscription.plan_id)
    ).scalar_one_or_none() if user.subscription else None
    
    limit = plan.max_parlays if plan else 0
    used = user.subscription.parlays_viewed_today if user.subscription else 0
    remaining = max(0, limit - used) if limit != -1 else 999
    
    return ParlaysResponse(
        parlays=parlays,
        remaining_today=remaining,
    )


@router.get("/stats")
async def get_signal_stats(db: Session = Depends(get_db)):
    """Get public stats about signal performance (for marketing)."""
    from ufa.models.user import DailyMetrics, SignalResult
    from datetime import timedelta
    
    # Get last 30 days of metrics
    cutoff = date.today() - timedelta(days=30)
    
    # Count graded signals
    graded = db.execute(
        select(Signal).where(Signal.result != SignalResult.PENDING)
    ).scalars().all()
    
    if not graded:
        return {
            "period": "30 days",
            "total_picks": 0,
            "win_rate": 0,
            "slam_win_rate": 0,
            "message": "Building track record...",
        }
    
    total = len(graded)
    wins = sum(1 for s in graded if s.result == SignalResult.WIN)
    losses = sum(1 for s in graded if s.result == SignalResult.LOSS)
    
    slam_signals = [s for s in graded if s.tier == "SLAM"]
    slam_wins = sum(1 for s in slam_signals if s.result == SignalResult.WIN)
    slam_total = len([s for s in slam_signals if s.result != SignalResult.PENDING])
    
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    slam_rate = (slam_wins / slam_total * 100) if slam_total > 0 else 0
    
    return {
        "period": "30 days",
        "total_picks": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "slam_picks": len(slam_signals),
        "slam_win_rate": round(slam_rate, 1),
    }
