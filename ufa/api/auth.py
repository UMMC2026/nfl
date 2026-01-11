"""
JWT Authentication with tier-based access control.
"""
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import select
import os

from ufa.db import SessionLocal
from ufa.models.user import User, Subscription, Plan, PlanTier

router = APIRouter(prefix="/auth", tags=["authentication"])

# Security config
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

bearer_scheme = HTTPBearer(auto_error=False)


# Pydantic models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TelegramAuth(BaseModel):
    telegram_id: str
    telegram_username: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user_id: int
    tier: str


class UserProfile(BaseModel):
    id: int
    email: Optional[str]
    telegram_username: Optional[str]
    display_name: Optional[str]
    tier: str
    plan_name: str
    signals_remaining_today: int
    parlays_remaining_today: int
    subscription_expires: Optional[datetime]

    class Config:
        from_attributes = True


# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Password utilities (SHA256 + salt - simpler than bcrypt, works on Python 3.14)
def get_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((salt + password).encode())
    return f"{salt}${hash_obj.hexdigest()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, stored_hash = hashed_password.split("$")
        hash_obj = hashlib.sha256((salt + plain_password).encode())
        return hash_obj.hexdigest() == stored_hash
    except ValueError:
        return False


# JWT utilities
def create_access_token(user_id: int, tier: str) -> tuple[str, datetime]:
    expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": str(user_id),
        "tier": tier,
        "exp": expires_at,
    }
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token, expires_at


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# Auth dependencies
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    
    payload = decode_token(credentials.credentials)
    user_id = int(payload.get("sub"))
    
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns user if authenticated, None otherwise."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def get_user_tier(user: User, db: Session) -> PlanTier:
    """Get user's current plan tier."""
    if not user.subscription or not user.subscription.is_active:
        return PlanTier.FREE
    
    plan = db.execute(
        select(Plan).where(Plan.id == user.subscription.plan_id)
    ).scalar_one_or_none()
    
    return plan.tier if plan else PlanTier.FREE


def require_tier(min_tier: PlanTier):
    """Dependency factory for tier-gated endpoints."""
    tier_order = [PlanTier.FREE, PlanTier.STARTER, PlanTier.PRO, PlanTier.WHALE]
    min_index = tier_order.index(min_tier)
    
    async def check_tier(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        current_tier = get_user_tier(user, db)
        current_index = tier_order.index(current_tier)
        
        if current_index < min_index:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {min_tier.value} tier or higher. "
                       f"Your current tier: {current_tier.value}",
            )
        return user
    
    return check_tier


def check_daily_limit(limit_type: str):
    """Check if user has remaining daily signals/parlays."""
    async def check_limit(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        if not user.subscription:
            # Create free subscription
            free_plan = db.execute(
                select(Plan).where(Plan.tier == PlanTier.FREE)
            ).scalar_one_or_none()
            
            if free_plan:
                user.subscription = Subscription(
                    user_id=user.id,
                    plan_id=free_plan.id,
                )
                db.add(user.subscription)
                db.commit()
        
        sub = user.subscription
        sub.reset_daily_limits()
        
        plan = db.execute(
            select(Plan).where(Plan.id == sub.plan_id)
        ).scalar_one_or_none()
        
        if not plan:
            raise HTTPException(status_code=500, detail="Plan not found")
        
        if limit_type == "signals":
            limit = plan.daily_signals
            used = sub.signals_viewed_today
        else:  # parlays
            limit = plan.max_parlays
            used = sub.parlays_viewed_today
        
        # -1 means unlimited
        if limit != -1 and used >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily {limit_type} limit reached ({limit}). "
                       f"Upgrade your plan for more access.",
            )
        
        return user
    
    return check_limit


def increment_usage(user: User, limit_type: str, db: Session):
    """Increment daily usage counter after successful access."""
    if user.subscription:
        user.subscription.reset_daily_limits()
        if limit_type == "signals":
            user.subscription.signals_viewed_today += 1
        else:
            user.subscription.parlays_viewed_today += 1
        db.commit()


# Routes
@router.post("/register", response_model=Token)
async def register(data: UserCreate, db: Session = Depends(get_db)):
    """Register new user with email/password."""
    existing = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        display_name=data.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create free subscription
    free_plan = db.execute(
        select(Plan).where(Plan.tier == PlanTier.FREE)
    ).scalar_one_or_none()
    
    if free_plan:
        subscription = Subscription(user_id=user.id, plan_id=free_plan.id)
        db.add(subscription)
        db.commit()
    
    token, expires_at = create_access_token(user.id, PlanTier.FREE.value)
    
    return Token(
        access_token=token,
        expires_at=expires_at,
        user_id=user.id,
        tier=PlanTier.FREE.value,
    )


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: Session = Depends(get_db)):
    """Login with email/password."""
    user = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()
    
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    
    tier = get_user_tier(user, db)
    token, expires_at = create_access_token(user.id, tier.value)
    
    return Token(
        access_token=token,
        expires_at=expires_at,
        user_id=user.id,
        tier=tier.value,
    )


@router.post("/telegram", response_model=Token)
async def telegram_auth(data: TelegramAuth, db: Session = Depends(get_db)):
    """Authenticate via Telegram ID (used by bot)."""
    user = db.execute(
        select(User).where(User.telegram_id == data.telegram_id)
    ).scalar_one_or_none()
    
    if not user:
        # Auto-create user from Telegram
        user = User(
            telegram_id=data.telegram_id,
            telegram_username=data.telegram_username,
            display_name=data.telegram_username or f"User_{data.telegram_id[:8]}",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create free subscription
        free_plan = db.execute(
            select(Plan).where(Plan.tier == PlanTier.FREE)
        ).scalar_one_or_none()
        
        if free_plan:
            subscription = Subscription(user_id=user.id, plan_id=free_plan.id)
            db.add(subscription)
            db.commit()
    
    tier = get_user_tier(user, db)
    token, expires_at = create_access_token(user.id, tier.value)
    
    return Token(
        access_token=token,
        expires_at=expires_at,
        user_id=user.id,
        tier=tier.value,
    )


@router.get("/me", response_model=UserProfile)
async def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user profile with subscription details."""
    tier = get_user_tier(user, db)
    
    plan_name = "Free"
    signals_remaining = 1
    parlays_remaining = 0
    expires_at = None
    
    if user.subscription:
        user.subscription.reset_daily_limits()
        plan = db.execute(
            select(Plan).where(Plan.id == user.subscription.plan_id)
        ).scalar_one_or_none()
        
        if plan:
            plan_name = plan.name
            if plan.daily_signals == -1:
                signals_remaining = 999  # Unlimited
            else:
                signals_remaining = max(0, plan.daily_signals - user.subscription.signals_viewed_today)
            
            if plan.max_parlays == -1:
                parlays_remaining = 999
            else:
                parlays_remaining = max(0, plan.max_parlays - user.subscription.parlays_viewed_today)
        
        expires_at = user.subscription.expires_at
    
    return UserProfile(
        id=user.id,
        email=user.email,
        telegram_username=user.telegram_username,
        display_name=user.display_name,
        tier=tier.value,
        plan_name=plan_name,
        signals_remaining_today=signals_remaining,
        parlays_remaining_today=parlays_remaining,
        subscription_expires=expires_at,
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Issue a fresh JWT with updated tier.
    
    Use this after subscription changes to get latest claims.
    """
    tier = get_user_tier(user, db)
    token, expires_at = create_access_token(user.id, tier.value)
    
    return Token(
        access_token=token,
        expires_at=expires_at,
        user_id=user.id,
        tier=tier.value,
    )