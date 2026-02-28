"""
PLAYER ACES ENGINE — Edge Generator
====================================
Market: PLAYER_ACES
Edge Identity: (player, opponent, surface, aces_line)

Most restricted engine. Elite servers only.
"""

from __future__ import annotations

import argparse
import json
import math
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
    config_path = CONFIG_DIR / "player_aces.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


# Elite server thresholds by surface
ELITE_ACE_RATES = {
    "HARD": 0.09,    # Top servers hit >9% aces on hard
    "GRASS": 0.11,   # Grass favors big servers
    "CLAY": 0.07,    # Clay suppresses aces
    "INDOOR": 0.10,  # Indoor = fast
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PlayerAcesCandidate:
    player: str
    opponent: str
    surface: str
    aces_line: float
    tournament: str = ""
    best_of: int = 3
    allowed_directions: Set[str] = None
    
    def __post_init__(self):
        if self.allowed_directions is None:
            self.allowed_directions = {"OVER", "UNDER"}


@dataclass
class PlayerAcesEdge:
    edge_id: str
    sport: str
    engine: str
    market: str
    player: str
    opponent: str
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
            "player": self.player,
            "opponent": self.opponent,
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
            "sources": ["player_stats", "serve_data"],
            "finalized": not self.blocked,
            "features": self.features,
            "generated_at": self.generated_at,
        }


# =============================================================================
# HELPERS
# =============================================================================

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def make_edge_id(player: str, opponent: str, surface: str, line: float) -> str:
    p = player.replace(" ", "_")[:20]
    o = opponent.replace(" ", "_")[:20]
    return f"PLAYER_ACES::{p}::{o}::{surface}::{line:.1f}"


# =============================================================================
# BLOCK RULES
# =============================================================================

def check_player_aces_blocks(
    candidate: PlayerAcesCandidate,
    stats: Dict[str, PlayerStats],
    global_config: Dict,
    engine_config: Dict,
) -> List[str]:
    """Check Player Aces specific block rules (strictest)."""
    
    # Global blocks (use player vs opponent)
    reasons = check_global_blocks(
        candidate.player,
        candidate.opponent,
        candidate.surface,
        stats,
        global_config,
    )
    
    block_rules = engine_config.get("block_rules", {})
    ps = stats.get(candidate.player.lower())
    
    if not ps:
        reasons.append("NO_PLAYER_DATA")
        return reasons
    
    surface = candidate.surface.upper()
    
    # ace_rate < 7% always block
    ace_rate = ps.ace_pct or 0.0
    if block_rules.get("ace_rate_lt_7") and ace_rate < 0.07:
        reasons.append(f"LOW_ACE_RATE::{ace_rate:.1%}")
    
    # Non-elite server: ace_rate < 9% AND ranking > 30
    rank = ps.ranking or 999
    elite_threshold = ELITE_ACE_RATES.get(surface, 0.09)
    
    if block_rules.get("non_elite_server") and ace_rate < elite_threshold and rank > 30:
        reasons.append(f"NON_ELITE_SERVER::ace={ace_rate:.1%},rank={rank}")
    
    # Clay surface + ace_rate < 8%
    if block_rules.get("clay_ace_rate_lt_8") and surface == "CLAY" and ace_rate < 0.08:
        reasons.append(f"CLAY_LOW_ACE::{ace_rate:.1%}")
    
    # First serve % < 60%
    first_serve = ps.first_serve_pct or 0.62
    if block_rules.get("first_serve_lt_60") and first_serve < 0.60:
        reasons.append(f"LOW_FIRST_SERVE::{first_serve:.1%}")
    
    return reasons


# =============================================================================
# PROBABILITY MODEL
# =============================================================================

