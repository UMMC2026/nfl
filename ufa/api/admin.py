"""
Admin operations for user and subscription management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from ufa.db import SessionLocal
from ufa.models.user import User, PlanTier
from ufa.billing.subscriptions import update_user_subscription
from ufa.api.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(user: User = Depends(get_current_user)):
    """Verify user is admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


class SetUserTierRequest(BaseModel):
    tier: str  # "free", "starter", "pro", "whale"
    reason: str = ""  # Optional audit log


class SetUserTierResponse(BaseModel):
    user_id: int
    tier: str
    status: str


@router.post("/users/{user_id}/tier", response_model=SetUserTierResponse)
async def set_user_tier(
    user_id: int,
    request: SetUserTierRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Set user tier directly (admin override).
    
    Useful for:
    - Support/refunds
    - Promo codes
    - Testing
    
    Usage: POST /admin/users/5/tier
    {
      "tier": "pro",
      "reason": "Promo code EARLY50"
    }
    """
    # Validate tier
    valid_tiers = ["free", "starter", "pro", "whale"]
    if request.tier not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier. Must be one of: {valid_tiers}",
        )
    
    tier = PlanTier(request.tier)
    
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    
    # Update subscription
    update_user_subscription(
        user_id=user_id,
        tier=tier,
        status="active",
        subscription_id=None,
        period_end=None,
    )
    
    return SetUserTierResponse(
        user_id=user_id,
        tier=request.tier,
        status="updated",
    )


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get detailed user info for admin panel."""
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "telegram_id": user.telegram_id,
        "telegram_username": user.telegram_username,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "created_at": user.created_at,
        "subscription": {
            "plan_id": user.subscription.plan_id if user.subscription else None,
            "plan_name": user.subscription.plan.name if user.subscription else "None",
            "tier": user.subscription.plan.tier.value if user.subscription else "free",
            "status": user.subscription.status if user.subscription else "none",
            "stripe_subscription_id": user.subscription.stripe_subscription_id if user.subscription else None,
            "expires_at": user.subscription.expires_at if user.subscription else None,
        } if user.subscription else None,
    }
