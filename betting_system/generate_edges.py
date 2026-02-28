#!/usr/bin/env python3
"""
GENERATE_EDGES.PY — SOP v2.1 EDGE GENERATION
============================================
Stage 2: Generate raw betting lines from model projections

This stage creates ALL possible lines - collapse_edges.py will
reduce them to unique edges per Rule A2.

Version: 2.1.0
"""

import json
import sys
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import statistics


# ============================================================================
# CONFIGURATION
# ============================================================================

# Minimum games for reliable projection
MIN_GAMES_FOR_PROJECTION = 3

# Minimum confidence to generate a line
MIN_CONFIDENCE_THRESHOLD = 0.55

# Stats we generate edges for by sport
SUPPORTED_STATS = {
    "NBA": ["points", "rebounds", "assists", "three_pointers", "steals", "blocks"],
    "NFL": ["passing_yards", "rushing_yards", "receiving_yards", "receptions", "touchdowns"],
    "WNBA": ["points", "rebounds", "assists"],
    "CFB": ["passing_yards", "rushing_yards", "receiving_yards"],
    "CBB": ["points", "rebounds", "assists"]
}


# ============================================================================
# PROJECTION MODEL
# ============================================================================

class ProjectionModel:
    """
    Simple projection model based on historical averages
    
    In production: Replace with your actual model (Bayesian, ML, etc.)
    This is a baseline implementation for the pipeline.
    """
    
    def __init__(self, historical_stats: List[Dict]):
        self.stats = historical_stats
        self._build_player_profiles()
    
    def _build_player_profiles(self):
        """Build statistical profiles for each player"""
        self.profiles = {}
        
        # Group stats by player and stat type
        for stat in self.stats:
            player_id = stat['player_id']
            stat_type = stat['stat_type']
            value = stat['value']
            
            if player_id not in self.profiles:
                self.profiles[player_id] = {}
            if stat_type not in self.profiles[player_id]:
                self.profiles[player_id][stat_type] = []
            
            self.profiles[player_id][stat_type].append(value)
    
    def project(self, player_id: str, stat_type: str) -> Optional[Dict]:
        """
        Generate projection for player/stat
        
        Returns:
            {
                "projection": float,
                "std_dev": float,
                "sample_size": int,
                "confidence_base": float
            }
        """
        if player_id not in self.profiles:
            return None
        if stat_type not in self.profiles[player_id]:
            return None
        
        values = self.profiles[player_id][stat_type]
        
        if len(values) < MIN_GAMES_FOR_PROJECTION:
            return None
        
        # Calculate projection (weighted recent average)
        # More weight on recent games
        weights = [1.2, 1.1, 1.0, 0.9, 0.8][:len(values)]
        weighted_sum = sum(v * w for v, w in zip(values, weights))
        weighted_avg = weighted_sum / sum(weights)
        
        # Standard deviation
        std_dev = statistics.stdev(values) if len(values) > 1 else values[0] * 0.15
        
        # Base confidence from sample consistency
        cv = std_dev / weighted_avg if weighted_avg > 0 else 1.0  # Coefficient of variation
        confidence_base = max(0.5, min(0.85, 1.0 - cv))
        
        return {
            "projection": round(weighted_avg, 1),
            "std_dev": round(std_dev, 2),
            "sample_size": len(values),
            "confidence_base": round(confidence_base, 3)
        }


# ============================================================================
# EDGE GENERATION
# ============================================================================

