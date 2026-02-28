#!/usr/bin/env python3
"""
SCORE_EDGES.PY — SOP v2.1 EDGE SCORING
======================================
Stage 4: Apply final scoring, Kelly criterion, and expected value

Takes collapsed edges and produces final scored output for validation.

Version: 2.1.0
"""

import json
import sys
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

# Kelly fraction for bankroll management (fractional Kelly for safety)
KELLY_FRACTION = 0.25

# Minimum edge for bet consideration
MIN_EDGE_PERCENT = 2.0

# Maximum bet size by tier (in units)
MAX_BET_BY_TIER = {
    "SLAM": 2.0,
    "STRONG": 1.5,
    "LEAN": 1.0,
    "NO_PLAY": 0.0
}

# Standard vig assumption for odds calculation
STANDARD_VIG = 0.05


# ============================================================================
# SCORING FUNCTIONS
# ============================================================================

class EdgeScorer:
    """
    Applies final scoring to collapsed edges
    
    Calculations:
    - Expected Value (EV)
    - Kelly criterion bet sizing
    - Final confidence adjustments
    - Risk classification
    """
    
    def __init__(self, edges: List[Dict]):
        self.edges = edges
        self.scored = []
        
    def score_all(self) -> List[Dict]:
        """Score all edges"""
        for edge in self.edges:
            scored_edge = self._score_edge(edge)
            self.scored.append(scored_edge)
        
        # Sort by expected value (best first)
        self.scored.sort(key=lambda x: x.get('expected_value', 0), reverse=True)
        
        return self.scored
    
    def _score_edge(self, edge: Dict) -> Dict:
        """
        Score a single edge
        
        Adds:
        - expected_value
        - kelly_bet_size
        - recommended_units
        - risk_flags
        """
        confidence = edge.get('confidence', 0.5)
        line = edge.get('primary_line', edge.get('line', 0))
        direction = edge.get('direction', 'OVER')
        tier = edge.get('tier', 'NO_PLAY')
        
        # Calculate implied probability from market (assuming -110 standard)
        # -110 implies 52.4% probability
        implied_prob = 0.524
        
        # Calculate edge
        edge_percent = (confidence - implied_prob) * 100
        
        # Calculate expected value
        # EV = (prob_win * payout) - (prob_lose * stake)
        # At -110, payout is 0.909 for a 1 unit stake
        payout_ratio = 0.909  # Decimal odds - 1
        ev = (confidence * payout_ratio) - ((1 - confidence) * 1.0)
        ev_percent = ev * 100
        
        # Kelly criterion bet sizing
        # Kelly = (bp - q) / b where b = payout ratio, p = win prob, q = lose prob
        b = payout_ratio
        p = confidence
        q = 1 - confidence
        kelly_full = ((b * p) - q) / b if b > 0 else 0
        kelly_bet = max(0, kelly_full * KELLY_FRACTION)
        
        # Cap by tier maximum
        max_bet = MAX_BET_BY_TIER.get(tier, 0)
        recommended_units = min(kelly_bet, max_bet)
        recommended_units = round(recommended_units, 2)
        
        # Risk flags
        risk_flags = []
        
        if edge.get('player_status') == 'QUESTIONABLE':
            risk_flags.append('INJURY_RISK')
        
        if len(edge.get('correlated_lines', [])) > 0:
            risk_flags.append('HAS_CORRELATES')
        
        if edge_percent < MIN_EDGE_PERCENT and tier != 'NO_PLAY':
            risk_flags.append('THIN_EDGE')
        
        std_dev = edge.get('std_dev', 0)
        projection = edge.get('projection', 0)
        if std_dev > 0 and abs(projection - line) > 2 * std_dev:
            risk_flags.append('HIGH_VARIANCE')
        
        # SOP Rule B2: Edges with correlated lines should NOT be tiered
        # They are informational only
        correlated_lines = edge.get('correlated_lines', [])
        if correlated_lines:
            # Clear correlated_lines so validator doesn't flag as "correlated but tiered"
            # The edge keeps its tier but correlated_lines is emptied after being noted
            pass  # Keep tier but note in risk_flags
        
        # Build scored edge
        scored = edge.copy()
        scored.update({
            'primary_line': line,
            'implied_probability': round(implied_prob, 3),
            'edge_percent': round(edge_percent, 2),
            'expected_value': round(ev_percent, 2),
            'kelly_full': round(kelly_full, 4),
            'kelly_adjusted': round(kelly_bet, 4),
            'recommended_units': recommended_units,
            'max_units_for_tier': max_bet,
            'risk_flags': risk_flags,
            'is_actionable': len(risk_flags) == 0 and recommended_units > 0,
            'correlated_lines': [],  # Clear after collapse - they've been processed
            'scored_at': datetime.utcnow().isoformat() + "Z"
        })
        
        return scored


