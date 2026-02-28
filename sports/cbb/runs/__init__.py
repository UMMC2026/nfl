"""
CBB Runs Package — State and Risk Management
"""

from .update_state import (
    load_state,
    save_state,
    start_session,
    record_outcome,
    record_edge_generated,
    record_edge_published,
    is_unders_only,
    get_bankroll_policy,
    get_session_summary,
    force_unders_only,
    clear_unders_only
)

from .risk_manager import (
    compute_unit_size,
    can_add_exposure,
    record_exposure,
    get_max_edges_for_game,
    get_exposure_summary,
    UnitSizing
)

__all__ = [
    # State management
    'load_state',
    'save_state', 
    'start_session',
    'record_outcome',
    'record_edge_generated',
    'record_edge_published',
    'is_unders_only',
    'get_bankroll_policy',
    'get_session_summary',
    'force_unders_only',
    'clear_unders_only',
    
    # Risk management
    'compute_unit_size',
    'can_add_exposure',
    'record_exposure',
    'get_max_edges_for_game',
    'get_exposure_summary',
    'UnitSizing'
]
