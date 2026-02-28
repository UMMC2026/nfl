"""
TOTAL GAMES ENGINE — Edge Generator
====================================
Market: TOTAL_GAMES
Edge Identity: (playerA, playerB, surface, games_line)

Deterministic structural model.
No ML. No guessing.
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
    config_path = CONFIG_DIR / "totals_games.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


SURFACE_BASELINES = {
    "HARD": 9.9,
    "CLAY": 9.5,
    "GRASS": 10.8,
    "INDOOR": 10.5,
}

GRAND_SLAMS = {"australian open", "french open", "roland garros", "wimbledon", "us open"}

WTA_INDICATORS = {
    "elena", "iga", "aryna", "coco", "naomi", "jessica", "emma", "belinda",
    "madison", "jelena", "paula", "maria", "petra", "caroline", "victoria",
    "daria", "donna", "marketa", "barbora", "sloane", "peyton", "amanda",
    "rybakina", "swiatek", "sabalenka", "gauff", "pegula", "bencic", "keys",
    "ostapenko", "bouzkova", "gracheva", "bartunkova", "mertens", "siniakova",
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TotalGamesCandidate:
    player_a: str
    player_b: str
    surface: str
    games_line: float
    tournament: str = ""
    best_of: int = 3
    allowed_directions: Set[str] = None
    
    def __post_init__(self):
        if self.allowed_directions is None:
            self.allowed_directions = {"OVER", "UNDER"}


@dataclass
class TotalGamesEdge:
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
            "sport": self.sport,
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

def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def make_edge_id(player_a: str, player_b: str, surface: str, line: float) -> str:
    a = player_a.replace(" ", "_")[:20]
    b = player_b.replace(" ", "_")[:20]
    return f"TOTAL_GAMES::{a}::{b}::{surface}::{line:.1f}"


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
    return 5 if line > 33.5 else 3


def infer_rating_gap_from_line(line: float, best_of: int) -> str:
    """Infer rating gap from line (book's implied competitiveness)."""
    if best_of == 3:
        return "LARGE" if line <= 19.5 else "EVEN"
    else:
        return "LARGE" if line <= 32.5 else "EVEN"


# =============================================================================
# BLOCK RULES
# =============================================================================

def check_totals_games_blocks(
    candidate: TotalGamesCandidate,
    stats: Dict[str, PlayerStats],
    global_config: Dict,
    engine_config: Dict,
) -> List[str]:
    """Check Total Games specific block rules."""
    
    # Global blocks first
    reasons = check_global_blocks(
        candidate.player_a,
        candidate.player_b,
        candidate.surface,
        stats,
        global_config,
    )
    
    # Engine-specific blocks
    block_rules = engine_config.get("block_rules", {})
    
    # games_line >= 36.5 AND (elo_gap > 120 OR hold% < 78%)
    if candidate.games_line >= 36.5:
        elo_a = get_player_elo(candidate.player_a, candidate.surface, stats)
        elo_b = get_player_elo(candidate.player_b, candidate.surface, stats)
        elo_gap = abs(elo_a - elo_b)
        
        hold_a = get_player_hold_pct(candidate.player_a, candidate.surface, stats)
        hold_b = get_player_hold_pct(candidate.player_b, candidate.surface, stats)
        min_hold = min(hold_a, hold_b)
        
        if block_rules.get("games_line_gte_36_5_and_elo_gap_gt_120") and elo_gap > 120:
            reasons.append(f"HIGH_LINE_ELO_GAP::{elo_gap:.0f}")
        
        if block_rules.get("games_line_gte_36_5_and_hold_pct_lt_78") and min_hold < 0.78:
            reasons.append(f"HIGH_LINE_LOW_HOLD::{min_hold:.1%}")
    
    return reasons


# =============================================================================
# PROBABILITY MODEL
# =============================================================================

def compute_total_games_probability(
    candidate: TotalGamesCandidate,
    stats: Dict[str, PlayerStats],
    engine_config: Dict,
) -> Tuple[float, float, str, Dict]:
    """
    Compute Over probability using structural model.
    
    base = expected_sets * expected_games_per_set
    adj = tiebreak_prob * 1.2 - blowout_risk * 1.5
    p_over = sigmoid(base - line)
    
    Returns: (probability, edge, direction, features_dict)
    """
    surface = candidate.surface.upper()
    best_of = candidate.best_of
    line = candidate.games_line
    
    # Get player stats
    ps_a = stats.get(candidate.player_a.lower())
    ps_b = stats.get(candidate.player_b.lower())
    
    # Elo and gap
    elo_a = get_player_elo(candidate.player_a, surface, stats)
    elo_b = get_player_elo(candidate.player_b, surface, stats)
    elo_gap = abs(elo_a - elo_b)
    
    # Hold percentages
    hold_a = get_player_hold_pct(candidate.player_a, surface, stats)
    hold_b = get_player_hold_pct(candidate.player_b, surface, stats)
    
    # Tiebreak rates
    tb_a = ps_a.tiebreak_rate if ps_a else 0.22
    tb_b = ps_b.tiebreak_rate if ps_b else 0.22
    tiebreak_rate = (tb_a + tb_b) / 2
    
    # Straight set rates (blowout risk)
    ss_a = ps_a.straight_set_pct if ps_a else 0.60
    ss_b = ps_b.straight_set_pct if ps_b else 0.60
    straight_set_rate = (ss_a + ss_b) / 2
    
    # Rating gap category from line
    rating_gap = infer_rating_gap_from_line(line, best_of)
    
    # Expected sets from config
    exp_sets_cfg = engine_config.get("expected_sets", {})
    if best_of == 3:
        E_sets = exp_sets_cfg.get("Bo3_mismatch", 2.2) if rating_gap == "LARGE" else exp_sets_cfg.get("Bo3_even", 2.7)
    else:
        E_sets = exp_sets_cfg.get("Bo5_mismatch", 3.4) if rating_gap == "LARGE" else exp_sets_cfg.get("Bo5_even", 4.2)
    
    # Expected games per set (surface baseline)
    E_games_set = SURFACE_BASELINES.get(surface, 9.9)
    
    # Adjustments
    # Higher holds + tiebreaks = more games
    hold_adj = ((hold_a + hold_b) / 2 - 0.80) * 3.0
    tb_adj = (tiebreak_rate - 0.20) * 4.0
    # Straight sets = fewer games
    blowout_adj = (straight_set_rate - 0.60) * -3.0
    
    # Base expected total
    base = E_sets * E_games_set + hold_adj + tb_adj + blowout_adj
    
    # Sigmoid of delta
    delta = base - line
    k = 0.30  # Sensitivity
    p_over_raw = _sigmoid(k * delta)
    
    # Direction
    if p_over_raw >= 0.5:
        direction = "OVER"
        probability = p_over_raw
    else:
        direction = "UNDER"
        probability = 1.0 - p_over_raw
    
    # Clamp
    probability = _clamp(probability, 0.55, 0.72)
    
    # Edge (vs implied 50%)
    edge = probability - 0.50
    
    features = {
        "elo_a": round(elo_a, 1),
        "elo_b": round(elo_b, 1),
        "elo_gap": round(elo_gap, 1),
        "hold_a": round(hold_a, 3),
        "hold_b": round(hold_b, 3),
        "tiebreak_rate": round(tiebreak_rate, 3),
        "straight_set_rate": round(straight_set_rate, 3),
        "rating_gap": rating_gap,
        "E_sets": round(E_sets, 2),
        "E_games_set": round(E_games_set, 2),
        "base_expected": round(base, 2),
        "delta": round(delta, 2),
        "p_over_raw": round(p_over_raw, 4),
    }
    
    return probability, edge, direction, features


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
        from tennis.tournament_tier import implied_tier_for_tennis, get_tournament_tier
        
        if tournament:
            return implied_tier_for_tennis(probability, tournament)
    except ImportError:
        pass
    
    # Fallback to engine config thresholds
    tiers = engine_config.get("tiers", {})
    
    slam_min = tiers.get("SLAM", {}).get("min", 0.80)
    strong_min = tiers.get("STRONG", {}).get("min", 0.66)
    lean_min = tiers.get("LEAN", {}).get("min", 0.58)
    
    # Check SLAM first (now enabled for tennis)
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
    candidate: TotalGamesCandidate,
    stats: Dict[str, PlayerStats],
    global_config: Dict,
    engine_config: Dict,
) -> TotalGamesEdge:
    """Generate a single Total Games edge."""
    
    timestamp = datetime.utcnow().isoformat() + "Z"
    edge_id = make_edge_id(
        candidate.player_a,
        candidate.player_b,
        candidate.surface,
        candidate.games_line,
    )
    
    # Check blocks
    block_reasons = check_totals_games_blocks(candidate, stats, global_config, engine_config)
    
    if block_reasons:
        return TotalGamesEdge(
            edge_id=edge_id,
            sport="TENNIS",
            engine="TOTAL_GAMES_ENGINE",
            market="TOTAL_GAMES",
            player_a=candidate.player_a,
            player_b=candidate.player_b,
            surface=candidate.surface,
            line=candidate.games_line,
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
    probability, edge_val, direction, features = compute_total_games_probability(
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
            return TotalGamesEdge(
                edge_id=edge_id,
                sport="TENNIS",
                engine="TOTAL_GAMES_ENGINE",
                market="TOTAL_GAMES",
                player_a=candidate.player_a,
                player_b=candidate.player_b,
                surface=candidate.surface,
                line=candidate.games_line,
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
    
    return TotalGamesEdge(
        edge_id=edge_id,
        sport="TENNIS",
        engine="TOTAL_GAMES_ENGINE",
        market="TOTAL_GAMES",
        player_a=candidate.player_a,
        player_b=candidate.player_b,
        surface=candidate.surface,
        line=candidate.games_line,
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
    candidates: List[TotalGamesCandidate],
    max_plays: int = 2,
) -> Dict:
    """
    Generate edges for all candidates.
    
    Returns output document with edges sorted by probability.
    """
    global_config = load_global_config()
    engine_config = load_engine_config()
    stats = load_player_stats()
    
    edges = []
    seen = set()
    
    for c in candidates:
        # Canonical ordering
        pa, pb = sorted([c.player_a, c.player_b])
        key = (pa, pb, c.surface, c.games_line)
        
        if key in seen:
            continue
        seen.add(key)
        
        # Update candidate with canonical order
        c.player_a = pa
        c.player_b = pb
        
        edge = generate_edge(c, stats, global_config, engine_config)
        edges.append(edge)
    
    # Split blocked vs playable
    blocked = [e for e in edges if e.blocked]
    playable = [e for e in edges if not e.blocked and e.tier in ("STRONG", "LEAN")]
    
    # Sort by probability descending
    playable.sort(key=lambda e: e.probability or 0, reverse=True)
    
    # Cap to max_plays
    top_edges = playable[:max_plays]
    
    return {
        "engine": "TOTAL_GAMES_ENGINE",
        "market": "TOTAL_GAMES",
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

def parse_paste_file(filepath: str, surface: str, tournament: str) -> List[TotalGamesCandidate]:
    """Parse paste file into candidates."""
    raw = Path(filepath).read_text(encoding="utf-8")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    
    candidates = []
    current_player = None
    current_opponent = None
    
    def clean_name(s):
        s = re.sub(r"goblin$|demon$", "", s, flags=re.IGNORECASE).strip()
        return s
    
    def is_time_line(s):
        return bool(re.search(r"\b(wed|thu|fri|sat|sun|mon|tue)\b", s, flags=re.IGNORECASE))
    
    def extract_opponent(s):
        s = s.strip()
        if s.startswith("@"):
            s = s[1:].strip()
        elif s.lower().startswith("vs"):
            s = s[2:].strip()
        s = re.sub(r"\b(wed|thu|fri|sat|sun|mon|tue)\b.*$", "", s, flags=re.IGNORECASE).strip()
        return clean_name(s)
    
    i = 0
    while i < len(lines):
        line = lines[i]
        low = line.lower()
        
        if is_time_line(line) and (line.startswith("@") or low.startswith("vs")):
            current_opponent = extract_opponent(line)
            i += 1
            continue
        
        try:
            value = float(line)
        except ValueError:
            value = None
        
        if value is not None:
            if i + 1 < len(lines) and lines[i + 1].strip().lower() == "total games":
                allowed = set()
                j = i + 2
                while j < len(lines):
                    nxt = lines[j].strip().lower()
                    if nxt in ("less", "more"):
                        allowed.add("UNDER" if nxt == "less" else "OVER")
                        j += 1
                        continue
                    if re.fullmatch(r"\d+(?:\.\d+)?", lines[j].strip()):
                        break
                    if lines[j].strip().endswith("- Player"):
                        break
                    if is_time_line(lines[j]):
                        break
                    j += 1
                
                if current_player and current_opponent:
                    is_wta = detect_wta(current_player, current_opponent)
                    best_of = infer_best_of(value, tournament, is_wta)
                    
                    candidates.append(TotalGamesCandidate(
                        player_a=clean_name(current_player),
                        player_b=clean_name(current_opponent),
                        surface=surface.upper(),
                        games_line=value,
                        tournament=tournament,
                        best_of=best_of,
                        allowed_directions=allowed or {"OVER", "UNDER"},
                    ))
                i = j
                continue
        
        if line.endswith("- Player"):
            nm = clean_name(line.replace("- Player", ""))
            if nm:
                current_player = nm
            i += 1
            continue
        
        noise = {"trending", "player", "total games", "less", "more"}
        if low not in noise and not line.startswith("@") and not low.startswith("vs"):
            if not re.fullmatch(r"\d+(?:\.\d+)?", line) and len(line) >= 3:
                current_player = clean_name(line)
        
        i += 1
    
    return candidates


def main():
    parser = argparse.ArgumentParser(description="Total Games Edge Generator")
    parser.add_argument("--paste-file", required=True, help="Input paste file")
    parser.add_argument("--surface", required=True, help="Surface (HARD/CLAY/GRASS/INDOOR)")
    parser.add_argument("--tournament", default="", help="Tournament name")
    parser.add_argument("--max-plays", type=int, default=2, help="Max plays to output")
    parser.add_argument("--output", help="Output JSON file")
    
    args = parser.parse_args()
    
    candidates = parse_paste_file(args.paste_file, args.surface, args.tournament)
    print(f"Parsed {len(candidates)} candidates")
    
    output = generate_all_edges(candidates, args.max_plays)
    
    # Save output
    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_path = OUTPUTS_DIR / f"totals_games_edges_{ts}.json"
    
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Output: {out_path}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("TOTAL GAMES ENGINE — OUTPUT")
    print(f"{'='*60}")
    print(f"Candidates: {output['total_candidates']} | Blocked: {output['blocked_count']} | Playable: {output['playable_count']}")
    print(f"Output: {output['output_count']} (max {output['max_plays']})")
    
    for e in output["edges"]:
        print(f"\n[{e['tier']}] {e['players'][0]} vs {e['players'][1]}")
        print(f"  {e['direction']} {e['line']} | P={e['probability']:.1%} | edge={e['edge']:+.1%}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