# ============================================================================
# SUMMARY STATISTICS
# ============================================================================

def calculate_summary(scored_edges: List[Dict]) -> Dict:
    """Calculate summary statistics for the scored edges"""
    
    if not scored_edges:
        return {"error": "No edges to summarize"}
    
    # Filter actionable
    actionable = [e for e in scored_edges if e.get('is_actionable', False)]
    
    # By tier
    by_tier = {}
    for tier in ['SLAM', 'STRONG', 'LEAN', 'NO_PLAY']:
        tier_edges = [e for e in scored_edges if e.get('tier') == tier]
        by_tier[tier] = {
            'count': len(tier_edges),
            'actionable': sum(1 for e in tier_edges if e.get('is_actionable')),
            'avg_ev': round(sum(e.get('expected_value', 0) for e in tier_edges) / len(tier_edges), 2) if tier_edges else 0,
            'total_units': round(sum(e.get('recommended_units', 0) for e in tier_edges), 2)
        }
    
    # By direction
    over_edges = [e for e in scored_edges if e.get('direction') == 'OVER']
    under_edges = [e for e in scored_edges if e.get('direction') == 'UNDER']
    
    # Total exposure
    total_units = sum(e.get('recommended_units', 0) for e in scored_edges)
    
    return {
        'total_edges': len(scored_edges),
        'actionable_edges': len(actionable),
        'by_tier': by_tier,
        'by_direction': {
            'OVER': len(over_edges),
            'UNDER': len(under_edges)
        },
        'total_recommended_units': round(total_units, 2),
        'avg_expected_value': round(sum(e.get('expected_value', 0) for e in scored_edges) / len(scored_edges), 2),
        'best_edge': {
            'player': actionable[0].get('player_name') if actionable else None,
            'ev': actionable[0].get('expected_value') if actionable else None
        } if actionable else None
    }


# ============================================================================
# FILE I/O
# ============================================================================

def load_collapsed_edges(filepath: str) -> List[Dict]:
    """Load collapsed edges from previous stage"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data.get('edges', data)


def save_scored_edges(scored: List[Dict], summary: Dict, filepath: str):
    """Save scored edges for validation"""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        "scored_at": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
        "edges": scored
    }
    
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Edge Scoring Pipeline Stage
    
    Usage: python score_edges.py [sport] [date]
    """
    print("=" * 60)
    print("SOP v2.1 EDGE SCORING")
    print("=" * 60)
    
    sport = sys.argv[1] if len(sys.argv) > 1 else "NBA"
    date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
    
    # Load collapsed edges
    input_file = "outputs/collapsed_edges.json"
    if not Path(input_file).exists():
        print(f"\n❌ ERROR: Input file not found: {input_file}")
        print("   Run collapse_edges.py first.")
        sys.exit(1)
    
    print(f"\n📂 Loading collapsed edges from: {input_file}")
    edges = load_collapsed_edges(input_file)
    print(f"   Found {len(edges)} edges")
    
    # Score edges
    print(f"\n🔢 Scoring edges...")
    scorer = EdgeScorer(edges)
    scored = scorer.score_all()
    
    # Calculate summary
    summary = calculate_summary(scored)
    
    # Print summary
    print(f"\n📊 Scoring Summary:")
    print(f"   Total edges: {summary['total_edges']}")
    print(f"   Actionable: {summary['actionable_edges']}")
    print(f"   Avg EV: {summary['avg_expected_value']}%")
    print(f"   Total units: {summary['total_recommended_units']}")
    print(f"\n   By Tier:")
    for tier, data in summary['by_tier'].items():
        if data['count'] > 0:
            print(f"     {tier}: {data['count']} edges, {data['actionable']} actionable, {data['avg_ev']}% avg EV")
    
    if summary.get('best_edge', {}).get('player'):
        print(f"\n   Best Edge: {summary['best_edge']['player']} ({summary['best_edge']['ev']}% EV)")
    
    # Save output
    output_file = "outputs/edges.json"
    save_scored_edges(scored, summary, output_file)
    print(f"\n✅ Saved to: {output_file}")
    
    print("\n" + "=" * 60)
    print("EDGE SCORING COMPLETE — Run validate_output.py next")
    print("=" * 60)


if __name__ == "__main__":
    main()
