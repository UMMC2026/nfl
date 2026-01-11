"""
Subscription state management and updates.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from ufa.models.user import User, Subscription, Plan, PlanTier
from ufa.db import SessionLocal


def get_db_session() -> Session:
    """Get a database session."""
    return SessionLocal()


def update_user_subscription(
    user_id: int,
    tier: PlanTier,
    status: str,
    subscription_id: str | None = None,
    period_end: int | None = None,
    customer_id: str | None = None,
) -> Subscription:
    """
    Update user's subscription state atomically.
    
    Args:
        user_id: User ID
        tier: New tier (FREE, STARTER, PRO, WHALE)
        status: Subscription status (active, past_due, canceled)
        subscription_id: Stripe subscription ID
        period_end: Unix timestamp of current period end
        customer_id: Stripe customer ID
    
    Returns:
        Updated Subscription object
    """
    db = get_db_session()
    try:
        user = db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Get or create subscription
        sub = db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        ).scalar_one_or_none()
        
        if not sub:
            # Find plan for this tier
            plan = db.execute(
                select(Plan).where(Plan.tier == tier)
            ).scalar_one_or_none()
            
            if not plan:
                raise ValueError(f"No plan found for tier {tier}")
            
            sub = Subscription(user_id=user_id, plan_id=plan.id)
            db.add(sub)
        else:
            # Update plan if tier changed
            if tier != sub.plan.tier:
                new_plan = db.execute(
                    select(Plan).where(Plan.tier == tier)
                ).scalar_one_or_none()
                
                if new_plan:
                    sub.plan_id = new_plan.id
        
        # Update subscription state
        sub.status = status
        sub.stripe_subscription_id = subscription_id
        if customer_id:
            sub.stripe_customer_id = customer_id
        
        if period_end:
            sub.expires_at = datetime.fromtimestamp(period_end)
        
        if status == "canceled":
            sub.canceled_at = datetime.utcnow()
        
        db.commit()
        db.refresh(sub)
        return sub
    finally:
        db.close()


def get_user_subscription(user_id: int) -> Subscription | None:
    """Get user's current subscription."""
    db = get_db_session()
    try:
        return db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        ).scalar_one_or_none()
    finally:
        db.close()


def get_user_tier(user_id: int) -> PlanTier:
    """Get user's current tier based on subscription."""
    sub = get_user_subscription(user_id)
    if sub and sub.is_active:
        return sub.plan.tier
    return PlanTier.FREE
