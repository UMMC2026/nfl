#!/usr/bin/env python3
"""
VALIDATE_OUTPUT.PY — SOP v2.1 HARD GATE
=======================================
This module MUST run before render_report.py
Any failure ABORTS output. No silent failures. No partial reports.

Version: 2.1.0
Status: TRUTH-ENFORCED
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib


# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIDENCE_TIERS = {
    "SLAM": (0.75, 1.00),
    "STRONG": (0.65, 0.749),
    "LEAN": (0.55, 0.649),
    "NO_PLAY": (0.00, 0.549)
}

# Maximum std_dev multiplier before confidence compression kicks in
COMPRESSION_THRESHOLD = 2.5
COMPRESSED_MAX_CONFIDENCE = 0.65


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Edge:
    """Represents a unique betting edge (player + game + direction)"""
    player_id: str
    player_name: str
    game_id: str
    stat_type: str
    direction: str  # "OVER" or "UNDER"
    projection: float
    std_dev: float
    confidence: float
    tier: str
    primary_line: float
    correlated_lines: List[float] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    
    @property
    def edge_key(self) -> str:
        """Unique identifier for this edge"""
        return f"{self.player_id}|{self.game_id}|{self.stat_type}|{self.direction}"
    
    @property
    def player_game_key(self) -> str:
        """Key for checking one player per game rule"""
        return f"{self.player_id}|{self.game_id}|{self.stat_type}"


@dataclass
class ValidationResult:
    """Result of a single validation check"""
    check_name: str
    passed: bool
    message: str
    severity: str  # "ERROR" or "WARNING"
    details: Optional[Dict] = None


@dataclass 
class ValidationReport:
    """Complete validation report"""
    timestamp: str
    input_file: str
    total_edges: int
    checks_run: int
    checks_passed: int
    checks_failed: int
    errors: List[ValidationResult] = field(default_factory=list)
    warnings: List[ValidationResult] = field(default_factory=list)
    
    @property
    def passed(self) -> bool:
        return self.checks_failed == 0


# ============================================================================
# VALIDATION CHECKS
# ============================================================================

class SOPValidator:
    """
    SOP v2.1 Truth-Enforced Validator
    
    HARD CONSTRAINTS:
    ✔ No duplicate EDGES
    ✔ No player appears twice as PRIMARY
    ✔ No correlated line is tiered
    ✔ Tier labels match probabilities
    ✔ Confidence compression applied where required
    """
    
    def __init__(self, edges: List[Edge]):
        self.edges = edges
        self.results: List[ValidationResult] = []
        
    def validate_all(self) -> ValidationReport:
        """Run all validation checks. Returns report."""
        
        # Core SOP v2.1 checks
        self._check_no_duplicate_edges()
        self._check_one_player_per_game()
        self._check_correlated_not_tiered()
        self._check_tier_probability_alignment()
        self._check_confidence_compression()
        self._check_data_source_requirements()
        self._check_edge_definition_completeness()
        
        # Build report
        errors = [r for r in self.results if r.severity == "ERROR"]
        warnings = [r for r in self.results if r.severity == "WARNING"]
        
        return ValidationReport(
            timestamp=datetime.utcnow().isoformat() + "Z",
            input_file="edges.json",
            total_edges=len(self.edges),
            checks_run=len(self.results),
            checks_passed=sum(1 for r in self.results if r.passed),
            checks_failed=sum(1 for r in self.results if not r.passed and r.severity == "ERROR"),
            errors=errors,
            warnings=warnings
        )
    
    def _check_no_duplicate_edges(self):
        """Rule A2: Each edge must be unique"""
        seen = {}
        duplicates = []
        
        for edge in self.edges:
            key = edge.edge_key
            if key in seen:
                duplicates.append({
                    "edge_key": key,
                    "player": edge.player_name,
                    "first_occurrence": seen[key],
                    "duplicate_line": edge.primary_line
                })
            else:
                seen[key] = edge.primary_line
        
        self.results.append(ValidationResult(
            check_name="NO_DUPLICATE_EDGES",
            passed=len(duplicates) == 0,
            message=f"Found {len(duplicates)} duplicate edges" if duplicates else "No duplicate edges",
            severity="ERROR" if duplicates else "INFO",
            details={"duplicates": duplicates} if duplicates else None
        ))
    
    def _check_one_player_per_game(self):
        """Rule B1: Max 1 PRIMARY bet per player per game per stat type"""
        player_game_counts = defaultdict(list)
        
        for edge in self.edges:
            if edge.tier != "CORRELATED_ALTERNATIVE":
                player_game_counts[edge.player_game_key].append({
                    "direction": edge.direction,
                    "line": edge.primary_line,
                    "tier": edge.tier
                })
        
        violations = {k: v for k, v in player_game_counts.items() if len(v) > 1}
        
        self.results.append(ValidationResult(
            check_name="ONE_PLAYER_PER_GAME",
            passed=len(violations) == 0,
            message=f"Found {len(violations)} players with multiple PRIMARY bets" if violations else "One player per game rule satisfied",
            severity="ERROR" if violations else "INFO",
            details={"violations": violations} if violations else None
        ))
    
    def _check_correlated_not_tiered(self):
        """Rule B2: Correlated alternatives must not be tiered"""
        violations = []
        
        for edge in self.edges:
            if edge.correlated_lines and edge.tier in ["SLAM", "STRONG", "LEAN"]:
                violations.append({
                    "player": edge.player_name,
                    "edge_key": edge.edge_key,
                    "tier": edge.tier,
                    "should_be": "CORRELATED_ALTERNATIVE"
                })
        
        self.results.append(ValidationResult(
            check_name="CORRELATED_NOT_TIERED",
            passed=len(violations) == 0,
            message=f"Found {len(violations)} correlated lines incorrectly tiered" if violations else "Correlated handling correct",
            severity="ERROR" if violations else "INFO",
            details={"violations": violations} if violations else None
        ))
    
    def _check_tier_probability_alignment(self):
        """Rule C2: Tier labels must match probability ranges"""
        violations = []
        
        for edge in self.edges:
            if edge.tier == "CORRELATED_ALTERNATIVE":
                continue
                
            expected_tier = self._get_expected_tier(edge.confidence)
            if edge.tier != expected_tier:
                violations.append({
                    "player": edge.player_name,
                    "confidence": edge.confidence,
                    "assigned_tier": edge.tier,
                    "expected_tier": expected_tier
                })
        
        self.results.append(ValidationResult(
            check_name="TIER_PROBABILITY_ALIGNMENT",
            passed=len(violations) == 0,
            message=f"Found {len(violations)} tier/probability mismatches" if violations else "All tiers match probabilities",
            severity="ERROR" if violations else "INFO",
            details={"violations": violations} if violations else None
        ))
    
    def _check_confidence_compression(self):
        """Rule C1: Apply compression when projection far from line"""
        violations = []
        
        for edge in self.edges:
            if edge.std_dev > 0:
                distance = abs(edge.projection - edge.primary_line)
                if distance > COMPRESSION_THRESHOLD * edge.std_dev:
                    if edge.confidence > COMPRESSED_MAX_CONFIDENCE:
                        violations.append({
                            "player": edge.player_name,
                            "projection": edge.projection,
                            "line": edge.primary_line,
                            "std_dev": edge.std_dev,
                            "distance_in_std": round(distance / edge.std_dev, 2),
                            "confidence": edge.confidence,
                            "max_allowed": COMPRESSED_MAX_CONFIDENCE
                        })
        
        self.results.append(ValidationResult(
            check_name="CONFIDENCE_COMPRESSION",
            passed=len(violations) == 0,
            message=f"Found {len(violations)} edges needing confidence compression" if violations else "Confidence compression rules satisfied",
            severity="ERROR" if violations else "INFO",
            details={"violations": violations} if violations else None
        ))
    
    def _check_data_source_requirements(self):
        """Rule 2.2: Minimum 2 data sources for verification"""
        violations = []
        
        for edge in self.edges:
            if len(edge.data_sources) < 2:
                violations.append({
                    "player": edge.player_name,
                    "edge_key": edge.edge_key,
                    "sources": edge.data_sources,
                    "required": 2
                })
        
        self.results.append(ValidationResult(
            check_name="DATA_SOURCE_VERIFICATION",
            passed=len(violations) == 0,
            message=f"Found {len(violations)} edges with insufficient data sources" if violations else "All edges have verified sources",
            severity="ERROR" if violations else "INFO",
            details={"violations": violations} if violations else None
        ))
    
    def _check_edge_definition_completeness(self):
        """Rule 10: Every edge must be fully explainable"""
        violations = []
        
        required_fields = ['player_id', 'game_id', 'stat_type', 'direction', 
                          'projection', 'confidence', 'primary_line']
        
        for edge in self.edges:
            missing = []
            for field in required_fields:
                value = getattr(edge, field, None)
                if value is None or value == "":
                    missing.append(field)
            
            if missing:
                violations.append({
                    "player": edge.player_name,
                    "edge_key": edge.edge_key,
                    "missing_fields": missing
                })
        
        self.results.append(ValidationResult(
            check_name="EDGE_COMPLETENESS",
            passed=len(violations) == 0,
            message=f"Found {len(violations)} incomplete edge definitions" if violations else "All edges fully defined",
            severity="ERROR" if violations else "INFO",
            details={"violations": violations} if violations else None
        ))
    
    def _get_expected_tier(self, confidence: float) -> str:
        """Determine correct tier based on probability"""
        for tier, (low, high) in CONFIDENCE_TIERS.items():
            if low <= confidence <= high:
                return tier
        return "NO_PLAY"


# ============================================================================
# EDGE COLLAPSE UTILITY
# ============================================================================

def collapse_edges(raw_lines: List[Dict]) -> List[Edge]:
    """
    Rule A2: Collapse multiple lines for same edge into single PRIMARY
    
    OVER  → highest reasonable line becomes PRIMARY
    UNDER → lowest reasonable line becomes PRIMARY
    """
    edge_groups = defaultdict(list)
    
    for line in raw_lines:
        key = f"{line['player_id']}|{line['game_id']}|{line['stat_type']}|{line['direction']}"
        edge_groups[key].append(line)
    
    collapsed = []
    for key, lines in edge_groups.items():
        direction = lines[0]['direction']
        
        # Sort by line value
        sorted_lines = sorted(lines, key=lambda x: x['line'])
        
        # Select PRIMARY based on direction
        if direction == "OVER":
            primary = sorted_lines[-1]  # Highest line
            correlated = [l['line'] for l in sorted_lines[:-1]]
        else:  # UNDER
            primary = sorted_lines[0]   # Lowest line
            correlated = [l['line'] for l in sorted_lines[1:]]
        
        edge = Edge(
            player_id=primary['player_id'],
            player_name=primary['player_name'],
            game_id=primary['game_id'],
            stat_type=primary['stat_type'],
            direction=direction,
            projection=primary['projection'],
            std_dev=primary.get('std_dev', 0),
            confidence=primary['confidence'],
            tier=primary['tier'],
            primary_line=primary['line'],
            correlated_lines=correlated,
            data_sources=primary.get('data_sources', [])
        )
        collapsed.append(edge)
    
    return collapsed


# ============================================================================
# FILE I/O
# ============================================================================

def load_edges(filepath: str) -> List[Edge]:
    """Load edges from JSON file"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    edges = []
    for item in data.get('edges', data):
        edge = Edge(
            player_id=item['player_id'],
            player_name=item['player_name'],
            game_id=item['game_id'],
            stat_type=item['stat_type'],
            direction=item['direction'],
            projection=item['projection'],
            std_dev=item.get('std_dev', 0),
            confidence=item['confidence'],
            tier=item['tier'],
            primary_line=item['primary_line'],
            correlated_lines=item.get('correlated_lines', []),
            data_sources=item.get('data_sources', [])
        )
        edges.append(edge)
    
    return edges