def compute_player_aces_probability(
    candidate: PlayerAcesCandidate,
    stats: Dict[str, PlayerStats],
    engine_config: Dict,
) -> Tuple[float, float, str, Dict]:
    """
    Compute Over/Under probability for player aces.
    Uses L10 rolling stats when available for better accuracy.
    
    base_aces = ace_rate * E[serve_points]
    E[serve_points] = E[games_served] * avg_points_per_game
    
    Returns: (probability, edge, direction, features_dict)
    """
    surface = candidate.surface.upper()
    best_of = candidate.best_of
    line = candidate.aces_line
    
    ps = stats.get(candidate.player.lower())
    opp_stats = stats.get(candidate.opponent.lower())
    
    # Player serve stats — prefer L10 (rolling) over season average
    if ps and ps.ace_pct_L10:
        ace_rate = ps.ace_pct_L10
    elif ps:
        ace_rate = ps.ace_pct
    else:
        ace_rate = 0.07
    
    first_serve = ps.first_serve_pct_L10 if (ps and ps.first_serve_pct_L10) else (ps.first_serve_pct if ps else 0.62)
    hold_pct = get_player_hold_pct(candidate.player, surface, stats)
    
    # Opponent return pressure (affects service games length)
    opp_return_rating = opp_stats.return_rating if opp_stats else 100
    
    # Expected sets
    if best_of == 3:
        E_sets = 2.5
    else:
        E_sets = 4.0
    
    # Expected service games per set
    # Higher hold = longer matches = more service opportunities
    E_service_games = 4.5 + (hold_pct - 0.80) * 2
    E_service_games = _clamp(E_service_games, 4.0, 6.0)
    
    # Expected serve points per service game
    # Avg ~6 points per game, player serves half
    E_serve_points_per_game = 5.5
    
    # Total expected serve points
    E_serve_points = E_sets * E_service_games * E_serve_points_per_game
    
    # Surface ace rate adjustment
    surface_ace_mult = {
        "HARD": 1.0,
        "GRASS": 1.15,
        "CLAY": 0.85,
        "INDOOR": 1.10,
    }
    ace_mult = surface_ace_mult.get(surface, 1.0)
    
    # Opponent return pressure adjustment
    # Higher return rating = fewer free points = fewer aces
    return_adj = 1.0 - (opp_return_rating - 100) / 500
    return_adj = _clamp(return_adj, 0.90, 1.10)
    
    # Expected aces
    E_aces = E_serve_points * ace_rate * ace_mult * return_adj
    
    # Probability calculation (using normal approximation)
    # Variance increases with expected value
    std_dev = math.sqrt(E_aces * 0.8)  # Poisson-like variance
    
    # Z-score
    z = (E_aces - line) / max(std_dev, 0.5)
    
    # Convert to probability
    # Sigmoid approximation of normal CDF
    def sigmoid(x):
        if x >= 0:
            return 1.0 / (1.0 + math.exp(-x * 1.1))
        ez = math.exp(x * 1.1)
        return ez / (1.0 + ez)
    
    p_over = sigmoid(z)
    
    # Direction
    if p_over >= 0.5:
        direction = "OVER"
        probability = p_over
    else:
        direction = "UNDER"
        probability = 1.0 - p_over
    
    # Clamp
    probability = _clamp(probability, 0.55, 0.72)
    edge_val = probability - 0.50
    
    features = {
        "ace_rate": round(ace_rate, 4),
        "first_serve_pct": round(first_serve, 3),
        "hold_pct": round(hold_pct, 3),
        "opp_return_rating": round(opp_return_rating, 1),
        "E_sets": round(E_sets, 2),
        "E_service_games": round(E_service_games, 2),
        "E_serve_points": round(E_serve_points, 1),
        "E_aces": round(E_aces, 2),
        "std_dev": round(std_dev, 2),
        "z_score": round(z, 3),
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
    candidate: PlayerAcesCandidate,
    stats: Dict[str, PlayerStats],
    global_config: Dict,
    engine_config: Dict,
) -> PlayerAcesEdge:
    """Generate a single Player Aces edge."""
    
    timestamp = datetime.utcnow().isoformat() + "Z"
    edge_id = make_edge_id(
        candidate.player,
        candidate.opponent,
        candidate.surface,
        candidate.aces_line,
    )
    
    # Check blocks
    block_reasons = check_player_aces_blocks(candidate, stats, global_config, engine_config)
    
    if block_reasons:
        return PlayerAcesEdge(
            edge_id=edge_id,
            sport="TENNIS",
            engine="PLAYER_ACES_ENGINE",
            market="PLAYER_ACES",
            player=candidate.player,
            opponent=candidate.opponent,
            surface=candidate.surface,
            line=candidate.aces_line,
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
    probability, edge_val, direction, features = compute_player_aces_probability(
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
            return PlayerAcesEdge(
                edge_id=edge_id,
                sport="TENNIS",
                engine="PLAYER_ACES_ENGINE",
                market="PLAYER_ACES",
                player=candidate.player,
                opponent=candidate.opponent,
                surface=candidate.surface,
                line=candidate.aces_line,
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
            probability, candidate.player, candidate.opponent
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
            probability, candidate.player, candidate.opponent, candidate.surface
        )
        if surface_info.get("adjustment_applied"):
            features = features or {}
            features["surface_momentum"] = surface_info
    except ImportError:
        pass
    
    # Assign tier (Phase 5B: tournament-aware)
    tournament = getattr(candidate, 'tournament', '') or ''
    tier = assign_tier(probability, engine_config, tournament)
    
    return PlayerAcesEdge(
        edge_id=edge_id,
        sport="TENNIS",
        engine="PLAYER_ACES_ENGINE",
        market="PLAYER_ACES",
        player=candidate.player,
        opponent=candidate.opponent,
        surface=candidate.surface,
        line=candidate.aces_line,
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
    candidates: List[PlayerAcesCandidate],
    max_plays: int = 1,
) -> Dict:
    """Generate edges for all candidates."""
    
    global_config = load_global_config()
    engine_config = load_engine_config()
    stats = load_player_stats()
    
    edges = []
    seen = set()
    
    for c in candidates:
        key = (c.player.lower(), c.opponent.lower(), c.surface, c.aces_line)
        
        if key in seen:
            continue
        seen.add(key)
        
        edge = generate_edge(c, stats, global_config, engine_config)
        edges.append(edge)
    
    blocked = [e for e in edges if e.blocked]
    playable = [e for e in edges if not e.blocked and e.tier in ("STRONG", "LEAN")]
    
    playable.sort(key=lambda e: e.probability or 0, reverse=True)
    top_edges = playable[:max_plays]
    
    return {
        "engine": "PLAYER_ACES_ENGINE",
        "market": "PLAYER_ACES",
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

def parse_csv_file(filepath: str) -> List[PlayerAcesCandidate]:
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
        
        dirs = data.get("directions", "OVER,UNDER")
        allowed = {d.strip().upper() for d in dirs.split("|") if d.strip()}
        
        candidates.append(PlayerAcesCandidate(
            player=data.get("player", ""),
            opponent=data.get("opponent", ""),
            surface=data.get("surface", "HARD").upper(),
            aces_line=float(data.get("line", "8.5")),
            tournament=data.get("tournament", ""),
            best_of=int(data.get("best_of", "3")),
            allowed_directions=allowed or {"OVER", "UNDER"},
        ))
    
    return candidates


def main():
    parser = argparse.ArgumentParser(description="Player Aces Edge Generator")
    parser.add_argument("--csv", required=True, help="Input CSV file")
    parser.add_argument("--max-plays", type=int, default=1, help="Max plays to output")
    parser.add_argument("--output", help="Output JSON file")
    
    args = parser.parse_args()
    
    candidates = parse_csv_file(args.csv)
    print(f"Parsed {len(candidates)} candidates")
    
    output = generate_all_edges(candidates, args.max_plays)
    
    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_path = OUTPUTS_DIR / f"player_aces_edges_{ts}.json"
    
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Output: {out_path}")
    
    print(f"\n{'='*60}")
    print("PLAYER ACES ENGINE — OUTPUT")
    print(f"{'='*60}")
    print(f"Candidates: {output['total_candidates']} | Blocked: {output['blocked_count']} | Playable: {output['playable_count']}")
    
    for e in output["edges"]:
        print(f"\n[{e['tier']}] {e['player']} (vs {e['opponent']})")
        print(f"  {e['direction']} {e['line']} | P={e['probability']:.1%} | edge={e['edge']:+.1%}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