class EdgeGenerator:
    """
    Generates raw betting lines from projections and market data
    
    Output: ALL possible lines (before collapse)
    """
    
    def __init__(self, sport: str, ingested_data: Dict):
        self.sport = sport
        self.data = ingested_data
        self.model = ProjectionModel(ingested_data.get('historical_stats', []))
        self.lines_generated = []
        
    def generate_all(self) -> List[Dict]:
        """
        Generate lines for all players and market lines
        """
        market_lines = self.data.get('market_lines', [])
        players = {p['player_id']: p for p in self.data.get('players', [])}
        
        for market_line in market_lines:
            player_id = market_line['player_id']
            player_name = market_line['player_name']
            game_id = market_line['game_id']
            stat_type = market_line['stat_type']
            line = market_line['line']
            
            # Get projection
            projection = self.model.project(player_id, stat_type)
            if not projection:
                continue
            
            # Get player status
            player = players.get(player_id, {})
            if player.get('status') == 'OUT':
                continue
            
            # Generate OVER edge
            over_edge = self._create_edge(
                player_id=player_id,
                player_name=player_name,
                game_id=game_id,
                stat_type=stat_type,
                line=line,
                direction="OVER",
                projection=projection,
                player_status=player.get('status', 'ACTIVE')
            )
            if over_edge:
                self.lines_generated.append(over_edge)
            
            # Generate UNDER edge
            under_edge = self._create_edge(
                player_id=player_id,
                player_name=player_name,
                game_id=game_id,
                stat_type=stat_type,
                line=line,
                direction="UNDER",
                projection=projection,
                player_status=player.get('status', 'ACTIVE')
            )
            if under_edge:
                self.lines_generated.append(under_edge)
        
        return self.lines_generated
    
    def _create_edge(self, player_id: str, player_name: str, game_id: str,
                     stat_type: str, line: float, direction: str,
                     projection: Dict, player_status: str) -> Optional[Dict]:
        """
        Create a single edge with confidence calculation
        
        SOP Rules Applied:
        - C1: Confidence compression for extreme projections
        - C2: Tier must match probability
        """
        proj_value = projection['projection']
        std_dev = projection['std_dev']
        
        # Calculate raw probability using normal distribution approximation
        if direction == "OVER":
            # P(X > line) where X ~ N(proj, std_dev)
            z_score = (proj_value - line) / std_dev if std_dev > 0 else 0
            raw_prob = self._normal_cdf(z_score)
        else:  # UNDER
            # P(X < line)
            z_score = (line - proj_value) / std_dev if std_dev > 0 else 0
            raw_prob = self._normal_cdf(z_score)
        
        # Apply confidence base adjustment
        confidence = raw_prob * projection['confidence_base'] + (1 - projection['confidence_base']) * 0.5
        
        # SOP Rule C1: Confidence compression
        distance = abs(proj_value - line)
        if std_dev > 0 and distance > 2.5 * std_dev:
            confidence = min(confidence, 0.65)
        
        # Apply injury status adjustment
        if player_status == "QUESTIONABLE":
            confidence *= 0.9
        elif player_status == "DOUBTFUL":
            confidence *= 0.8
        
        confidence = round(confidence, 3)
        
        # Skip if below threshold
        if confidence < MIN_CONFIDENCE_THRESHOLD:
            return None
        
        # Determine tier (SOP Rule C2)
        tier = self._get_tier(confidence)
        
        return {
            "player_id": player_id,
            "player_name": player_name,
            "game_id": game_id,
            "stat_type": stat_type,
            "direction": direction,
            "line": line,
            "projection": proj_value,
            "std_dev": std_dev,
            "confidence": confidence,
            "tier": tier,
            "player_status": player_status,
            "data_sources": self.data.get('data_sources_used', []),
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
    
    def _normal_cdf(self, z: float) -> float:
        """Approximate normal CDF using error function"""
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))
    
    def _get_tier(self, confidence: float) -> str:
        """Determine tier based on confidence (SOP Rule C2)"""
        if confidence >= 0.75:
            return "SLAM"
        elif confidence >= 0.65:
            return "STRONG"
        elif confidence >= 0.55:
            return "LEAN"
        else:
            return "NO_PLAY"


# ============================================================================
# FILE I/O
# ============================================================================

def load_ingested_data(filepath: str) -> Dict:
    """Load ingested data from previous stage"""
    with open(filepath, 'r') as f:
        return json.load(f)


def save_raw_lines(lines: List[Dict], filepath: str):
    """Save raw lines for collapse stage"""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_lines": len(lines),
        "lines": lines
    }
    
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Edge Generation Pipeline Stage
    
    Usage: python generate_edges.py [sport] [date]
    """
    print("=" * 60)
    print("SOP v2.1 EDGE GENERATION")
    print("=" * 60)
    
    sport = sys.argv[1] if len(sys.argv) > 1 else "NBA"
    date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
    
    # Load ingested data
    input_file = "outputs/ingested_data.json"
    if not Path(input_file).exists():
        print(f"\n❌ ERROR: Input file not found: {input_file}")
        print("   Run ingest_data.py first.")
        sys.exit(1)
    
    print(f"\n📂 Loading data from: {input_file}")
    data = load_ingested_data(input_file)
    
    # Generate edges
    print(f"\n🔄 Generating edges for {sport}...")
    generator = EdgeGenerator(sport, data)
    lines = generator.generate_all()
    
    # Summary
    print(f"\n📊 Generation Results:")
    print(f"   Total lines generated: {len(lines)}")
    
    # Count by direction
    over_count = sum(1 for l in lines if l['direction'] == 'OVER')
    under_count = sum(1 for l in lines if l['direction'] == 'UNDER')
    print(f"   OVER lines: {over_count}")
    print(f"   UNDER lines: {under_count}")
    
    # Count by tier
    tier_counts = {}
    for line in lines:
        tier = line['tier']
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    print(f"   By tier: {tier_counts}")
    
    # Save output
    output_file = "outputs/raw_lines.json"
    save_raw_lines(lines, output_file)
    print(f"\n✅ Saved to: {output_file}")
    
    print("\n" + "=" * 60)
    print("EDGE GENERATION COMPLETE — Run collapse_edges.py next")
    print("=" * 60)


if __name__ == "__main__":
    main()
