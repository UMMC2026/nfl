"""
CBB Run State Management
-------------------------
Tracks session state, loss streaks, and triggers auto-unders mode.

Key responsibilities:
1. Record edge outcomes (win/loss/push)
2. Detect loss streaks
3. Auto-switch to unders-only after N consecutive losses
4. Manage bankroll policy based on session performance
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Literal


STATE_FILE = Path(__file__).parent / "state.json"


def load_state() -> dict:
    """Load current state from JSON file."""
    if not STATE_FILE.exists():
        return _default_state()
    
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def save_state(state: dict) -> None:
    """Save state to JSON file."""
    state['last_updated'] = datetime.now().isoformat()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def _default_state() -> dict:
    """Return default state structure."""
    return {
        "_notes": "CBB run state for loss tracking and auto-unders switch",
        "last_updated": None,
        "session": {
            "date": None,
            "edges_generated": 0,
            "edges_published": 0,
            "wins": 0,
            "losses": 0,
            "pushes": 0,
            "net_units": 0.0
        },
        "streaks": {
            "current_streak": 0,
            "streak_type": None,
            "max_win_streak": 0,
            "max_loss_streak": 0
        },
        "auto_controls": {
            "unders_only_mode": False,
            "unders_only_triggered_at": None,
            "unders_only_reason": None,
            "consecutive_losses_threshold": 2
        },
        "bankroll": {
            "current_policy": "NORMAL",
            "policy_reason": None,
            "daily_exposure": 0.0,
            "max_daily_exposure": 10.0
        },
        "history": []
    }


def start_session(date: Optional[str] = None) -> dict:
    """Start a new session, resetting daily counters."""
    state = load_state()
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Archive previous session if different date
    if state['session']['date'] and state['session']['date'] != date:
        state['history'].append({
            'date': state['session']['date'],
            'wins': state['session']['wins'],
            'losses': state['session']['losses'],
            'pushes': state['session']['pushes'],
            'net_units': state['session']['net_units']
        })
        # Keep only last 30 days
        state['history'] = state['history'][-30:]
    
    # Reset session
    state['session'] = {
        "date": date,
        "edges_generated": 0,
        "edges_published": 0,
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "net_units": 0.0
    }
    
    # Reset daily bankroll exposure
    state['bankroll']['daily_exposure'] = 0.0
    
    save_state(state)
    return state


def record_edge_generated(count: int = 1) -> dict:
    """Record that edges were generated."""
    state = load_state()
    state['session']['edges_generated'] += count
    save_state(state)
    return state


def record_edge_published(count: int = 1) -> dict:
    """Record that edges were published."""
    state = load_state()
    state['session']['edges_published'] += count
    save_state(state)
    return state


def record_outcome(
    result: Literal['win', 'loss', 'push'],
    units: float = 1.0
) -> dict:
    """
    Record an edge outcome and update streaks.
    
    Args:
        result: 'win', 'loss', or 'push'
        units: Units won/lost (positive for win, negative for loss)
    
    Returns:
        Updated state dict
    """
    state = load_state()
    
    # Update session counters
    if result == 'win':
        state['session']['wins'] += 1
        state['session']['net_units'] += abs(units)
    elif result == 'loss':
        state['session']['losses'] += 1
        state['session']['net_units'] -= abs(units)
    else:  # push
        state['session']['pushes'] += 1
    
    # Update streaks
    _update_streaks(state, result)
    
    # Check auto-unders trigger
    _check_auto_unders(state)
    
    # Update bankroll policy
    _update_bankroll_policy(state)
    
    save_state(state)
    return state


def _update_streaks(state: dict, result: str) -> None:
    """Update streak tracking based on result."""
    if result == 'push':
        return  # Pushes don't affect streaks
    
    streaks = state['streaks']
    
    if result == 'win':
        if streaks['streak_type'] == 'win':
            streaks['current_streak'] += 1
        else:
            streaks['current_streak'] = 1
            streaks['streak_type'] = 'win'
        
        streaks['max_win_streak'] = max(
            streaks['max_win_streak'], 
            streaks['current_streak']
        )
    
    elif result == 'loss':
        if streaks['streak_type'] == 'loss':
            streaks['current_streak'] += 1
        else:
            streaks['current_streak'] = 1
            streaks['streak_type'] = 'loss'
        
        streaks['max_loss_streak'] = max(
            streaks['max_loss_streak'],
            streaks['current_streak']
        )


def _check_auto_unders(state: dict) -> None:
    """Check if auto-unders should be triggered."""
    streaks = state['streaks']
    controls = state['auto_controls']
    
    # Trigger unders-only after N consecutive losses
    if (streaks['streak_type'] == 'loss' and 
        streaks['current_streak'] >= controls['consecutive_losses_threshold']):
        
        if not controls['unders_only_mode']:
            controls['unders_only_mode'] = True
            controls['unders_only_triggered_at'] = datetime.now().isoformat()
            controls['unders_only_reason'] = f"{streaks['current_streak']} consecutive losses"
    
    # Clear unders-only after 2 consecutive wins
    if (streaks['streak_type'] == 'win' and 
        streaks['current_streak'] >= 2 and
        controls['unders_only_mode']):
        
        controls['unders_only_mode'] = False
        controls['unders_only_triggered_at'] = None
        controls['unders_only_reason'] = None


def _update_bankroll_policy(state: dict) -> None:
    """Update bankroll policy based on session performance."""
    session = state['session']
    bankroll = state['bankroll']
    
    total_plays = session['wins'] + session['losses']
    if total_plays == 0:
        return
    
    win_rate = session['wins'] / total_plays
    
    # Policy rules
    if session['net_units'] <= -3.0:
        bankroll['current_policy'] = 'RECOVERY'
        bankroll['policy_reason'] = 'Down 3+ units'
    elif win_rate < 0.40 and total_plays >= 5:
        bankroll['current_policy'] = 'CONSERVATIVE'
        bankroll['policy_reason'] = f'Win rate {win_rate:.0%} below 40%'
    elif session['net_units'] >= 2.0:
        bankroll['current_policy'] = 'NORMAL'
        bankroll['policy_reason'] = 'Positive session'
    else:
        bankroll['current_policy'] = 'CONSERVATIVE'
        bankroll['policy_reason'] = 'Default caution'


def is_unders_only() -> bool:
    """Check if currently in unders-only mode."""
    state = load_state()
    return state['auto_controls']['unders_only_mode']


def get_bankroll_policy() -> str:
    """Get current bankroll policy."""
    state = load_state()
    return state['bankroll']['current_policy']


def get_session_summary() -> dict:
    """Get current session summary."""
    state = load_state()
    return {
        'date': state['session']['date'],
        'record': f"{state['session']['wins']}-{state['session']['losses']}-{state['session']['pushes']}",
        'net_units': state['session']['net_units'],
        'current_streak': f"{state['streaks']['current_streak']} {state['streaks']['streak_type'] or 'N/A'}",
        'unders_only': state['auto_controls']['unders_only_mode'],
        'bankroll_policy': state['bankroll']['current_policy']
    }


def force_unders_only(reason: str = "Manual override") -> dict:
    """Manually force unders-only mode."""
    state = load_state()
    state['auto_controls']['unders_only_mode'] = True
    state['auto_controls']['unders_only_triggered_at'] = datetime.now().isoformat()
    state['auto_controls']['unders_only_reason'] = reason
    save_state(state)
    return state


def clear_unders_only() -> dict:
    """Manually clear unders-only mode."""
    state = load_state()
    state['auto_controls']['unders_only_mode'] = False
    state['auto_controls']['unders_only_triggered_at'] = None
    state['auto_controls']['unders_only_reason'] = None
    save_state(state)
    return state
