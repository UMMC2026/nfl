"""
Tennis Output Validation — HARD GATE
=====================================
Validation failure = abort. No exceptions.

This is the final gate before any output is rendered or acted upon.

GOVERNANCE: Tier thresholds imported from config/thresholds.py (single source of truth).
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.thresholds import get_all_thresholds, implied_tier

TENNIS_DIR = Path(__file__).parent
OUTPUTS_DIR = TENNIS_DIR / "outputs"
CONFIG_FILE = TENNIS_DIR / "tennis_config.json"

CONFIG = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}

# Required fields for a valid edge
REQUIRED_FIELDS = [
    "sport",
    "match_id",
    "player",
    "opponent",
    "surface",
    "market",
    "direction",
    "tier",
    "blocked",
]

# Fields required for playable edges
PLAYABLE_FIELDS = [
    "probability",
    "edge",
    "line",
]

# Valid values
VALID_SPORTS = ["TENNIS"]
VALID_TOURS = ["ATP", "WTA"]
VALID_SURFACES = ["HARD", "CLAY", "GRASS", "INDOOR"]
VALID_MARKETS = ["match_winner"]
# Canonical tiers are defined in config/thresholds.py and include SLAM/AVOID.
# Keep NO_PLAY accepted for backward compatibility (treated as AVOID).
VALID_TIERS = ["SLAM", "STRONG", "LEAN", "AVOID", "NO_PLAY", "BLOCKED"]


def validate_edge(edge: Dict, idx: int) -> Tuple[bool, List[str]]:
    """Validate a single edge."""
    errors = []
    
    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in edge:
            errors.append(f"Edge {idx}: Missing required field '{field}'")
    
    # Check playable edge fields (only for tiers that are actually playable)
    tier_u = str(edge.get("tier") or "").upper()
    if not edge.get("blocked") and tier_u in {"SLAM", "STRONG", "LEAN"}:
        for field in PLAYABLE_FIELDS:
            if field not in edge or edge[field] is None:
                errors.append(f"Edge {idx}: Playable edge missing '{field}'")
    
    # Validate sport
    if edge.get("sport") not in VALID_SPORTS:
        errors.append(f"Edge {idx}: Invalid sport '{edge.get('sport')}'")
    
    # Validate tour
    if edge.get("tour") and edge.get("tour") not in VALID_TOURS:
        errors.append(f"Edge {idx}: Invalid tour '{edge.get('tour')}'")
    
    # Validate surface
    if edge.get("surface") not in VALID_SURFACES:
        errors.append(f"Edge {idx}: Invalid surface '{edge.get('surface')}'")
    
    # Validate market
    if edge.get("market") not in VALID_MARKETS:
        errors.append(f"Edge {idx}: Invalid market '{edge.get('market')}' (only match_winner allowed)")
    
    # Validate tier
    if edge.get("tier") not in VALID_TIERS:
        errors.append(f"Edge {idx}: Invalid tier '{edge.get('tier')}'")
    
    # Validate probability bounds
    prob = edge.get("probability")
    if prob is not None:
        prob_config = CONFIG.get("probability", {})
        min_prob = prob_config.get("min_probability", 0.50)
        max_prob = prob_config.get("max_probability", 0.80)
        
        if prob < min_prob or prob > max_prob:
            errors.append(f"Edge {idx}: Probability {prob:.2%} outside bounds [{min_prob:.0%}, {max_prob:.0%}]")
    
    # Validate tier consistency
    # GOVERNANCE: Use canonical thresholds from config/thresholds.py
    if prob is not None and edge.get("tier") not in ["BLOCKED"]:
        expected_tier = implied_tier(prob, "TENNIS")
        declared = str(edge.get("tier") or "").upper()
        if declared == "NO_PLAY":
            declared = "AVOID"

        if declared != expected_tier:
            errors.append(f"Edge {idx}: Tier mismatch - prob={prob:.1%} should be {expected_tier}, got {edge.get('tier')}")
    
    # Validate edge calculation
    if not edge.get("blocked") and prob is not None:
        implied = edge.get("implied_prob", 0.5)
        calc_edge = prob - implied
        reported_edge = edge.get("edge", 0)
        
        if abs(calc_edge - reported_edge) > 0.01:
            errors.append(f"Edge {idx}: Edge calculation mismatch - expected {calc_edge:.3f}, got {reported_edge:.3f}")
    
    # Validate blocked edge consistency
    if edge.get("blocked"):
        if not edge.get("block_reason"):
            errors.append(f"Edge {idx}: Blocked edge missing block_reason")
        if edge.get("tier") != "BLOCKED":
            errors.append(f"Edge {idx}: Blocked edge should have tier=BLOCKED")
    
    return len(errors) == 0, errors


def validate_output(output: Dict) -> Tuple[bool, List[str]]:
    """Validate the entire output structure."""
    all_errors = []
    
    # Check top-level structure
    if output.get("sport") != "TENNIS":
        all_errors.append(f"Invalid sport in output: {output.get('sport')}")
    
    if "edges" not in output:
        all_errors.append("Missing 'edges' array in output")
        return False, all_errors
    
    edges = output["edges"]
    
    if not isinstance(edges, list):
        all_errors.append("'edges' must be an array")
        return False, all_errors
    
    # Validate each edge
    for idx, edge in enumerate(edges):
        valid, errors = validate_edge(edge, idx)
        all_errors.extend(errors)
    
    # Check for duplicate edges (same player, opponent, surface, round)
    seen = set()
    for idx, edge in enumerate(edges):
        key = (edge.get("player"), edge.get("opponent"), edge.get("surface"), edge.get("round"))
        if key in seen:
            all_errors.append(f"Edge {idx}: Duplicate edge for {key}")
        seen.add(key)
    
    # Sanity checks
    # Playable = governed tiers only (SLAM/STRONG/LEAN)
    playable = [
        e for e in edges
        if not e.get("blocked")
        and str(e.get("tier") or "").upper() in {"SLAM", "STRONG", "LEAN"}
    ]
    if len(playable) > 20:
        all_errors.append(f"Warning: {len(playable)} playable edges seems high - check calibration")
    
    strong = [e for e in playable if str(e.get("tier") or "").upper() == "STRONG"]
    if len(strong) > 10:
        all_errors.append(f"Warning: {len(strong)} STRONG edges seems high - check tier thresholds")
    
    return len(all_errors) == 0, all_errors


def validate_file(filepath: Path) -> Tuple[bool, List[str]]:
    """Validate a tennis output file."""
    
    if not filepath.exists():
        return False, [f"File not found: {filepath}"]
    
    try:
        output = json.loads(filepath.read_text())
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    
    return validate_output(output)


def run_validation(filepath: Path = None) -> bool:
    """
    Run validation on tennis output.
    
    Returns: True if valid, False if validation failed (HARD GATE)
    """
    print("=" * 60)
    print("TENNIS OUTPUT VALIDATION — HARD GATE")
    print("=" * 60)
    
    if filepath is None:
        # Try latest scored, then latest edges
        filepath = OUTPUTS_DIR / "tennis_scored_latest.json"
        if not filepath.exists():
            filepath = OUTPUTS_DIR / "tennis_edges_latest.json"
    
    print(f"\nValidating: {filepath}")
    
    valid, errors = validate_file(filepath)
    
    if valid:
        print("\n✅ VALIDATION PASSED")
        print("   All edges are structurally valid")
        print("   Output is safe to render/act upon")
        return True
    else:
        print(f"\n❌ VALIDATION FAILED ({len(errors)} errors)")
        print("-" * 40)
        for error in errors[:20]:  # Show first 20 errors
            print(f"  • {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors")
        print("-" * 40)
        print("\n⛔ OUTPUT BLOCKED — Fix errors before proceeding")
        return False


if __name__ == "__main__":
    # Accept optional filepath argument
    filepath = None
    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
    
    success = run_validation(filepath)
    sys.exit(0 if success else 1)
