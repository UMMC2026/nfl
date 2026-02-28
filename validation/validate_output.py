#!/usr/bin/env python3
"""
FUOOM VALIDATION GATE — SOP v2.1 (TRUTH-ENFORCED)
=================================================
This script MUST run before render_report.py
If ANY check fails → ABORT OUTPUT → No silent failures

HARD CHECKS:
1. No duplicate EDGES (player + game_id + stat + direction)
2. No player appears twice as PRIMARY
3. No correlated line is tiered
4. Tier labels match probabilities

Usage:
    python validation/validate_output.py --input edges.json
    python validation/validate_output.py --input edges.json --strict
    
Exit Codes:
    0 = All validations passed
    1 = Validation failed (DO NOT PROCEED)
    2 = Input file error
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict


class ValidationSeverity(Enum):
    """Validation failure severity levels"""
    CRITICAL = "CRITICAL"  # Blocks output completely
    ERROR = "ERROR"        # Blocks output
    WARNING = "WARNING"    # Logs but allows output (non-strict mode)


@dataclass
class ValidationResult:
    """Single validation check result"""
    check_name: str
    passed: bool
    severity: ValidationSeverity
    message: str
    details: Optional[List[Dict]] = None
    
    def to_dict(self) -> Dict:
        return {
            "check": self.check_name,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details or []
        }


class TierConfig:
    """
    SOP v2.1 Tier Alignment (Rule C2)
    Tier labels MUST match probability ranges exactly
    """
    TIERS = {
        "SLAM": (0.75, 1.00),
        "STRONG": (0.65, 0.7499),
        "LEAN": (0.55, 0.6499),
        "NO_PLAY": (0.00, 0.5499),
        # Legacy support
        "PLAY": (0.55, 1.00),  # Generic play tier
        "SPEC": (0.50, 0.5499),  # Research only
    }
    
    # Sport-specific tier overrides
    SPORT_OVERRIDES = {
        "CBB": {
            "SLAM": None,  # CBB does NOT have SLAM tier
            "STRONG": (0.70, 1.00),
            "LEAN": (0.60, 0.6999),
        },
        "GOLF": {
            "SLAM": None,  # Golf does NOT have SLAM tier
            "STRONG": (0.68, 1.00),
            "LEAN": (0.58, 0.6799),
        }
    }
    
    @classmethod
    def get_tier_bounds(cls, tier: str, sport: str = None) -> Optional[Tuple[float, float]]:
        """Get tier bounds, considering sport overrides"""
        tier_upper = tier.upper().replace(" ", "_")
        
        # Check sport-specific override first
        if sport and sport.upper() in cls.SPORT_OVERRIDES:
            sport_tiers = cls.SPORT_OVERRIDES[sport.upper()]
            if tier_upper in sport_tiers:
                return sport_tiers[tier_upper]
        
        # Fall back to default
        return cls.TIERS.get(tier_upper)
    
    @classmethod
    def get_expected_tier(cls, probability: float, sport: str = None) -> str:
        """Return the correct tier for a given probability"""
        # Sport-specific logic
        if sport and sport.upper() == "CBB":
            if probability >= 0.70:
                return "STRONG"
            elif probability >= 0.60:
                return "LEAN"
            else:
                return "NO_PLAY"
        elif sport and sport.upper() == "GOLF":
            if probability >= 0.68:
                return "STRONG"
            elif probability >= 0.58:
                return "LEAN"
            else:
                return "NO_PLAY"
        
        # Default tiers
        if probability >= 0.75:
            return "SLAM"
        elif probability >= 0.65:
            return "STRONG"
        elif probability >= 0.55:
            return "LEAN"
        else:
            return "NO_PLAY"
    
    @classmethod
    def is_tier_valid(cls, tier: str, probability: float, sport: str = None) -> bool:
        """Check if tier matches probability per SOP v2.1 Rule C2"""
        tier_upper = tier.upper().replace(" ", "_")
        
        # Get bounds for this tier (with sport override)
        bounds = cls.get_tier_bounds(tier_upper, sport)
        
        if bounds is None:
            # Tier not allowed for this sport
            return False
        
        min_prob, max_prob = bounds
        return min_prob <= probability <= max_prob


class EdgeValidator:
    """
    FUOOM Edge Validation Engine
    Implements SOP v2.1 Section 6: RENDER GATE (FAIL-FAST RULE)
    """
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.results: List[ValidationResult] = []
        self.edges: List[Dict] = []
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.sport = None  # Will be detected from edges
        
    def load_edges(self, filepath: str) -> bool:
        """Load edges from JSON file"""
        try:
            path = Path(filepath)
            if not path.exists():
                self.results.append(ValidationResult(
                    check_name="FILE_LOAD",
                    passed=False,
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Input file not found: {filepath}"
                ))
                return False
                
            with open(path, 'r') as f:
                data = json.load(f)
            
            # Handle both array and object with 'edges' key
            if isinstance(data, list):
                self.edges = data
            elif isinstance(data, dict) and 'edges' in data:
                self.edges = data['edges']
            elif isinstance(data, dict) and 'picks' in data:
                self.edges = data['picks']
            elif isinstance(data, dict) and 'signals' in data:
                self.edges = data['signals']
            else:
                self.results.append(ValidationResult(
                    check_name="FILE_LOAD",
                    passed=False,
                    severity=ValidationSeverity.CRITICAL,
                    message="Invalid file structure: expected array or object with 'edges'/'picks'/'signals' key"
                ))
                return False
            
            # Detect sport from edges
            if self.edges:
                sports = set(e.get('sport', '').upper() for e in self.edges if e.get('sport'))
                if len(sports) == 1:
                    self.sport = sports.pop()
                elif len(sports) > 1:
                    self.sport = "MIXED"
            
            self.results.append(ValidationResult(
                check_name="FILE_LOAD",
                passed=True,
                severity=ValidationSeverity.CRITICAL,
                message=f"Loaded {len(self.edges)} edges from {filepath} (sport: {self.sport or 'unknown'})"
            ))
            return True
            
        except json.JSONDecodeError as e:
            self.results.append(ValidationResult(
                check_name="FILE_LOAD",
                passed=False,
                severity=ValidationSeverity.CRITICAL,
                message=f"JSON parse error: {str(e)}"
            ))
            return False
        except Exception as e:
            self.results.append(ValidationResult(
                check_name="FILE_LOAD",
                passed=False,
                severity=ValidationSeverity.CRITICAL,
                message=f"Unexpected error: {str(e)}"
            ))
            return False
    
    def check_1_no_duplicate_edges(self) -> ValidationResult:
        """
        CHECK 1: No duplicate EDGES
        
        SOP v2.1 Rule A1: EDGE = unique(player, game_id, stat, direction)
        Each edge must be unique. Duplicates indicate pipeline failure.
        """
        edge_keys = []
        duplicates = []
        
        for i, edge in enumerate(self.edges):
            # Build canonical edge key
            player = edge.get('player', edge.get('player_name', edge.get('entity', ''))).lower().strip()
            game_id = str(edge.get('game_id', edge.get('match_id', edge.get('event_id', '')))).lower()
            stat = edge.get('stat', edge.get('stat_type', edge.get('market', ''))).lower().strip()
            direction = edge.get('direction', edge.get('pick', '')).lower().strip()
            
            # Normalize direction
            if direction in ['over', 'higher', 'more', 'o']:
                direction = 'over'
            elif direction in ['under', 'lower', 'less', 'u']:
                direction = 'under'
            
            edge_key = f"{player}|{game_id}|{stat}|{direction}"
            
            if edge_key in edge_keys:
                duplicates.append({
                    "index": i,
                    "edge_key": edge_key,
                    "player": edge.get('player', edge.get('player_name', edge.get('entity', ''))),
                    "stat": edge.get('stat', edge.get('stat_type', edge.get('market', ''))),
                    "direction": direction
                })
            else:
                edge_keys.append(edge_key)
        
        passed = len(duplicates) == 0
        return ValidationResult(
            check_name="NO_DUPLICATE_EDGES",
            passed=passed,
            severity=ValidationSeverity.CRITICAL,
            message=f"Found {len(duplicates)} duplicate edges" if not passed else "No duplicate edges",
            details=duplicates if duplicates else None
        )
    
    def check_2_no_duplicate_primary_players(self) -> ValidationResult:
        """
        CHECK 2: No player appears twice as PRIMARY
        
        SOP v2.1 Rule B1: Max 1 PRIMARY bet per player per game
        Prevents correlation blowup from same-player multi-bets.
        """
        # Track primary bets per player per game
        player_game_primaries: Dict[str, List[Dict]] = defaultdict(list)
        violations = []
        
        for i, edge in enumerate(self.edges):
            # Skip non-primary bets
            is_primary = edge.get('is_primary', True)  # Default to primary if not specified
            risk_tag = edge.get('risk_tag', '').upper()
            pick_state = edge.get('pick_state', '').upper()
            
            # Skip if explicitly marked as correlated or not optimizable
            if not is_primary or risk_tag == 'CORRELATED':
                continue
            if pick_state in ['REJECTED', 'VETTED']:
                continue
            
            # Build player-game key
            player = edge.get('player', edge.get('player_name', edge.get('entity', ''))).lower().strip()
            game_id = str(edge.get('game_id', edge.get('match_id', edge.get('event_id', '')))).lower()
            
            key = f"{player}|{game_id}"
            
            player_game_primaries[key].append({
                "index": i,
                "player": edge.get('player', edge.get('player_name', edge.get('entity', ''))),
                "game_id": game_id,
                "stat": edge.get('stat', edge.get('stat_type', edge.get('market', ''))),
                "line": edge.get('line', edge.get('value', '')),
                "direction": edge.get('direction', edge.get('pick', ''))
            })
        
        # Find violations (players with multiple primaries)
        for key, entries in player_game_primaries.items():
            if len(entries) > 1:
                violations.append({
                    "player_game_key": key,
                    "count": len(entries),
                    "bets": entries
                })
        
        passed = len(violations) == 0
        return ValidationResult(
            check_name="NO_DUPLICATE_PRIMARY_PLAYERS",
            passed=passed,
            severity=ValidationSeverity.CRITICAL,
            message=f"Found {len(violations)} players with multiple PRIMARY bets" if not passed else "No duplicate primary players",
            details=violations if violations else None
        )
    
    def check_3_no_correlated_in_tiers(self) -> ValidationResult:
        """
        CHECK 3: No correlated line is tiered
        
        SOP v2.1 Rule B2: Correlated alternatives are excluded from tiers
        They must be visually separated and excluded from parlays.
        """
        violations = []
        
        for i, edge in enumerate(self.edges):
            risk_tag = edge.get('risk_tag', '').upper()
            is_primary = edge.get('is_primary', True)
            tier = edge.get('tier', edge.get('confidence_tier', '')).upper()
            
            # Check if correlated but has a tier
            is_correlated = risk_tag == 'CORRELATED' or is_primary == False
            has_tier = tier in ['SLAM', 'STRONG', 'LEAN', 'PLAY']
            
            if is_correlated and has_tier:
                violations.append({
                    "index": i,
                    "player": edge.get('player', edge.get('player_name', edge.get('entity', ''))),
                    "stat": edge.get('stat', edge.get('stat_type', edge.get('market', ''))),
                    "tier": tier,
                    "risk_tag": risk_tag,
                    "is_primary": is_primary
                })
        
        passed = len(violations) == 0
        return ValidationResult(
            check_name="NO_CORRELATED_IN_TIERS",
            passed=passed,
            severity=ValidationSeverity.ERROR,
            message=f"Found {len(violations)} correlated lines with tier assignments" if not passed else "No correlated lines in tiers",
            details=violations if violations else None
        )
    
    def check_4_tier_probability_alignment(self) -> ValidationResult:
        """
        CHECK 4: Tier labels match probabilities
        
        SOP v2.1 Rule C2: 
        - SLAM ≥ 75%
        - STRONG 65-74%
        - LEAN 55-64%
        - NO_PLAY < 55%
        
        Note: CBB and Golf do NOT have SLAM tier
        """
        violations = []
        
        for i, edge in enumerate(self.edges):
            tier = edge.get('tier', edge.get('confidence_tier', '')).upper()
            probability = edge.get('probability', edge.get('win_probability', edge.get('confidence', 0)))
            edge_sport = edge.get('sport', self.sport or '').upper()
            
            # Skip edges without tier or probability
            if not tier or probability == 0:
                continue
            
            # Skip non-tiered markers
            if tier in ['NO_PLAY', 'REJECTED', 'VETTED', 'N/A', '']:
                continue
            
            # Normalize probability (handle both 0-1 and 0-100 scales)
            if probability > 1:
                probability = probability / 100
            
            expected_tier = TierConfig.get_expected_tier(probability, edge_sport)
            
            if not TierConfig.is_tier_valid(tier, probability, edge_sport):
                violations.append({
                    "index": i,
                    "player": edge.get('player', edge.get('player_name', edge.get('entity', ''))),
                    "stat": edge.get('stat', edge.get('stat_type', edge.get('market', ''))),
                    "sport": edge_sport,
                    "assigned_tier": tier,
                    "expected_tier": expected_tier,
                    "probability": round(probability, 4),
                    "probability_pct": f"{probability * 100:.1f}%"
                })
        
        passed = len(violations) == 0
        return ValidationResult(
            check_name="TIER_PROBABILITY_ALIGNMENT",
            passed=passed,
            severity=ValidationSeverity.CRITICAL,
            message=f"Found {len(violations)} tier-probability mismatches" if not passed else "All tiers align with probabilities",
            details=violations if violations else None
        )
    
    def check_5_required_fields(self) -> ValidationResult:
        """
        CHECK 5: All required fields present
        
        Every edge must have: player/entity, stat/market, line, direction, probability
        """
        violations = []
        
        required_fields = [
            ('player', 'player_name', 'entity'),  # At least one of these
            ('stat', 'stat_type', 'market'),
            ('line', 'value'),
            ('direction', 'pick'),
            ('probability', 'win_probability', 'confidence'),
        ]
        
        for i, edge in enumerate(self.edges):
            missing = []
            for field_group in required_fields:
                if not any(edge.get(f) for f in field_group):
                    missing.append(field_group[0])
            
            if missing:
                violations.append({
                    "index": i,
                    "edge_id": edge.get('edge_id', f'edge_{i}'),
                    "missing_fields": missing
                })
        
        passed = len(violations) == 0
        return ValidationResult(
            check_name="REQUIRED_FIELDS",
            passed=passed,
            severity=ValidationSeverity.ERROR,
            message=f"Found {len(violations)} edges with missing required fields" if not passed else "All required fields present",
            details=violations if violations else None
        )
    
    def check_6_pick_state_valid(self) -> ValidationResult:
        """
        CHECK 6: Pick states are valid
        
        Valid states: OPTIMIZABLE, VETTED, REJECTED
        Only OPTIMIZABLE should be in output for betting
        """
        violations = []
        valid_states = {'OPTIMIZABLE', 'VETTED', 'REJECTED', ''}
        
        for i, edge in enumerate(self.edges):
            pick_state = edge.get('pick_state', '').upper()
            tier = edge.get('tier', edge.get('confidence_tier', '')).upper()
            
            # Check for invalid state
            if pick_state and pick_state not in valid_states:
                violations.append({
                    "index": i,
                    "player": edge.get('player', edge.get('player_name', '')),
                    "pick_state": pick_state,
                    "issue": "Invalid pick state"
                })
            
            # Check for REJECTED edges that are tiered
            if pick_state == 'REJECTED' and tier in ['SLAM', 'STRONG', 'LEAN']:
                violations.append({
                    "index": i,
                    "player": edge.get('player', edge.get('player_name', '')),
                    "pick_state": pick_state,
                    "tier": tier,
                    "issue": "REJECTED edge should not have tier"
                })
        
        passed = len(violations) == 0
        return ValidationResult(
            check_name="PICK_STATE_VALID",
            passed=passed,
            severity=ValidationSeverity.WARNING,
            message=f"Found {len(violations)} pick state issues" if not passed else "All pick states valid",
            details=violations if violations else None
        )
    
    def run_all_checks(self) -> Tuple[bool, List[ValidationResult]]:
        """
        Execute all validation checks
        Returns (all_passed, results)
        """
        # Run all checks
        self.results.append(self.check_1_no_duplicate_edges())
        self.results.append(self.check_2_no_duplicate_primary_players())
        self.results.append(self.check_3_no_correlated_in_tiers())
        self.results.append(self.check_4_tier_probability_alignment())
        self.results.append(self.check_5_required_fields())
        self.results.append(self.check_6_pick_state_valid())
        
        # Determine overall pass/fail
        if self.strict_mode:
            # Strict: any non-pass fails (except warnings)
            all_passed = all(
                r.passed for r in self.results 
                if r.severity != ValidationSeverity.WARNING
            )
        else:
            # Non-strict: only CRITICAL failures block
            all_passed = all(
                r.passed for r in self.results 
                if r.severity == ValidationSeverity.CRITICAL
            )
        
        return all_passed, self.results
    
    def generate_report(self, all_passed: bool) -> Dict:
        """Generate validation report"""
        return {
            "validation_run": {
                "timestamp": self.timestamp,
                "strict_mode": self.strict_mode,
                "total_edges": len(self.edges),
                "detected_sport": self.sport,
                "overall_status": "PASSED" if all_passed else "FAILED"
            },
            "checks": [r.to_dict() for r in self.results],
            "summary": {
                "passed": sum(1 for r in self.results if r.passed),
                "failed": sum(1 for r in self.results if not r.passed),
                "critical_failures": sum(
                    1 for r in self.results 
                    if not r.passed and r.severity == ValidationSeverity.CRITICAL
                )
            },
            "sop_version": "2.1",
            "gate": "RENDER_GATE"
        }


def print_report(report: Dict, verbose: bool = False):
    """Print human-readable validation report"""
    status = report['validation_run']['overall_status']
    
    print("\n" + "=" * 60)
    print(f"  FUOOM VALIDATION GATE — SOP v2.1")
    print("=" * 60)
    print(f"  Timestamp: {report['validation_run']['timestamp']}")
    print(f"  Edges Checked: {report['validation_run']['total_edges']}")
    print(f"  Sport: {report['validation_run']['detected_sport'] or 'Unknown'}")
    print(f"  Mode: {'STRICT' if report['validation_run']['strict_mode'] else 'STANDARD'}")
    print("-" * 60)
    
    for check in report['checks']:
        status_icon = "✓" if check['passed'] else "✗"
        severity_tag = f"[{check['severity']}]" if not check['passed'] else ""
        print(f"  {status_icon} {check['check']}: {check['message']} {severity_tag}")
        
        if verbose and check['details']:
            for detail in check['details'][:5]:  # Show first 5
                print(f"      → {detail}")
            if len(check['details']) > 5:
                print(f"      ... and {len(check['details']) - 5} more")
    
    print("-" * 60)
    
    if report['validation_run']['overall_status'] == "PASSED":
        print("  ✓ ALL CHECKS PASSED — Safe to proceed with render")
    else:
        print("  ✗ VALIDATION FAILED — DO NOT PROCEED")
        print("  Fix the issues above before rendering output")
    
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="FUOOM Validation Gate — SOP v2.1 (Truth-Enforced)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0 = All validations passed
  1 = Validation failed (DO NOT PROCEED)
  2 = Input file error

Examples:
  python validation/validate_output.py --input edges.json
  python validation/validate_output.py --input edges.json --strict --verbose
  python validation/validate_output.py --input picks.json --output validation_report.json
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Path to edges JSON file'
    )
    parser.add_argument(
        '--output', '-o',
        help='Path to save validation report JSON (optional)'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        default=True,
        help='Strict mode: any failure blocks output (default: True)'
    )
    parser.add_argument(
        '--no-strict',
        action='store_true',
        help='Non-strict mode: only CRITICAL failures block output'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed violation information'
    )
    parser.add_argument(
        '--json-only',
        action='store_true',
        help='Output JSON report only (no human-readable output)'
    )
    
    args = parser.parse_args()
    
    # Handle strict mode flags
    strict_mode = True
    if args.no_strict:
        strict_mode = False
    
    # Initialize validator
    validator = EdgeValidator(strict_mode=strict_mode)
    
    # Load edges
    if not validator.load_edges(args.input):
        print_report(validator.generate_report(False), verbose=args.verbose)
        sys.exit(2)
    
    # Run all checks
    all_passed, results = validator.run_all_checks()
    
    # Generate report
    report = validator.generate_report(all_passed)
    
    # Output report
    if args.json_only:
        print(json.dumps(report, indent=2))
    else:
        print_report(report, verbose=args.verbose)
    
    # Save report if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, indent=2, fp=f)
        if not args.json_only:
            print(f"Report saved to: {args.output}")
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
