"""
TENNIS EDGE SCHEMA v2.1 - SOP COMPLIANT
========================================
Canonical edge definitions with correlation tracking.

Usage:
    from tennis.ingest.tennis_edge_schema import TennisMatchIngest, ingest_match_json
    
    # From JSON string or dict
    match = ingest_match_json(json_data)
    edges = match.to_edges()  # Returns List[TennisEdge]
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CORRELATION GROUPS - MANDATORY FOR SOP v2.1
# ============================================================================

CORRELATION_GROUPS = {
    # Games correlations (sum constraint)
    "games": ["games_played", "games_won"],
    
    # Set correlations  
    "sets": ["sets_played", "sets_won"],
    
    # Breakpoint correlations (opponent service dependency)
    "breakpoints": ["breakpoints_won", "breakpoints_faced"],
    
    # Serve correlations
    "serve": ["aces", "double_faults", "first_serve_pct"],
    
    # Tiebreak correlations
    "tiebreak": ["tiebreakers_played", "tiebreakers_won"],
}

# Stats that MUST be flagged as correlated
CORRELATED_STATS = {
    "games_won": ["games_played", "games_won"],  # Both players' games_won sum to games_played
    "sets_won": ["sets_played", "sets_won"],
    "breakpoints_won": ["breakpoints_won", "games_won"],  # More breaks = more games won
    "aces": ["games_won", "sets_played"],  # More sets = more serve games = more aces
}

# Distribution types (NOT Gaussian for all)
STAT_DISTRIBUTIONS = {
    "games_played": "bounded",      # 12-39 for Bo3, 18-65 for Bo5
    "games_won": "bounded",         # 0 to games_played
    "sets_played": "discrete",      # 2 or 3 for Bo3, 3-5 for Bo5
    "sets_won": "discrete",         # 0, 1, 2 for Bo3
    "aces": "poisson",              # Count data
    "double_faults": "poisson",     # Count data
    "breakpoints_won": "poisson",   # Count data - NEVER GAUSSIAN
    "breakpoints_faced": "poisson", # Count data
    "tiebreakers_played": "poisson", # 0, 1, 2, 3...
}


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class MarketLine:
    """Single line offering (MORE/LESS)"""
    direction: str  # "MORE" or "LESS"
    payout: float
    implied_prob: float = 0.0
    
    def __post_init__(self):
        # Calculate implied probability from payout
        if self.payout > 0 and self.implied_prob == 0:
            self.implied_prob = 1.0 / self.payout


@dataclass
class EdgeDefinition:
    """
    CANONICAL EDGE = (player, stat, direction)
    Line is an expression of the edge, not a separate edge.
    """
    edge_id: str
    player: str
    stat: str
    line: float
    market_lines: Dict[str, MarketLine] = field(default_factory=dict)
    
    # Correlation tracking
    correlation_group: str = ""
    is_correlated_with: List[str] = field(default_factory=list)
    
    # Modeling metadata
    distribution: str = "gaussian"  # poisson, bounded, discrete, gaussian
    modeling_notes: str = ""
    
    # State
    is_primary: bool = True  # False if collapsed into another edge
    
    def __post_init__(self):
        # Auto-assign distribution type
        if self.stat in STAT_DISTRIBUTIONS:
            self.distribution = STAT_DISTRIBUTIONS[self.stat]
        
        # Auto-assign correlation group
        for group_name, stats in CORRELATION_GROUPS.items():
            if self.stat in stats:
                self.correlation_group = group_name
                break
        
        # Auto-flag correlated stats
        if self.stat in CORRELATED_STATS:
            self.is_correlated_with = CORRELATED_STATS[self.stat]


@dataclass
class TennisMatchIngest:
    """
    Full match ingest with all edges and metadata.
    """
    sport: str = "TENNIS"
    tour: str = "ATP"
    match_id: str = ""
    scheduled_time: str = ""
    player_a: str = ""
    player_b: str = ""
    match_format: str = "BEST_OF_3"
    surface: str = "UNKNOWN"
    data_source: str = "underdog"
    
    edges: List[EdgeDefinition] = field(default_factory=list)
    correlations: List[List[str]] = field(default_factory=list)
    
    # Validation gates
    surface_known: bool = False
    match_format_confirmed: bool = True
    retirement_rules_loaded: bool = True
    correlated_edges_flagged: bool = False
    
    def __post_init__(self):
        # Auto-validate
        self.surface_known = self.surface not in ["UNKNOWN", ""]
        self._flag_correlations()
    
    def _flag_correlations(self):
        """Auto-detect and flag correlated edges."""
        if not self.edges:
            self.correlated_edges_flagged = True  # No edges = nothing to flag
            return
        
        # Build correlation map
        edge_by_stat = {}
        for edge in self.edges:
            key = f"{edge.player}_{edge.stat}"
            edge_by_stat[key] = edge
        
        # Flag correlations
        # 1. Games won between players must sum to games played
        for edge in self.edges:
            if edge.stat == "games_won":
                other_player = self.player_b if edge.player == self.player_a else self.player_a
                other_key = f"{other_player}_games_won"
                if other_key in edge_by_stat:
                    if other_key not in edge.is_correlated_with:
                        edge.is_correlated_with.append(other_key)
                    corr_pair = sorted([edge.edge_id, edge_by_stat[other_key].edge_id])
                    if corr_pair not in self.correlations:
                        self.correlations.append(corr_pair)
        
        # Always mark as flagged after processing
        self.correlated_edges_flagged = True
    
    def to_edges(self) -> List[Dict]:
        """
        Convert to TennisEdge format for pipeline.
        Returns list of edge dicts ready for collapse_edges().
        """
        result = []
        for edge in self.edges:
            for direction, market in edge.market_lines.items():
                result.append({
                    "edge_id": edge.edge_id,
                    "player": edge.player,
                    "opponent": self.player_b if edge.player == self.player_a else self.player_a,
                    "stat": edge.stat,
                    "market": edge.stat,  # Alias
                    "line": edge.line,
                    "direction": direction.upper(),
                    "payout": market.payout,
                    "implied_prob": market.implied_prob,
                    "match_id": self.match_id,
                    "correlation_group": edge.correlation_group,
                    "is_correlated_with": edge.is_correlated_with,
                    "is_primary": edge.is_primary,
                    "distribution": edge.distribution,
                    "surface": self.surface,
                    "match_format": self.match_format,
                })
        return result
    
    def validate(self) -> Dict[str, Any]:
        """
        Run validation gates. Returns dict with pass/fail status.
        """
        results = {
            "passed": True,
            "gates": {},
            "warnings": [],
            "errors": []
        }
        
        # Gate 1: Surface known
        results["gates"]["surface_known"] = self.surface_known
        if not self.surface_known:
            results["warnings"].append("Surface unknown - BLOCK learning")
        
        # Gate 2: Match format
        results["gates"]["match_format_confirmed"] = self.match_format_confirmed
        
        # Gate 3: Correlations flagged
        results["gates"]["correlated_edges_flagged"] = self.correlated_edges_flagged
        if not self.correlated_edges_flagged:
            results["errors"].append("Correlated edges not flagged - HARD FAIL")
            results["passed"] = False
        
        # Gate 4: No duplicate edges
        edge_keys = set()
        for edge in self.edges:
            key = f"{edge.player}_{edge.stat}"
            if key in edge_keys:
                results["errors"].append(f"Duplicate edge: {key} - HARD FAIL")
                results["passed"] = False
            edge_keys.add(key)
        
        # Gate 5: Breakpoints using Poisson
        for edge in self.edges:
            if "breakpoint" in edge.stat.lower() and edge.distribution != "poisson":
                results["warnings"].append(f"{edge.edge_id} should use Poisson, not {edge.distribution}")
        
        return results


# ============================================================================
# INGEST FUNCTIONS
# ============================================================================

def ingest_match_json(data: Any) -> TennisMatchIngest:
    """
    Parse match JSON into TennisMatchIngest.
    
    Accepts:
    - Dict with match metadata and edges
    - JSON string
    - File path to JSON file
    """
    if isinstance(data, str):
        if data.strip().startswith('{'):
            data = json.loads(data)
        else:
            # Assume file path
            with open(data) as f:
                data = json.load(f)
    
    # Extract players
    players = data.get("players", {})
    player_a = players.get("player_a", "")
    player_b = players.get("player_b", "")
    
    # Create match
    match = TennisMatchIngest(
        sport=data.get("sport", "TENNIS"),
        tour=data.get("tour", "ATP"),
        match_id=data.get("match_id", ""),
        scheduled_time=data.get("scheduled_time", ""),
        player_a=player_a,
        player_b=player_b,
        match_format=data.get("match_format", "BEST_OF_3"),
        surface=data.get("surface", "UNKNOWN"),
        data_source=data.get("data_source", "underdog"),
    )
    
    # Parse edges if provided separately
    if "edges" in data:
        for edge_data in data["edges"]:
            edge = parse_edge_json(edge_data, player_a, player_b)
            if edge:
                match.edges.append(edge)
    
    return match


def parse_edge_json(data: Dict, player_a: str = "", player_b: str = "") -> Optional[EdgeDefinition]:
    """
    Parse single edge JSON into EdgeDefinition.
    
    Supports both formats:
    - Full format with market_lines dict
    - Simple format with just line and direction
    """
    edge_id = data.get("edge_id", "")
    player = data.get("player", "")
    stat = data.get("stat", "")
    line = data.get("line", 0.0)
    
    if not all([edge_id, stat, line]):
        return None
    
    # Parse market lines
    market_lines = {}
    if "market_lines" in data:
        for direction, market_data in data["market_lines"].items():
            if isinstance(market_data, dict):
                market_lines[direction] = MarketLine(
                    direction=direction,
                    payout=market_data.get("payout", 1.0)
                )
    
    return EdgeDefinition(
        edge_id=edge_id,
        player=player or player_a,
        stat=stat,
        line=line,
        market_lines=market_lines,
        modeling_notes=data.get("notes", "")
    )


def ingest_machac_gea_match() -> TennisMatchIngest:
    """
    Hardcoded ingest for Macháč vs Gea match.
    Used for testing and reference.
    """
    match = TennisMatchIngest(
        sport="TENNIS",
        tour="ATP",
        match_id="ATP_2026_02_05_MACHAC_GEA",
        scheduled_time="2026-02-05T13:30:00",
        player_a="Tomas Machac",
        player_b="Arthur Gea",
        match_format="BEST_OF_3",
        surface="UNKNOWN",
        data_source="Underdog UI scrape"
    )
    
    # Edge 1: Games Played (match total)
    match.edges.append(EdgeDefinition(
        edge_id="MACHAC_GEA_GAMES_PLAYED",
        player="MATCH_TOTAL",
        stat="games_played",
        line=22.5,
        market_lines={
            "MORE": MarketLine("MORE", 1.72),
            "LESS": MarketLine("LESS", 1.84)
        },
        modeling_notes="Total games across entire match"
    ))
    
    # Edge 2: Games Won (Macháč)
    match.edges.append(EdgeDefinition(
        edge_id="MACHAC_GAMES_WON",
        player="Tomas Machac",
        stat="games_won",
        line=12.5,
        market_lines={
            "MORE": MarketLine("MORE", 1.66),
            "LESS": MarketLine("LESS", 1.92)
        }
    ))
    
    # Edge 3: Games Won (Gea)
    match.edges.append(EdgeDefinition(
        edge_id="GEA_GAMES_WON",
        player="Arthur Gea",
        stat="games_won",
        line=11.5,
        market_lines={
            "MORE": MarketLine("MORE", 1.78),
            "LESS": MarketLine("LESS", 1.79)
        }
    ))
    
    # Edge 4: Breakpoints Won (Macháč)
    match.edges.append(EdgeDefinition(
        edge_id="MACHAC_BREAKPOINTS_WON",
        player="Tomas Machac",
        stat="breakpoints_won",
        line=3.5,
        market_lines={
            "MORE": MarketLine("MORE", 2.09),
            "LESS": MarketLine("LESS", 1.54)
        }
    ))
    
    # Edge 5: Breakpoints Won (Gea)
    match.edges.append(EdgeDefinition(
        edge_id="GEA_BREAKPOINTS_WON",
        player="Arthur Gea",
        stat="breakpoints_won",
        line=1.5,
        market_lines={
            "MORE": MarketLine("MORE", 1.55),
            "LESS": MarketLine("LESS", 2.08)
        }
    ))
    
    return match


# ============================================================================
# COLLAPSE EDGES - SOP v2.1 REQUIRED
# ============================================================================

def collapse_tennis_edges(edges: List[Dict]) -> List[Dict]:
    """
    Collapse edges per SOP v2.1:
    - HIGHER → keep highest line
    - LOWER → keep lowest line
    - Flag non-primary edges
    
    Returns collapsed list with is_primary set correctly.
    """
    # Group by (player, stat, direction)
    groups = {}
    for edge in edges:
        key = (edge["player"], edge["stat"], edge["direction"])
        if key not in groups:
            groups[key] = []
        groups[key].append(edge)
    
    result = []
    for (player, stat, direction), group in groups.items():
        if len(group) == 1:
            group[0]["is_primary"] = True
            result.append(group[0])
            continue
        
        # Multiple lines for same edge - collapse
        if direction == "HIGHER":
            # Keep highest line (hardest to hit)
            primary = max(group, key=lambda x: x["line"])
        else:
            # Keep lowest line (hardest to hit)
            primary = min(group, key=lambda x: x["line"])
        
        primary["is_primary"] = True
        result.append(primary)
        
        # Mark others as collapsed
        for edge in group:
            if edge != primary:
                edge["is_primary"] = False
                edge["collapsed_into"] = primary["edge_id"]
    
    return result


def validate_parlay_correlations(picks: List[Dict]) -> Dict[str, Any]:
    """
    Validate that parlay doesn't contain correlated edges.
    
    Returns:
        {
            "valid": True/False,
            "conflicts": [(edge1, edge2, reason), ...]
        }
    """
    conflicts = []
    
    for i, pick1 in enumerate(picks):
        for pick2 in picks[i+1:]:
            # Same player, correlated stats
            if pick1["player"] == pick2["player"]:
                stat1, stat2 = pick1["stat"], pick2["stat"]
                
                # Check if in same correlation group
                for group_name, stats in CORRELATION_GROUPS.items():
                    if stat1 in stats and stat2 in stats:
                        conflicts.append((
                            pick1["edge_id"],
                            pick2["edge_id"],
                            f"Both in {group_name} correlation group"
                        ))
            
            # Different players but games_won (sum constraint)
            if pick1["stat"] == "games_won" and pick2["stat"] == "games_won":
                if pick1["match_id"] == pick2["match_id"]:
                    conflicts.append((
                        pick1["edge_id"],
                        pick2["edge_id"],
                        "Both players' games_won sum to games_played - HARD CORRELATION"
                    ))
    
    return {
        "valid": len(conflicts) == 0,
        "conflicts": conflicts
    }


# ============================================================================
# CLI TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TENNIS EDGE SCHEMA v2.1 - TEST")
    print("=" * 60)
    
    # Load test match
    match = ingest_machac_gea_match()
    
    print(f"\nMatch: {match.player_a} vs {match.player_b}")
    print(f"Match ID: {match.match_id}")
    print(f"Format: {match.match_format}")
    print(f"Surface: {match.surface} (known: {match.surface_known})")
    
    print(f"\nEdges ({len(match.edges)}):")
    for edge in match.edges:
        print(f"  - {edge.edge_id}")
        print(f"    Player: {edge.player} | Stat: {edge.stat} | Line: {edge.line}")
        print(f"    Distribution: {edge.distribution}")
        print(f"    Correlation Group: {edge.correlation_group or 'None'}")
        if edge.is_correlated_with:
            print(f"    Correlated With: {edge.is_correlated_with}")
    
    print("\nValidation Gates:")
    validation = match.validate()
    for gate, status in validation["gates"].items():
        print(f"  - {gate}: {'PASS' if status else 'FAIL'}")
    
    if validation["warnings"]:
        print("\nWarnings:")
        for w in validation["warnings"]:
            print(f"  ⚠️ {w}")
    
    if validation["errors"]:
        print("\nErrors:")
        for e in validation["errors"]:
            print(f"  ❌ {e}")
    
    print(f"\nOverall: {'PASS' if validation['passed'] else 'FAIL'}")
    
    # Test edge export
    print("\n" + "=" * 60)
    print("EDGE EXPORT (for pipeline)")
    print("=" * 60)
    edges = match.to_edges()
    print(f"Exported {len(edges)} edge entries")
    for e in edges[:4]:
        print(f"  {e['player']} | {e['stat']} {e['direction']} {e['line']} | dist={e['distribution']}")
