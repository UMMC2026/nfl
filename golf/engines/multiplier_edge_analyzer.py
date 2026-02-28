"""
Golf Multiplier-Based Edge Analyzer
===================================
Extract implied probabilities from Underdog multipliers.
When multipliers are asymmetric, the books are pricing in direction.

Key insight: Lower multiplier = books expect that outcome
- Higher 0.86x, Lower 1.07x → Books expect LOWER (they pay less for LOWER wins)
- Higher 1.07x, Lower 0.86x → Books expect HIGHER

This bypasses the coin-flip problem by using market-implied direction.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path


@dataclass
class MultiplierEdge:
    """An edge derived from multiplier asymmetry."""
    player: str
    market: str
    line: float
    direction: str  # "higher" or "lower" or "better"
    higher_mult: Optional[float]
    lower_mult: Optional[float]
    better_mult: Optional[float] = None
    
    # Derived values
    implied_prob_higher: float = 0.50
    implied_prob_lower: float = 0.50
    multiplier_edge: float = 0.0  # Asymmetry score
    recommended_direction: str = ""
    confidence: str = "LOW"  # LOW, MEDIUM, HIGH
    
    # Metadata
    tournament: str = ""
    round_num: int = 0
    tee_time: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "player": self.player,
            "market": self.market,
            "line": self.line,
            "direction": self.direction,
            "higher_mult": self.higher_mult,
            "lower_mult": self.lower_mult,
            "better_mult": self.better_mult,
            "implied_prob_higher": round(self.implied_prob_higher, 3),
            "implied_prob_lower": round(self.implied_prob_lower, 3),
            "multiplier_edge": round(self.multiplier_edge, 3),
            "recommended_direction": self.recommended_direction,
            "confidence": self.confidence,
            "tournament": self.tournament,
            "round_num": self.round_num,
            "tee_time": self.tee_time,
        }


def multiplier_to_implied_prob(mult: float) -> float:
    """
    Convert Underdog multiplier to implied probability.
    
    Underdog pays multiplier * stake on win.
    Lower multiplier = higher implied probability of that outcome.
    
    For a fair bet: implied_prob = 1 / (1 + multiplier - 1) = 1 / multiplier
    But Underdog has juice, so we adjust.
    
    Rough formula: implied_prob ≈ 1 / (multiplier + 0.05)
    """
    if mult <= 0:
        return 0.50
    
    # Underdog's multiplier includes their edge
    # A 1.0x multiplier means ~50% implied
    # A 0.8x multiplier means ~55-58% implied (they pay less = more likely)
    # A 1.2x multiplier means ~42-45% implied (they pay more = less likely)
    
    # Simple inversion with juice adjustment
    raw_prob = 1.0 / (mult + 0.10)  # +0.10 accounts for house edge
    
    # Clamp to reasonable range
    return max(0.30, min(0.70, raw_prob))


def calculate_multiplier_edge(higher_mult: Optional[float], lower_mult: Optional[float]) -> Tuple[str, float, str]:
    """
    Calculate which direction the books favor based on multiplier asymmetry.
    
    Returns:
        (recommended_direction, edge_magnitude, confidence)
    """
    if higher_mult is None or lower_mult is None:
        return ("", 0.0, "NONE")
    
    if higher_mult <= 0 or lower_mult <= 0:
        return ("", 0.0, "NONE")
    
    # Calculate asymmetry
    # If higher_mult < lower_mult → books expect HIGHER
    # If lower_mult < higher_mult → books expect LOWER
    
    diff = lower_mult - higher_mult
    
    if abs(diff) < 0.05:
        # Too close to call
        return ("", abs(diff), "NONE")
    
    if diff > 0:
        # higher_mult is lower → books favor HIGHER
        direction = "higher"
        confidence = "HIGH" if diff >= 0.15 else "MEDIUM" if diff >= 0.08 else "LOW"
    else:
        # lower_mult is lower → books favor LOWER
        direction = "lower"
        confidence = "HIGH" if abs(diff) >= 0.15 else "MEDIUM" if abs(diff) >= 0.08 else "LOW"
    
    return (direction, abs(diff), confidence)


def analyze_props_with_multipliers(props: List[Dict]) -> List[MultiplierEdge]:
    """
    Analyze parsed props and extract multiplier-based edges.
    
    Args:
        props: List of parsed prop dicts from underdog parser
        
    Returns:
        List of MultiplierEdge objects with recommendations
    """
    edges = []
    
    for prop in props:
        player = prop.get("player", "Unknown")
        market = prop.get("market", "")
        line = prop.get("line", 0.0)
        tournament = prop.get("tournament", "")
        round_num = prop.get("round", 0)
        tee_time = prop.get("tee_time", "")
        
        higher_mult = prop.get("higher_mult")
        lower_mult = prop.get("lower_mult")
        better_mult = prop.get("better_mult")
        
        # Skip if no multiplier data
        if higher_mult is None and lower_mult is None and better_mult is None:
            continue
        
        # Calculate implied probabilities
        implied_higher = multiplier_to_implied_prob(higher_mult) if higher_mult else 0.50
        implied_lower = multiplier_to_implied_prob(lower_mult) if lower_mult else 0.50
        
        # Get recommended direction from multiplier asymmetry
        rec_dir, edge_mag, confidence = calculate_multiplier_edge(higher_mult, lower_mult)
        
        # For finishing position, "better" = lower position number
        if market == "finishing_position" and better_mult:
            implied_better = multiplier_to_implied_prob(better_mult)
            
            # High confidence if better_mult is very low (books expect them to finish well)
            if better_mult < 0.75:
                confidence = "HIGH"
                rec_dir = "better"
                edge_mag = 1.0 - better_mult
            elif better_mult < 0.90:
                confidence = "MEDIUM"
                rec_dir = "better"
                edge_mag = 1.0 - better_mult
            else:
                # Better mult >= 0.90 means books don't expect top finish
                confidence = "LOW"
                rec_dir = ""
        
        edge = MultiplierEdge(
            player=player,
            market=market,
            line=line,
            direction=rec_dir,
            higher_mult=higher_mult,
            lower_mult=lower_mult,
            better_mult=better_mult,
            implied_prob_higher=implied_higher,
            implied_prob_lower=implied_lower,
            multiplier_edge=edge_mag,
            recommended_direction=rec_dir,
            confidence=confidence,
            tournament=tournament,
            round_num=round_num,
            tee_time=tee_time,
        )
        
        edges.append(edge)
    
    return edges


def filter_actionable_edges(edges: List[MultiplierEdge], min_confidence: str = "MEDIUM") -> List[MultiplierEdge]:
    """Filter to only actionable edges based on confidence level."""
    confidence_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
    min_level = confidence_order.get(min_confidence, 2)
    
    return [e for e in edges if confidence_order.get(e.confidence, 0) >= min_level]


def generate_multiplier_report(edges: List[MultiplierEdge]) -> str:
    """Generate human-readable report from multiplier analysis."""
    lines = []
    lines.append("=" * 70)
    lines.append("⛳ GOLF MULTIPLIER EDGE ANALYSIS — Farmers Insurance Open R4")
    lines.append(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("   Method: Underdog Multiplier Asymmetry (Market-Implied Direction)")
    lines.append("=" * 70)
    lines.append("")
    
    # Filter to actionable
    actionable = filter_actionable_edges(edges, "MEDIUM")
    high_conf = [e for e in edges if e.confidence == "HIGH"]
    
    lines.append(f"📊 SUMMARY")
    lines.append(f"   Total Props Analyzed: {len(edges)}")
    lines.append(f"   Actionable Edges: {len(actionable)}")
    lines.append(f"   HIGH Confidence: {len(high_conf)}")
    lines.append("")
    
    # HIGH confidence edges
    if high_conf:
        lines.append("=" * 70)
        lines.append("🎯 HIGH CONFIDENCE EDGES (Strong Multiplier Asymmetry)")
        lines.append("=" * 70)
        lines.append("")
        
        for e in sorted(high_conf, key=lambda x: x.multiplier_edge, reverse=True):
            lines.append(f"  {e.player} — {e.market.upper()} {e.line}")
            lines.append(f"    Direction: {e.recommended_direction.upper()}")
            lines.append(f"    Multipliers: Higher {e.higher_mult}x | Lower {e.lower_mult}x")
            if e.better_mult:
                lines.append(f"    Better: {e.better_mult}x")
            lines.append(f"    Edge Magnitude: {e.multiplier_edge:.2f}")
            lines.append(f"    ⚠️  RESEARCH-ONLY (Golf SOP v1.0)")
            lines.append("")
    
    # MEDIUM confidence edges
    medium_conf = [e for e in edges if e.confidence == "MEDIUM"]
    if medium_conf:
        lines.append("=" * 70)
        lines.append("📋 MEDIUM CONFIDENCE EDGES")
        lines.append("=" * 70)
        lines.append("")
        
        for e in sorted(medium_conf, key=lambda x: x.multiplier_edge, reverse=True):
            lines.append(f"  {e.player} — {e.market.upper()} {e.line}")
            lines.append(f"    Direction: {e.recommended_direction.upper()}")
            lines.append(f"    Multipliers: Higher {e.higher_mult}x | Lower {e.lower_mult}x")
            lines.append("")
    
    # Finishing position special section
    finish_edges = [e for e in edges if e.market == "finishing_position"]
    if finish_edges:
        lines.append("=" * 70)
        lines.append("🏆 FINISHING POSITION ANALYSIS")
        lines.append("=" * 70)
        lines.append("")
        
        for e in sorted(finish_edges, key=lambda x: x.better_mult or 2.0):
            mult_display = e.better_mult or "N/A"
            confidence_emoji = "🟢" if e.confidence == "HIGH" else "🟡" if e.confidence == "MEDIUM" else "⚪"
            lines.append(f"  {confidence_emoji} {e.player} — Top {e.line} | Better: {mult_display}x")
    
    lines.append("")
    lines.append("=" * 70)
    lines.append("⚠️  GOVERNANCE NOTICE")
    lines.append("=" * 70)
    lines.append("   Golf module is in RESEARCH-ONLY phase.")
    lines.append("   Multiplier edges are for observation, NOT betting.")
    lines.append("   No course priors = no Monte Carlo optimization.")
    lines.append("=" * 70)
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Demo with sample data
    sample_props = [
        {
            "player": "Justin Rose",
            "market": "round_strokes",
            "line": 71.5,
            "higher_mult": 0.88,
            "lower_mult": 1.03,
            "tournament": "Farmers Insurance Open",
            "round": 4,
        },
        {
            "player": "Brooks Koepka",
            "market": "round_strokes",
            "line": 71.5,
            "higher_mult": 0.86,
            "lower_mult": 1.07,
            "tournament": "Farmers Insurance Open",
            "round": 4,
        },
        {
            "player": "Si Woo Kim",
            "market": "finishing_position",
            "line": 5.5,
            "better_mult": 0.70,
            "tournament": "Farmers Insurance Open",
            "round": 4,
        },
    ]
    
    edges = analyze_props_with_multipliers(sample_props)
    report = generate_multiplier_report(edges)
    print(report)
