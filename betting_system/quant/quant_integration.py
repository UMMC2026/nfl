#!/usr/bin/env python3
"""
QUANT_INTEGRATION.PY — SOP v2.1 COMPLETE QUANT FRAMEWORK
========================================================
Integrates all missing components into a single pipeline.

This module combines:
1. Multi-window weighted projection (L3/L5/L10/L20/Season)
2. Variance penalty (CV-based)
3. Edge threshold gate (3% minimum)
4. Professional output format

COPY THIS INTO YOUR risk_first_analyzer.py TO FIX YOUR SYSTEM.

Version: 2.1.0
Author: SOP v2.1 Integration
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json

# Import the components we built
from multi_window_projection import (
    MultiWindowProjectionEngine,
    MultiWindowProjection,
    format_projection_report
)
from variance_penalty import (
    apply_variance_penalty,
    VariancePenaltyResult,
    format_variance_report
)
from edge_threshold_gate import (
    check_edge_gate,
    EdgeGateResult,
    format_edge_report
)


# ============================================================================
# COMPLETE ANALYSIS RESULT
# ============================================================================

@dataclass
class QuantAnalysisResult:
    """Complete professional quant analysis for a single prop"""
    
    # Player/Prop info
    player_id: str
    player_name: str
    stat_type: str
    line: float
    direction: str  # OVER or UNDER
    
    # Multi-window projection
    projection: MultiWindowProjection
    
    # Variance analysis
    variance: VariancePenaltyResult
    
    # Edge gate
    edge_gate: EdgeGateResult
    
    # Final outputs
    final_confidence: float
    final_tier: str
    is_actionable: bool
    recommended_units: float
    
    # Risk flags
    risk_flags: List[str]
    
    # Data quality
    data_sources: List[str]
    sample_size: int


# ============================================================================
# MAIN ANALYSIS ENGINE
# ============================================================================

class ProfessionalQuantEngine:
    """
    Complete professional quant analysis engine.
    
    This is what your system SHOULD be doing.
    """
    
    def __init__(self):
        self.projection_engine = MultiWindowProjectionEngine()
        
    def analyze_prop(
        self,
        player_id: str,
        player_name: str,
        stat_type: str,
        game_log: List[float],
        line: float,
        direction: str,
        data_sources: List[str],
        odds: int = -110
    ) -> QuantAnalysisResult:
        """
        Run complete professional analysis on a single prop.
        
        Args:
            player_id: Unique identifier
            player_name: Display name
            stat_type: points, assists, rebounds, etc.
            game_log: List of stat values, most recent first
            line: Betting line
            direction: "OVER" or "UNDER"
            data_sources: List of data sources used
            odds: American odds (default -110)
            
        Returns:
            QuantAnalysisResult with complete analysis
        """
        
        # Step 1: Multi-window projection
        projection = self.projection_engine.calculate_projection(
            player_id=player_id,
            player_name=player_name,
            stat_type=stat_type,
            game_log=game_log,
            line=line
        )
        
        # Step 2: Calculate raw confidence from z-score
        raw_confidence = self._calculate_raw_confidence(
            projection.z_score,
            direction
        )
        
        # Step 3: Apply variance penalty
        variance_result = apply_variance_penalty(
            confidence=raw_confidence,
            std_dev=projection.combined_std_dev,
            mean=projection.weighted_projection,
            sample_size=len(game_log)
        )
        
        # Step 4: Apply SOP v2.1 compression rule
        compressed_confidence = self._apply_compression(
            variance_result.adjusted_confidence,
            projection.z_score
        )
        
        # Step 5: Check edge gate
        edge_result = check_edge_gate(compressed_confidence, odds)
        
        # Step 6: Determine final outputs
        final_confidence = compressed_confidence
        final_tier = edge_result.tier_recommendation
        is_actionable = edge_result.passes_gate and final_tier in ["SLAM", "STRONG", "LEAN"]
        
        # Step 7: Calculate recommended units (Kelly-based)
        recommended_units = self._calculate_kelly_units(
            edge_result.edge,
            final_tier
        )
        
        # Step 8: Compile risk flags
        risk_flags = self._compile_risk_flags(
            projection, variance_result, edge_result, direction
        )
        
        return QuantAnalysisResult(
            player_id=player_id,
            player_name=player_name,
            stat_type=stat_type,
            line=line,
            direction=direction,
            projection=projection,
            variance=variance_result,
            edge_gate=edge_result,
            final_confidence=round(final_confidence, 4),
            final_tier=final_tier,
            is_actionable=is_actionable,
            recommended_units=round(recommended_units, 2),
            risk_flags=risk_flags,
            data_sources=data_sources,
            sample_size=len(game_log)
        )
    
    def _calculate_raw_confidence(self, z_score: float, direction: str) -> float:
        """Convert z-score to confidence using normal CDF approximation"""
        import math
        
        # Approximate normal CDF
        def norm_cdf(z):
            return 0.5 * (1 + math.erf(z / math.sqrt(2)))
        
        if direction == "OVER":
            # Positive z-score means projection > line, favorable for OVER
            return norm_cdf(z_score)
        else:  # UNDER
            # Negative z-score means projection < line, favorable for UNDER
            return norm_cdf(-z_score)
    
    def _apply_compression(self, confidence: float, z_score: float) -> float:
        """
        SOP v2.1 Rule C1: Compression for extreme values.
        
        If |z_score| > 2.5, cap confidence at 65%
        """
        if abs(z_score) > 2.5:
            return min(confidence, 0.65)
        return confidence
    
    def _calculate_kelly_units(self, edge: float, tier: str) -> float:
        """
        Calculate recommended bet size using 1/4 Kelly.
        
        Capped by tier maximums.
        """
        if edge <= 0:
            return 0.0
        
        # Kelly at -110 odds
        # Kelly = (bp - q) / b where b = 0.909
        b = 0.909
        p = 0.524 + edge  # Our confidence
        q = 1 - p
        
        kelly_full = ((b * p) - q) / b if b > 0 else 0
        kelly_quarter = kelly_full * 0.25
        
        # Tier caps
        tier_caps = {
            "SLAM": 2.0,
            "STRONG": 1.5,
            "LEAN": 1.0,
            "SPEC": 0.5,
            "NO_PLAY": 0.0
        }
        
        max_units = tier_caps.get(tier, 0)
        return min(max(kelly_quarter, 0), max_units)
    
    def _compile_risk_flags(
        self,
        projection: MultiWindowProjection,
        variance: VariancePenaltyResult,
        edge: EdgeGateResult,
        direction: str
    ) -> List[str]:
        """Compile all risk flags"""
        flags = []
        
        # Variance flags
        if variance.is_high_variance:
            flags.append(f"HIGH_VARIANCE (CV={variance.cv:.0%})")
        
        if variance.is_low_sample:
            flags.append(f"LOW_SAMPLE (n={variance.sample_size})")
        
        # Edge flags
        if edge.edge_percent < 5:
            flags.append(f"THIN_EDGE ({edge.edge_percent:.1f}%)")
        
        # Direction flags
        if direction == "OVER":
            flags.append("OVER_BIAS_RISK")
        
        # Compression flag
        if abs(projection.z_score) > 2.5:
            flags.append("CONFIDENCE_COMPRESSED")
        
        return flags


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def format_complete_analysis(result: QuantAnalysisResult) -> str:
    """Format complete analysis as professional report"""
    
    lines = []
    
    # Header
    status = "✅ ACTIONABLE" if result.is_actionable else "⛔ NO PLAY"
    lines.append(f"╔══════════════════════════════════════════════════════════════════╗")
    lines.append(f"║  {result.player_name}")
    lines.append(f"║  {result.stat_type.upper()} {result.direction} {result.line}")
    lines.append(f"║  Status: {status} | Tier: {result.final_tier}")
    lines.append(f"╚══════════════════════════════════════════════════════════════════╝")
    lines.append("")
    
    # Projections
    lines.append("┌─ MULTI-WINDOW PROJECTIONS ──────────────────────────────────────┐")
    for name in ["L3", "L5", "L10", "L20", "season"]:
        w = result.projection.windows.get(name)
        if w and w.is_valid:
            hit_pct = f"{w.hit_rate_vs_line:.0%}" if w.hit_rate_vs_line else "N/A"
            lines.append(
                f"│  {name:6s}: {w.average:5.1f}  (σ={w.std_dev:.1f}, n={w.games_available:2d}, "
                f"hit={hit_pct:>4s}, wt={w.weight_used:.0%})"
            )
        else:
            lines.append(f"│  {name:6s}: INSUFFICIENT DATA")
    lines.append(f"│")
    lines.append(f"│  WEIGHTED PROJECTION: {result.projection.weighted_projection}")
    lines.append(f"│  Z-SCORE vs LINE:     {result.projection.z_score:+.2f}σ")
    lines.append(f"└──────────────────────────────────────────────────────────────────┘")
    lines.append("")
    
    # Confidence breakdown
    lines.append("┌─ CONFIDENCE CALCULATION ────────────────────────────────────────┐")
    lines.append(f"│  Raw (from z-score):  {result.variance.original_confidence:.1%}")
    lines.append(f"│  After variance adj:  {result.variance.adjusted_confidence:.1%}")
    lines.append(f"│  After compression:   {result.final_confidence:.1%}")
    lines.append(f"│")
    lines.append(f"│  Variance Penalty:    {result.variance.total_penalty:.0%}")
    lines.append(f"│    CV = {result.variance.cv:.1%} ({result.variance.cv_category})")
    lines.append(f"│    Sample = {result.variance.sample_size} ({result.variance.sample_category})")
    lines.append(f"└──────────────────────────────────────────────────────────────────┘")
    lines.append("")
    
    # Edge analysis
    lines.append("┌─ EDGE ANALYSIS ─────────────────────────────────────────────────┐")
    lines.append(f"│  Your Confidence:     {result.edge_gate.confidence:.1%}")
    lines.append(f"│  Market Implied:      {result.edge_gate.implied_probability:.1%}")
    lines.append(f"│  ────────────────────────────────")
    lines.append(f"│  EDGE:                {result.edge_gate.edge_percent:+.2f}%")
    lines.append(f"│  Expected Value:      {result.edge_gate.ev_percent:+.2f}%")
    lines.append(f"│")
    gate_status = "✅ PASS" if result.edge_gate.passes_gate else "❌ FAIL"
    lines.append(f"│  3% Gate:             {gate_status}")
    lines.append(f"└──────────────────────────────────────────────────────────────────┘")
    lines.append("")
    
    # Final recommendation
    lines.append("┌─ RECOMMENDATION ────────────────────────────────────────────────┐")
    lines.append(f"│  Tier:                {result.final_tier}")
    lines.append(f"│  Units:               {result.recommended_units}")
    lines.append(f"│  Action:              {result.edge_gate.bet_recommendation}")
    lines.append(f"│")
    if result.risk_flags:
        lines.append(f"│  Risk Flags:")
        for flag in result.risk_flags:
            lines.append(f"│    ⚠️  {flag}")
    else:
        lines.append(f"│  Risk Flags:          None")
    lines.append(f"│")
    lines.append(f"│  Data Sources:        {', '.join(result.data_sources)}")
    lines.append(f"└──────────────────────────────────────────────────────────────────┘")
    
    return "\n".join(lines)


def to_json(result: QuantAnalysisResult) -> Dict:
    """Convert result to JSON-serializable dict"""
    return {
        "player_id": result.player_id,
        "player_name": result.player_name,
        "stat_type": result.stat_type,
        "line": result.line,
        "direction": result.direction,
        
        "projections": {
            "L3": result.projection.windows.get("L3", {}).average if result.projection.windows.get("L3") else None,
            "L5": result.projection.windows.get("L5", {}).average if result.projection.windows.get("L5") else None,
            "L10": result.projection.windows.get("L10", {}).average if result.projection.windows.get("L10") else None,
            "L20": result.projection.windows.get("L20", {}).average if result.projection.windows.get("L20") else None,
            "season": result.projection.windows.get("season", {}).average if result.projection.windows.get("season") else None,
            "weighted": result.projection.weighted_projection
        },
        
        "statistics": {
            "std_dev": result.projection.combined_std_dev,
            "z_score": result.projection.z_score,
            "cv": result.variance.cv,
            "sample_size": result.sample_size
        },
        
        "confidence": {
            "raw": result.variance.original_confidence,
            "after_variance": result.variance.adjusted_confidence,
            "final": result.final_confidence
        },
        
        "edge": {
            "value": result.edge_gate.edge,
            "percent": result.edge_gate.edge_percent,
            "ev_percent": result.edge_gate.ev_percent,
            "passes_gate": result.edge_gate.passes_gate
        },
        
        "recommendation": {
            "tier": result.final_tier,
            "units": result.recommended_units,
            "is_actionable": result.is_actionable,
            "action": result.edge_gate.bet_recommendation
        },
        
        "risk_flags": result.risk_flags,
        "data_sources": result.data_sources
    }


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PROFESSIONAL QUANT ENGINE TEST")
    print("=" * 70)
    
    # Initialize engine
    engine = ProfessionalQuantEngine()
    
    # Test with Amen Thompson
    # Simulated game log (assists, most recent first)
    game_log = [8, 9, 7, 10, 6, 8, 5, 9, 7, 8, 6, 7, 5, 8, 9, 7, 6, 8, 5, 7]
    
    result = engine.analyze_prop(
        player_id="thompson_001",
        player_name="Amen Thompson",
        stat_type="assists",
        game_log=game_log,
        line=5.5,
        direction="OVER",
        data_sources=["nba_api", "espn", "underdog"]
    )
    
    print()
    print(format_complete_analysis(result))
    
    print()
    print("=" * 70)
    print("JSON OUTPUT")
    print("=" * 70)
    print(json.dumps(to_json(result), indent=2))
