"""
CBB Edge Engine Module

EDGE = player + stat + direction + game_id

IMPORTANT: CBB edges are TIGHTER than NBA.
- No composite stats (PRA, PR, etc.) initially
- No unders on players < 20 mpg
- No overs if blowout probability > 25%
"""
from .edge_generator import generate_edges
from .edge_collapse import collapse_edges
from .edge_gates import apply_cbb_edge_gates

__all__ = ["generate_edges", "collapse_edges", "apply_cbb_edge_gates"]