def save_report(report: ValidationReport, filepath: str):
    """Save validation report to JSON"""
    output = {
        "timestamp": report.timestamp,
        "input_file": report.input_file,
        "summary": {
            "total_edges": report.total_edges,
            "checks_run": report.checks_run,
            "checks_passed": report.checks_passed,
            "checks_failed": report.checks_failed,
            "status": "PASSED" if report.passed else "FAILED"
        },
        "errors": [
            {
                "check": r.check_name,
                "message": r.message,
                "details": r.details
            }
            for r in report.errors
        ],
        "warnings": [
            {
                "check": r.check_name,
                "message": r.message,
                "details": r.details
            }
            for r in report.warnings
        ]
    }
    
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """
    HARD GATE EXECUTION
    
    Usage: python validate_output.py [edges_file] [output_report]
    
    Exit codes:
        0 = All checks passed, safe to render
        1 = Validation failed, ABORT OUTPUT
    """
    print("=" * 60)
    print("SOP v2.1 VALIDATION GATE — TRUTH-ENFORCED")
    print("=" * 60)
    
    # Paths
    edges_file = sys.argv[1] if len(sys.argv) > 1 else "outputs/edges.json"
    report_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/validation_report.json"
    
    # Check input exists
    if not Path(edges_file).exists():
        print(f"\n❌ ERROR: Input file not found: {edges_file}")
        print("   Run score_edges.py first.")
        sys.exit(1)
    
    # Load and validate
    print(f"\n📂 Loading edges from: {edges_file}")
    edges = load_edges(edges_file)
    print(f"   Found {len(edges)} edges")
    
    print("\n🔍 Running validation checks...")
    validator = SOPValidator(edges)
    report = validator.validate_all()
    
    # Save report
    Path(report_file).parent.mkdir(parents=True, exist_ok=True)
    save_report(report, report_file)
    print(f"\n📄 Report saved to: {report_file}")
    
    # Print results
    print("\n" + "=" * 60)
    if report.passed:
        print("✅ VALIDATION PASSED")
        print("   All SOP v2.1 constraints satisfied.")
        print("   Safe to proceed to render_report.py")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ VALIDATION FAILED — OUTPUT ABORTED")
        print(f"   {report.checks_failed} critical errors detected")
        print("\nErrors:")
        for error in report.errors:
            print(f"   • {error.check_name}: {error.message}")
            if error.details:
                for k, v in error.details.items():
                    if isinstance(v, list) and v:
                        print(f"     {k}:")
                        for item in v[:3]:  # Show first 3
                            print(f"       - {item}")
                        if len(v) > 3:
                            print(f"       ... and {len(v) - 3} more")
        print("\n" + "=" * 60)
        print("FIX ERRORS BEFORE RENDERING")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
