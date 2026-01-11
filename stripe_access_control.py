"""Access control middleware for tier-gated resources."""

from functools import wraps
from fastapi import HTTPException, Request
from stripe_db import Subscription, AccessLog


async def require_subscription(required_access: list):
    """Decorator to gate endpoints by subscription tier.
    
    Args:
        required_access: List of required features (e.g., ["cheatsheet", "commentary"])
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request, **kwargs):
            # Get user ID from request (from JWT token or session)
            user_id = request.headers.get("X-User-ID")
            if not user_id:
                raise HTTPException(status_code=401, detail="User ID required")
            
            # Get user's tier
            tier = Subscription.get_tier(user_id)
            if not tier:
                raise HTTPException(status_code=403, detail="No active subscription")
            
            # Check access
            tier_access = {
                "starter": ["cheatsheet"],
                "pro": ["cheatsheet", "commentary", "correlations"],
                "whale": ["cheatsheet", "commentary", "correlations", "telegram_alerts", "live_updates"],
            }
            
            user_features = tier_access.get(tier, [])
            
            for feature in required_access:
                if feature not in user_features:
                    raise HTTPException(
                        status_code=403, 
                        detail=f"Feature '{feature}' requires {feature} tier"
                    )
            
            # Log access
            resource = "_".join(required_access)
            AccessLog.record(user_id, resource)
            
            # Add tier to request context
            request.state.user_id = user_id
            request.state.tier = tier
            
            return await func(*args, request=request, **kwargs)
        
        return wrapper
    return decorator


def check_tier_access(tier: str, required_feature: str) -> bool:
    """Check if tier has access to feature."""
    tier_access = {
        "starter": ["cheatsheet"],
        "pro": ["cheatsheet", "commentary", "correlations"],
        "whale": ["cheatsheet", "commentary", "correlations", "telegram_alerts", "live_updates"],
    }
    return required_feature in tier_access.get(tier, [])


def get_available_features(tier: str) -> list:
    """Get all available features for a tier."""
    tier_access = {
        "starter": ["cheatsheet"],
        "pro": ["cheatsheet", "commentary", "correlations"],
        "whale": ["cheatsheet", "commentary", "correlations", "telegram_alerts", "live_updates"],
    }
    return tier_access.get(tier, [])
