"""
CBB Live Dashboard State
-------------------------
Expose real-time system state for observability.
Read-only, non-mutating. Enables auditing of live decisions.

Core Gauges:
- Pace Ratio: Actual vs expected possessions
- Fouls/Min: Ref + game control signal
- Foul-Out Risk: Top 2 players rotation collapse risk
- Variance Mult: Active variance governor
- Lock Status: NORMAL / UNDERS_ONLY / 2H_ONLY
- Hedge Active: Yes / No
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


# Dashboard state file
STATE_FILE = Path(__file__).parent.parent / "runs" / "dashboard_state.json"


# In-memory state (authoritative)
DASHBOARD_STATE: Dict[str, Any] = {
    # Pace metrics
    "pace_ratio": None,
    "expected_pace": None,
    "actual_pace": None,
    
    # Foul metrics
    "fouls_per_min": None,
    "baseline_fouls": None,
    "foul_rate_mult": None,
    
    # Foul-out risk
    "top_foulout_probs": [],
    "foulout_lock_triggered": False,
    
    # Variance governor
    "variance_mult": 1.0,
    "confidence_cap": None,
    "governor_source": None,  # e.g., "seed_ref_coach"
    
    # Mode/status
    "mode": "NORMAL",  # NORMAL, UNDERS_ONLY, 2H_ONLY, HALTED
    "second_half_only": False,
    "ladder_step": None,  # PREGAME, HALF_TIME, SECOND_HALF
    
    # Hedge
    "hedge_active": False,
    "hedge_units": 0.0,
    "hedge_target": None,
    
    # Session
    "game_id": None,
    "elapsed_minutes": 0.0,
    "score_margin": 0,
    
    # Meta
    "timestamp": None,
    "last_trigger": None
}


def update_dashboard(**kwargs) -> Dict[str, Any]:
    """
    Update dashboard state with new values.
    
    Only updates keys that exist in DASHBOARD_STATE.
    Auto-updates timestamp.
    
    Args:
        **kwargs: Key-value pairs to update
    
    Returns:
        Updated state dict
    """
    for k, v in kwargs.items():
        if k in DASHBOARD_STATE:
            DASHBOARD_STATE[k] = v
    
    DASHBOARD_STATE["timestamp"] = datetime.now().isoformat()
    
    return DASHBOARD_STATE.copy()


def get_dashboard_state() -> Dict[str, Any]:
    """Get current dashboard state."""
    return DASHBOARD_STATE.copy()


def persist_dashboard() -> None:
    """Write dashboard state to JSON file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(DASHBOARD_STATE, f, indent=2, default=str)


def load_dashboard() -> Dict[str, Any]:
    """Load dashboard state from JSON file."""
    global DASHBOARD_STATE
    
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            loaded = json.load(f)
            for k, v in loaded.items():
                if k in DASHBOARD_STATE:
                    DASHBOARD_STATE[k] = v
    
    return DASHBOARD_STATE.copy()


def reset_dashboard() -> Dict[str, Any]:
    """Reset dashboard to default state."""
    global DASHBOARD_STATE
    
    DASHBOARD_STATE = {
        "pace_ratio": None,
        "expected_pace": None,
        "actual_pace": None,
        "fouls_per_min": None,
        "baseline_fouls": None,
        "foul_rate_mult": None,
        "top_foulout_probs": [],
        "foulout_lock_triggered": False,
        "variance_mult": 1.0,
        "confidence_cap": None,
        "governor_source": None,
        "mode": "NORMAL",
        "second_half_only": False,
        "ladder_step": None,
        "hedge_active": False,
        "hedge_units": 0.0,
        "hedge_target": None,
        "game_id": None,
        "elapsed_minutes": 0.0,
        "score_margin": 0,
        "timestamp": None,
        "last_trigger": None
    }
    
    return DASHBOARD_STATE.copy()


# === HOOK FUNCTIONS (for integration) ===

