"""
CBB Live Controls — Package Init
Observability + In-Game Risk Management
"""

from .lock_unders import (
    LockUndersDetector,
    LockUndersSignal,
    LockUndersThresholds,
    LiveGameState,
    check_lock_unders
)

from .foulout_model import (
    foulout_probability,
    assess_player_foulout,
    assess_team_foulout,
    should_lock_unders_foulout,
    PlayerFoulState,
    FoulOutRisk
)

from .second_half import (
    allow_second_half_only,
    evaluate_second_half,
    check_triggers,
    get_2h_under_units,
    SecondHalfState,
    SecondHalfDecision
)

from .dashboard_state import (
    update_dashboard,
    get_dashboard_state,
    persist_dashboard,
    load_dashboard,
    reset_dashboard,
    print_dashboard,
    stream_dashboard_json,
    hook_live_monitor,
    hook_foulout_engine,
    hook_variance_governor,
    hook_mode_change,
    hook_ladder_step,
    hook_hedge
)

from .ladder_engine import (
    evaluate_ladder_step,
    get_ladder_summary,
    get_next_ladder_action,
    record_ladder_loss,
    reset_ladder,
    ladder_step_allowed,
    compute_ladder_units,
    LadderState,
    LadderDecision
)

__all__ = [
    # Lock unders
    'LockUndersDetector',
    'LockUndersSignal', 
    'LockUndersThresholds',
    'LiveGameState',
    'check_lock_unders',
    
    # Foul-out
    'foulout_probability',
    'assess_player_foulout',
    'assess_team_foulout',
    'should_lock_unders_foulout',
    'PlayerFoulState',
    'FoulOutRisk',
    
    # Second half
    'allow_second_half_only',
    'evaluate_second_half',
    'check_triggers',
    'get_2h_under_units',
    'SecondHalfState',
    'SecondHalfDecision',
    
    # Dashboard
    'update_dashboard',
    'get_dashboard_state',
    'persist_dashboard',
    'load_dashboard',
    'reset_dashboard',
    'print_dashboard',
    'stream_dashboard_json',
    'hook_live_monitor',
    'hook_foulout_engine',
    'hook_variance_governor',
    'hook_mode_change',
    'hook_ladder_step',
    'hook_hedge',
    
    # Ladder
    'evaluate_ladder_step',
    'get_ladder_summary',
    'get_next_ladder_action',
    'record_ladder_loss',
    'reset_ladder',
    'ladder_step_allowed',
    'compute_ladder_units',
    'LadderState',
    'LadderDecision'
]
