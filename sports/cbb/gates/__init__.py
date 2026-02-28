"""
CBB Gates Module

Hard gates that block edge generation:
- roster_gate: Player must be on active roster
- minutes_gate: Player must average ≥20 MPG
- games_played_gate: Minimum games for reliable stats
- blowout_gate: Skip overs when spread >25 points

Soft gates (penalties in scoring):
- variance_gate: Skip if stat variance too high
- role_mismatch_gate: Starter/bench changes
- conference_gate: Conference matchup adjustments

SDG Gates (v2.1 - Stat Deviation Gate):
- cbb_sdg_filter: Soft volatility governor - prices variance
- cbb_context_gates: Situational adjustments (SOS, road, conference)
- sdg_integration: Wiring layer for cbb_main.py
"""

from .roster_gate import check_roster_gate, check_minutes_gate, batch_check_roster
from .edge_gates import CBBEdgeGates, get_gates, apply_all_gates

# SDG v2.1 imports (2026-02-01)
try:
    from .cbb_sdg_filter import apply_cbb_sdg_filter, CBBSDGConfig
    from .cbb_context_gates import apply_all_context_gates, CBBWindowConfig
    from .sdg_integration import (
        run_full_sdg_pipeline,
        apply_sdg_to_edges,
        apply_sdg_to_edge,
    )
    SDG_AVAILABLE = True
except ImportError as e:
    print(f"[CBB Gates] Warning: SDG modules not available: {e}")
    SDG_AVAILABLE = False

__all__ = [
    "check_roster_gate",
    "check_minutes_gate", 
    "batch_check_roster",
    "CBBEdgeGates",
    "get_gates",
    "apply_all_gates",
    # SDG v2.1
    "apply_cbb_sdg_filter",
    "CBBSDGConfig",
    "apply_all_context_gates",
    "CBBWindowConfig",
    "run_full_sdg_pipeline",
    "apply_sdg_to_edges",
    "apply_sdg_to_edge",
    "SDG_AVAILABLE",
]