def hook_live_monitor(live: Dict) -> None:
    """Hook for live monitor updates."""
    update_dashboard(
        pace_ratio=live.get("pace_ratio"),
        fouls_per_min=live.get("fouls_per_min"),
        baseline_fouls=live.get("baseline_fouls"),
        elapsed_minutes=live.get("elapsed_minutes", 0),
        score_margin=live.get("score_margin", 0),
        game_id=live.get("game_id")
    )
    
    # Compute foul rate multiplier
    if live.get("baseline_fouls") and live.get("fouls_per_min"):
        mult = live["fouls_per_min"] / live["baseline_fouls"]
        update_dashboard(foul_rate_mult=round(mult, 3))


def hook_foulout_engine(foul_probs: List[float], lock_triggered: bool) -> None:
    """Hook for foul-out engine updates."""
    # Keep top 2
    top_probs = sorted(foul_probs, reverse=True)[:2]
    
    update_dashboard(
        top_foulout_probs=[round(p, 3) for p in top_probs],
        foulout_lock_triggered=lock_triggered
    )
    
    if lock_triggered:
        update_dashboard(
            last_trigger="FOULOUT_RISK"
        )


def hook_variance_governor(variance: float, confidence: float, source: str) -> None:
    """Hook for variance governor updates."""
    update_dashboard(
        variance_mult=round(variance, 3),
        confidence_cap=round(confidence, 3),
        governor_source=source
    )


def hook_mode_change(mode: str, second_half_only: bool = False) -> None:
    """Hook for mode/status changes."""
    update_dashboard(
        mode=mode,
        second_half_only=second_half_only
    )
    
    if mode != "NORMAL":
        update_dashboard(last_trigger=f"MODE_{mode}")


def hook_ladder_step(step: Optional[str]) -> None:
    """Hook for ladder step updates."""
    update_dashboard(ladder_step=step)


def hook_hedge(active: bool, units: float = 0.0, target: Optional[str] = None) -> None:
    """Hook for hedge updates."""
    update_dashboard(
        hedge_active=active,
        hedge_units=round(units, 2),
        hedge_target=target
    )


# === CLI OUTPUT ===

def print_dashboard() -> None:
    """Print dashboard state to CLI."""
    state = get_dashboard_state()
    
    print("\n" + "=" * 60)
    print("📊 CBB LIVE DASHBOARD")
    print("=" * 60)
    
    print(f"\n🎮 Game: {state['game_id'] or 'N/A'}")
    print(f"⏱  Elapsed: {state['elapsed_minutes']:.1f} min")
    print(f"📍 Margin: {state['score_margin']}")
    
    print(f"\n📈 PACE")
    print(f"   Ratio: {state['pace_ratio'] or 'N/A'}")
    
    print(f"\n🚨 FOULS")
    print(f"   Per Min: {state['fouls_per_min'] or 'N/A'}")
    print(f"   Rate Mult: {state['foul_rate_mult'] or 'N/A'}")
    print(f"   Top Foul-Out: {state['top_foulout_probs']}")
    print(f"   Lock Triggered: {'[!] YES' if state['foulout_lock_triggered'] else 'No'}")
    
    print(f"\n📊 VARIANCE GOVERNOR")
    print(f"   Multiplier: {state['variance_mult']}")
    print(f"   Conf Cap: {state['confidence_cap'] or 'N/A'}")
    print(f"   Source: {state['governor_source'] or 'N/A'}")
    
    print(f"\n🔒 STATUS")
    mode_emoji = {"NORMAL": "✅", "UNDERS_ONLY": "🔸", "2H_ONLY": "🔹", "HALTED": "🛑"}
    print(f"   Mode: {mode_emoji.get(state['mode'], '❓')} {state['mode']}")
    print(f"   2H Only: {'Yes' if state['second_half_only'] else 'No'}")
    print(f"   Ladder Step: {state['ladder_step'] or 'N/A'}")
    
    print(f"\n🛡️ HEDGE")
    print(f"   Active: {'Yes' if state['hedge_active'] else 'No'}")
    if state['hedge_active']:
        print(f"   Units: {state['hedge_units']}u")
        print(f"   Target: {state['hedge_target']}")
    
    print(f"\n⏰ Last Update: {state['timestamp'] or 'N/A'}")
    print(f"📌 Last Trigger: {state['last_trigger'] or 'N/A'}")
    print("=" * 60 + "\n")


# === JSON STREAM ===

def stream_dashboard_json() -> str:
    """Return dashboard state as JSON string."""
    return json.dumps(get_dashboard_state(), indent=2, default=str)
