"""FastAPI routes for serving tier-gated analysis files."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path
from stripe_db import Subscription, AccessLog
from stripe_access_control import check_tier_access, get_available_features
import os
from datetime import datetime

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/cheatsheet")
async def get_cheatsheet(request: Request):
    """Get daily cheatsheet (all tiers have access)."""
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    
    tier = Subscription.get_tier(user_id)
    if not tier:
        raise HTTPException(status_code=403, detail="No active subscription")
    
    if not check_tier_access(tier, "cheatsheet"):
        raise HTTPException(status_code=403, detail="Cheatsheet access denied")
    
    # Log access
    AccessLog.record(user_id, "cheatsheet")
    
    # Find latest cheatsheet file
    cheatsheet_path = find_latest_file("outputs", "cheatsheet")
    if not cheatsheet_path:
        raise HTTPException(status_code=404, detail="No cheatsheet available")
    
    return FileResponse(cheatsheet_path, media_type="text/plain")


@router.get("/commentary")
async def get_commentary(request: Request):
    """Get Ollama commentary (PRO and WHALE only)."""
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    
    tier = Subscription.get_tier(user_id)
    if not tier:
        raise HTTPException(status_code=403, detail="No active subscription")
    
    if not check_tier_access(tier, "commentary"):
        raise HTTPException(status_code=403, detail="Commentary requires PRO or WHALE tier")
    
    AccessLog.record(user_id, "commentary")
    
    commentary_path = find_latest_file("outputs", "commentary")
    if not commentary_path:
        raise HTTPException(status_code=404, detail="No commentary available")
    
    return FileResponse(commentary_path, media_type="text/plain")


@router.get("/correlations")
async def get_correlations(request: Request):
    """Get correlation analysis (PRO and WHALE only)."""
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    
    tier = Subscription.get_tier(user_id)
    if not tier:
        raise HTTPException(status_code=403, detail="No active subscription")
    
    if not check_tier_access(tier, "correlations"):
        raise HTTPException(status_code=403, detail="Correlations requires PRO or WHALE tier")
    
    AccessLog.record(user_id, "correlations")
    
    correlations_path = find_latest_file("outputs", "correlations")
    if not correlations_path:
        raise HTTPException(status_code=404, detail="No correlations available")
    
    return FileResponse(correlations_path, media_type="text/plain")


@router.get("/dashboard")
async def get_dashboard(request: Request):
    """Get user dashboard with available features."""
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    
    tier = Subscription.get_tier(user_id)
    if not tier:
        raise HTTPException(status_code=403, detail="No active subscription")
    
    features = get_available_features(tier)
    
    return {
        "user_id": user_id,
        "tier": tier,
        "available_features": features,
        "cheatsheet_available": "cheatsheet" in features,
        "commentary_available": "commentary" in features,
        "correlations_available": "correlations" in features,
        "telegram_alerts_available": "telegram_alerts" in features,
        "live_updates_available": "live_updates" in features,
    }


def find_latest_file(directory: str, pattern: str) -> Path | None:
    """Find latest file matching pattern in directory.
    
    Args:
        directory: Directory to search
        pattern: Pattern in filename (e.g., "cheatsheet", "commentary")
    
    Returns:
        Path to latest file or None
    """
    output_dir = Path(directory)
    if not output_dir.exists():
        return None
    
    matching_files = list(output_dir.glob(f"*{pattern}*.txt"))
    if not matching_files:
        return None
    
    # Sort by modification time, newest first
    return max(matching_files, key=lambda p: p.stat().st_mtime)
