"""
TOTAL SETS ENGINE — Edge Generator
===================================
Market: TOTAL_SETS
Edge Identity: (playerA, playerB, surface, sets_line)

Focused on set count prediction (2.5 for Bo3, 3.5/4.5 for Bo5).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add parent to path for imports
TENNIS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(TENNIS_DIR / "ingest"))

from ingest_tennis import (
    load_global_config,
    load_player_stats,
    get_player_elo,
    get_player_hold_pct,
    check_global_blocks,
    PlayerStats,
)

CONFIG_DIR = TENNIS_DIR / "config"
OUTPUTS_DIR = TENNIS_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


# =============================================================================
# CONFIG
# =============================================================================

def load_engine_config() -> Dict:
    config_path = CONFIG_DIR / "totals_sets.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


GRAND_SLAMS = {"australian open", "french open", "roland garros", "wimbledon", "us open"}

WTA_INDICATORS = {
    "elena", "iga", "aryna", "coco", "naomi", "jessica", "emma", "belinda",
    "madison", "jelena", "paula", "maria", "petra", "caroline", "victoria",
    "daria", "donna", "marketa", "barbora", "sloane", "peyton", "amanda",
    "rybakina", "swiatek", "sabalenka", "gauff", "pegula", "bencic", "keys",
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TotalSetsCandidate:
    player_a: str
    player_b: str
    surface: str
    sets_line: float  # 2.5 for Bo3, 3.5/4.5 for Bo5
    tournament: str = ""
    best_of: int = 3
    allowed_directions: Set[str] = None
    
    def __post_init__(self):
        if self.allowed_directions is None:
            self.allowed_directions = {"OVER", "UNDER"}


@dataclass
class TotalSetsEdge:
    edge_id: str
    sport: str
    engine: str
    market: str
    player_a: str
    player_b: str
    surface: str
    line: float
    best_of: int
    direction: Optional[str]
    probability: Optional[float]
    tier: str
    edge: Optional[float]
    blocked: bool
    block_reason: Optional[List[str]]
    features: Optional[Dict]
    generated_at: str
    
    def to_dict(self) -> Dict:
        return {
            "edge_id": self.edge_id,
            "sport": "TENNIS",
            "engine": self.engine,
            "market": self.market,
            "players": [self.player_a, self.player_b],
            "surface": self.surface,
            "line": self.line,
            "best_of": self.best_of,
            "direction": self.direction,
            "probability": self.probability,
            "tier": self.tier,
            "edge": self.edge,
            "risk_tag": "ENGINE_ISOLATED",
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "sources": ["player_stats", "elo_ratings"],
            "finalized": not self.blocked,
            "features": self.features,
            "generated_at": self.generated_at,
        }


# =============================================================================
# HELPERS
# =============================================================================

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def make_edge_id(player_a: str, player_b: str, surface: str, line: float) -> str:
    a = player_a.replace(" ", "_")[:20]
    b = player_b.replace(" ", "_")[:20]
    return f"TOTAL_SETS::{a}::{b}::{surface}::{line:.1f}"


def detect_wta(player_a: str, player_b: str) -> bool:
    combined = (player_a + " " + player_b).lower()
    for indicator in WTA_INDICATORS:
        if indicator in combined:
            return True
    return False


def infer_best_of(line: float, tournament: str, is_wta: bool) -> int:
    if is_wta:
        return 3
    if tournament.lower().strip() in GRAND_SLAMS:
        return 5
    return 5 if line > 2.5 else 3


# =============================================================================
# BLOCK RULES
# =============================================================================

def check_totals_sets_blocks(
    candidate: TotalSetsCandidate,
    stats: Dict[str, PlayerStats],
    global_config: Dict,
    engine_config: Dict,
) -> List[str]:
    """Check Total Sets specific block rules."""
    
    reasons = check_global_blocks(
        candidate.player_a,
        candidate.player_b,
        candidate.surface,
        stats,
        global_config,
    )
    
    block_rules = engine_config.get("block_rules", {})
    
    ps_a = stats.get(candidate.player_a.lower())
    ps_b = stats.get(candidate.player_b.lower())
    
    # Qualifier vs top-20 block (massive ranking gap)
    if ps_a and ps_b:
        rank_a = ps_a.ranking or 999
        rank_b = ps_b.ranking or 999
        
        is_qualifier = rank_a > 200 or rank_b > 200
        is_top20 = rank_a <= 20 or rank_b <= 20
        
        if block_rules.get("qualifier_vs_top20") and is_qualifier and is_top20:
            reasons.append("QUALIFIER_VS_TOP20")
    
    # Straight set rate > 72% block (too predictable)
    if ps_a and ps_b:
        ss_a = ps_a.straight_set_pct or 0.60
        ss_b = ps_b.straight_set_pct or 0.60
        max_ss = max(ss_a, ss_b)
        
        if block_rules.get("straight_set_rate_gt_72") and max_ss > 0.72:
            reasons.append(f"HIGH_STRAIGHT_SET::{max_ss:.1%}")
    
    return reasons


# =============================================================================
# PROBABILITY MODEL
# =============================================================================

def compute_total_sets_probability(
    candidate: TotalSetsCandidate,
    stats: Dict[str, PlayerStats],
    engine_config: Dict,
) -> Tuple[float, float, str, Dict]:
    """
    Compute Over/Under probability for set count.
    
    For Bo3 (line 2.5): Over = 3 sets, Under = 2 sets (straight)
    For Bo5 (line 3.5/4.5): Different probabilities apply
    
    Returns: (probability, edge, direction, features_dict)
    """
    best_of = candidate.best_of
    line = candidate.sets_line
    surface = candidate.surface.upper()
    
    # Get player stats
    ps_a = stats.get(candidate.player_a.lower())
    ps_b = stats.get(candidate.player_b.lower())
    
    # Elo gap for match competitiveness
    elo_a = get_player_elo(candidate.player_a, surface, stats)
    elo_b = get_player_elo(candidate.player_b, surface, stats)
    elo_gap = abs(elo_a - elo_b)
    
    # Straight set rates
    ss_a = ps_a.straight_set_pct if ps_a else 0.60
    ss_b = ps_b.straight_set_pct if ps_b else 0.60
    avg_straight_set = (ss_a + ss_b) / 2
    
    # Tiebreak rates (more tiebreaks = longer sets = more competitive)
    tb_a = ps_a.tiebreak_rate if ps_a else 0.22
    tb_b = ps_b.tiebreak_rate if ps_b else 0.22
    avg_tiebreak = (tb_a + tb_b) / 2
    
    # Win percentage on surface
    win_a = ps_a.surface_win_pct.get(surface, 0.50) if ps_a else 0.50
    win_b = ps_b.surface_win_pct.get(surface, 0.50) if ps_b else 0.50
    
    # Competitiveness factor (1.0 = very even, 0.5 = mismatch)
    comp = 1.0 - (elo_gap / 300)
    comp = _clamp(comp, 0.4, 1.0)
    
    # Bo3: P(3 sets) based on competitiveness and straight set history
    if best_of == 3 and line == 2.5:
        # Base probability of 3 sets (over 2.5)
        # More competitive = more likely to go 3 sets
        # Higher straight set rates = more likely 2 sets
        
        p_three_sets = 0.35  # Base
        p_three_sets += (comp - 0.7) * 0.3  # Competitiveness adjustment
        p_three_sets -= (avg_straight_set - 0.60) * 0.4  # Straight set history
        p_three_sets += (avg_tiebreak - 0.20) * 0.2  # Tiebreaks = competitive
        
        p_over = _clamp(p_three_sets, 0.25, 0.55)
        
    elif best_of == 5 and line == 3.5:
        # P(4 or 5 sets) - over 3.5
        # Higher competitiveness = higher probability
        
        p_four_or_five = 0.55  # Base
        p_four_or_five += (comp - 0.7) * 0.25
        p_four_or_five -= (avg_straight_set - 0.60) * 0.3
        
        p_over = _clamp(p_four_or_five, 0.40, 0.70)
        
    elif best_of == 5 and line == 4.5:
        # P(5 sets) - over 4.5
        # Very competitive matches only
        
        p_five = 0.22  # Base
        p_five += (comp - 0.8) * 0.2
        p_five += (avg_tiebreak - 0.22) * 0.15
        
        p_over = _clamp(p_five, 0.15, 0.35)
    else:
        # Unknown line
        p_over = 0.50
    
    # Direction
    if p_over >= 0.5:
        direction = "OVER"
        probability = p_over
    else:
        direction = "UNDER"
        probability = 1.0 - p_over
    
    # Clamp to tennis module limits
    probability = _clamp(probability, 0.55, 0.72)
    edge_val = probability - 0.50
    
    features = {
        "elo_a": round(elo_a, 1),
        "elo_b": round(elo_b, 1),
        "elo_gap": round(elo_gap, 1),
        "competitiveness": round(comp, 3),
        "straight_set_a": round(ss_a, 3),
        "straight_set_b": round(ss_b, 3),
        "avg_straight_set": round(avg_straight_set, 3),
        "avg_tiebreak": round(avg_tiebreak, 3),
        "p_over_raw": round(p_over, 4),
    }
    
    return probability, edge_val, direction, features


# =============================================================================
# TIER ASSIGNMENT (Phase 5B: Tournament-Tier Aware)
# =============================================================================

def assign_tier(probability: float, engine_config: Dict, tournament: str = "") -> str:
    """
    Assign tier using tournament-specific thresholds.
    
    Phase 5B Enhancement: Uses TENNIS_GRAND_SLAM, TENNIS_MASTERS, etc.
    Grand Slams and Masters now eligible for SLAM tier.
    """
    # Try to use tournament-tier specific thresholds
    try:
        from tennis.tournament_tier import implied_tier_for_tennis
        
        if tournament:
            return implied_tier_for_tennis(probability, tournament)
    except ImportError:
        pass
    
    # Fallback to engine config thresholds
    tiers = engine_config.get("tiers", {})
    
    slam_min = tiers.get("SLAM", {}).get("min", 0.80)
    strong_min = tiers.get("STRONG", {}).get("min", 0.66)
    lean_min = tiers.get("LEAN", {}).get("min", 0.58)
    
    if slam_min is not None and probability >= slam_min:
        return "SLAM"
    if probability >= strong_min:
        return "STRONG"
    elif probability >= lean_min:
        return "LEAN"
    else:
        return "NO_PLAY"


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_edge(
    candidate: TotalSetsCandidate,
    stats: Dict[str, PlayerStats],
    global_config: Dict,
    engine_config: Dict,
) -> TotalSetsEdge:
    """Generate a single Total Sets edge."""
    
    timestamp = datetime.utcnow().isoformat() + "Z"
    edge_id = make_edge_id(
        candidate.player_a,
        candidate.player_b,
        candidate.surface,
        candidate.sets_line,
    )
    
    # Check blocks
    block_reasons = check_totals_sets_blocks(candidate, stats, global_config, engine_config)
    
    if block_reasons:
        return TotalSetsEdge(
            edge_id=edge_id,
            sport="TENNIS",
            engine="TOTAL_SETS_ENGINE",
            market="TOTAL_SETS",
            player_a=candidate.player_a,
            player_b=candidate.player_b,
            surface=candidate.surface,
            line=candidate.sets_line,
            best_of=candidate.best_of,
            direction=None,
            probability=None,
            tier="BLOCKED",
            edge=None,
            blocked=True,
            block_reason=block_reasons,
            features=None,
            generated_at=timestamp,
        )
    
    # Compute probability
    probability, edge_val, direction, features = compute_total_sets_probability(
        candidate, stats, engine_config
    )
    
    # Check direction availability
    if direction not in candidate.allowed_directions:
        other = "UNDER" if direction == "OVER" else "OVER"
        if other in candidate.allowed_directions:
            direction = other
            probability = 1.0 - probability
            probability = _clamp(probability, 0.55, 0.72)
            edge_val = probability - 0.50
        else:
            return TotalSetsEdge(
                edge_id=edge_id,
                sport="TENNIS",
                engine="TOTAL_SETS_ENGINE",
                market="TOTAL_SETS",
                player_a=candidate.player_a,
                player_b=candidate.player_b,
                surface=candidate.surface,
                line=candidate.sets_line,
                best_of=candidate.best_of,
                direction=None,
                probability=None,
                tier="BLOCKED",
                edge=None,
                blocked=True,
                block_reason=["DIRECTION_NOT_AVAILABLE"],
                features=None,
                generated_at=timestamp,
            )
    
    # Phase 5B: Apply injury adjustments
    injury_info = {}
    try:
        from tennis.injury_gate import apply_injury_adjustment
        probability, injury_info = apply_injury_adjustment(
            probability, candidate.player_a, candidate.player_b
        )
        if injury_info.get("adjustment_applied"):
            features = features or {}
            features["injury_adjustment"] = injury_info
    except ImportError:
        pass
    
    # Phase 5B: Apply surface momentum adjustments
    surface_info = {}
    try:
        from tennis.surface_momentum import apply_surface_momentum
        probability, surface_info = apply_surface_momentum(
            probability, candidate.player_a, candidate.player_b, candidate.surface
        )
        if surface_info.get("adjustment_applied"):
            features = features or {}
            features["surface_momentum"] = surface_info
    except ImportError:
        pass
    
    # Assign tier (Phase 5B: tournament-aware)
    tournament = getattr(candidate, 'tournament', '') or ''
    tier = assign_tier(probability, engine_config, tournament)
    
    return TotalSetsEdge(
        edge_id=edge_id,
        sport="TENNIS",
        engine="TOTAL_SETS_ENGINE",
        market="TOTAL_SETS",
        player_a=candidate.player_a,
        player_b=candidate.player_b,
        surface=candidate.surface,
        line=candidate.sets_line,
        best_of=candidate.best_of,
        direction=direction,
        probability=round(probability, 4),
        tier=tier,
        edge=round(edge_val, 4),
        blocked=False,
        block_reason=None,
        features=features,
        generated_at=timestamp,
    )


def generate_all_edges(
    candidates: List[TotalSetsCandidate],
    max_plays: int = 2,
) -> Dict:
    """Generate edges for all candidates."""
    
    global_config = load_global_config()
    engine_config = load_engine_config()
    stats = load_player_stats()
    
    edges = []
    seen = set()
    
    for c in candidates:
        pa, pb = sorted([c.player_a, c.player_b])
        key = (pa, pb, c.surface, c.sets_line)
        
        if key in seen:
            continue
        seen.add(key)
        
        c.player_a = pa
        c.player_b = pb
        
        edge = generate_edge(c, stats, global_config, engine_config)
        edges.append(edge)
    
    blocked = [e for e in edges if e.blocked]
    playable = [e for e in edges if not e.blocked and e.tier in ("STRONG", "LEAN")]
    
    playable.sort(key=lambda e: e.probability or 0, reverse=True)
    top_edges = playable[:max_plays]
    
    return {
        "engine": "TOTAL_SETS_ENGINE",
        "market": "TOTAL_SETS",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_candidates": len(candidates),
        "blocked_count": len(blocked),
        "playable_count": len(playable),
        "output_count": len(top_edges),
        "max_plays": max_plays,
        "edges": [e.to_dict() for e in top_edges],
        "blocked": [e.to_dict() for e in blocked],
    }


# =============================================================================
# CLI
# =============================================================================

def parse_csv_file(filepath: str) -> List[TotalSetsCandidate]:
    """Parse CSV file into candidates."""
    raw = Path(filepath).read_text(encoding="utf-8")
    lines = raw.strip().splitlines()
    
    if not lines:
        return []
    
    header = lines[0].lower().split(",")
    candidates = []
    
    for row in lines[1:]:
        if not row.strip():
            continue
        parts = row.split(",")
        data = dict(zip(header, parts))
        
        is_wta = detect_wta(data.get("player_a", ""), data.get("player_b", ""))
        tournament = data.get("tournament", "")
        line = float(data.get("line", "2.5"))
        best_of = infer_best_of(line, tournament, is_wta)
        
        dirs = data.get("directions", "OVER,UNDER")
        allowed = {d.strip().upper() for d in dirs.split("|") if d.strip()}
        
        candidates.append(TotalSetsCandidate(
            player_a=data.get("player_a", ""),
            player_b=data.get("player_b", ""),
            surface=data.get("surface", "HARD").upper(),
            sets_line=line,
            tournament=tournament,
            best_of=best_of,
            allowed_directions=allowed or {"OVER", "UNDER"},
        ))
    
    return candidates


def main():
    parser = argparse.ArgumentParser(description="Total Sets Edge Generator")
    parser.add_argument("--csv", required=True, help="Input CSV file")
    parser.add_argument("--max-plays", type=int, default=2, help="Max plays to output")
    parser.add_argument("--output", help="Output JSON file")
    
    args = parser.parse_args()
    
    candidates = parse_csv_file(args.csv)
    print(f"Parsed {len(candidates)} candidates")
    
    output = generate_all_edges(candidates, args.max_plays)
    
    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_path = OUTPUTS_DIR / f"totals_sets_edges_{ts}.json"
    
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Output: {out_path}")
    
    print(f"\n{'='*60}")
    print("TOTAL SETS ENGINE — OUTPUT")
    print(f"{'='*60}")
    print(f"Candidates: {output['total_candidates']} | Blocked: {output['blocked_count']} | Playable: {output['playable_count']}")
    
    for e in output["edges"]:
        print(f"\n[{e['tier']}] {e['players'][0]} vs {e['players'][1]}")
        print(f"  {e['direction']} {e['line']} | P={e['probability']:.1%} | edge={e['edge']:+.1%}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
