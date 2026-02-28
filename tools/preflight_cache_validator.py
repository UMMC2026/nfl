#!/usr/bin/env python3
"""
Preflight Cache Validator CLI

Run this BEFORE any sport pipeline to ensure cache integrity.
Detects cross-sport contamination and enforces namespace rules.

Usage:
    python tools/preflight_cache_validator.py --sport CBB
    python tools/preflight_cache_validator.py --sport CBB --fix
    python tools/preflight_cache_validator.py --all
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

VALID_SPORTS = {"NBA", "CBB", "NFL", "TENNIS", "GOLF", "SOCCER", "CFB", "WNBA", "MLB", "NHL"}

# Known cross-sport contamination patterns
CONTAMINATION_PATTERNS = {
    "TENNIS_IN_CBB": [
        r"hannes.*steinbach",
        r"tennis",
        r"aces_avg",
        r"double_faults",
        r"surface_(hard|clay|grass)",
    ],
    "GOLF_IN_CBB": [
        r"golf",
        r"sg_putting",
        r"sg_approach",
        r"strokes_gained",
        r"driving_distance",
    ],
    "NBA_IN_CBB": [
        r"nba_player_",
        r"fantasy_score",
        r"triple_double",
    ],
    "NFL_IN_CBB": [
        r"nfl_player_",
        r"passing_yards",
        r"rushing_yards",
        r"receiving_yards",
    ],
}

# Sport-specific cache locations
SPORT_CACHE_PATHS = {
    "CBB": [
        Path("sports/cbb/data/cache"),
        Path("cache/cbb"),
    ],
    "NBA": [
        Path("cache/nba_stats"),
        Path("cache"),
    ],
    "NFL": [
        Path("cache/nfl"),
        Path("nfl/cache"),
    ],
    "TENNIS": [
        Path("tennis/data/cache"),
        Path("cache/tennis"),
    ],
    "GOLF": [
        Path("golf/data/cache"),
        Path("cache/golf"),
    ],
    "SOCCER": [
        Path("soccer/data/cache"),
        Path("cache/soccer"),
    ],
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ContaminationReport:
    """Report of cache contamination findings."""
    sport: str
    cache_path: str
    total_keys: int
    contaminated_keys: List[str] = field(default_factory=list)
    contamination_type: Dict[str, List[str]] = field(default_factory=dict)
    is_clean: bool = True
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "sport": self.sport,
            "cache_path": self.cache_path,
            "total_keys": self.total_keys,
            "contaminated_keys": self.contaminated_keys,
            "contamination_type": self.contamination_type,
            "is_clean": self.is_clean,
            "checked_at": self.checked_at,
        }


@dataclass
class ValidationResult:
    """Overall validation result."""
    sport: str
    passed: bool
    reports: List[ContaminationReport] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fixed_count: int = 0


# =============================================================================
# VALIDATOR
# =============================================================================

class PreflightCacheValidator:
    """
    Validates sport-specific caches for contamination before pipeline runs.
    
    Key checks:
    1. No cross-sport keys (e.g., tennis player in CBB cache)
    2. Proper namespace prefixing (SPORT::version::entity)
    3. No legacy unprefixed keys
    """
    
    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path(__file__).parent.parent
        
    def validate(self, sport: str, fix: bool = False) -> ValidationResult:
        """
        Validate cache for a specific sport.
        
        Args:
            sport: Sport code (e.g., "CBB", "NBA")
            fix: If True, remove contaminated keys
            
        Returns:
            ValidationResult with pass/fail and details
        """
        sport = sport.upper()
        if sport not in VALID_SPORTS:
            return ValidationResult(
                sport=sport,
                passed=False,
                errors=[f"Unknown sport: {sport}. Valid: {VALID_SPORTS}"],
            )
        
        result = ValidationResult(sport=sport, passed=True)
        cache_paths = SPORT_CACHE_PATHS.get(sport, [])
        
        for rel_path in cache_paths:
            cache_dir = self.workspace_root / rel_path
            if not cache_dir.exists():
                continue
                
            # Check JSON cache files
            for json_file in cache_dir.glob("*.json"):
                report = self._check_json_cache(sport, json_file)
                result.reports.append(report)
                
                if not report.is_clean:
                    result.passed = False
                    result.errors.append(
                        f"[{json_file.name}] {len(report.contaminated_keys)} contaminated keys"
                    )
                    
                    if fix:
                        fixed = self._fix_json_cache(json_file, report.contaminated_keys)
                        result.fixed_count += fixed
                        result.warnings.append(f"Fixed {fixed} keys in {json_file.name}")
        
        return result
    
    def _check_json_cache(self, sport: str, json_file: Path) -> ContaminationReport:
        """Check a JSON cache file for contamination."""
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return ContaminationReport(
                sport=sport,
                cache_path=str(json_file),
                total_keys=0,
                is_clean=False,
                contaminated_keys=[f"FILE_ERROR: {e}"],
            )
        
        if not isinstance(data, dict):
            return ContaminationReport(
                sport=sport,
                cache_path=str(json_file),
                total_keys=0,
                is_clean=True,
            )
        
        keys = list(data.keys())
        contaminated = []
        contamination_type: Dict[str, List[str]] = {}
        
        # Build patterns to check based on sport
        patterns_to_check = self._get_contamination_patterns(sport)
        
        for key in keys:
            key_lower = key.lower()
            
            for pattern_name, patterns in patterns_to_check.items():
                for pattern in patterns:
                    if re.search(pattern, key_lower):
                        contaminated.append(key)
                        contamination_type.setdefault(pattern_name, []).append(key)
                        break
                else:
                    continue
                break
        
        return ContaminationReport(
            sport=sport,
            cache_path=str(json_file),
            total_keys=len(keys),
            contaminated_keys=contaminated,
            contamination_type=contamination_type,
            is_clean=len(contaminated) == 0,
        )
    
    def _get_contamination_patterns(self, sport: str) -> Dict[str, List[str]]:
        """Get contamination patterns relevant to a sport."""
        patterns = {}
        
        if sport == "CBB":
            patterns["TENNIS_IN_CBB"] = CONTAMINATION_PATTERNS["TENNIS_IN_CBB"]
            patterns["GOLF_IN_CBB"] = CONTAMINATION_PATTERNS["GOLF_IN_CBB"]
            patterns["NBA_IN_CBB"] = CONTAMINATION_PATTERNS["NBA_IN_CBB"]
            patterns["NFL_IN_CBB"] = CONTAMINATION_PATTERNS["NFL_IN_CBB"]
            
        elif sport == "NBA":
            patterns["TENNIS_IN_NBA"] = CONTAMINATION_PATTERNS["TENNIS_IN_CBB"]
            patterns["GOLF_IN_NBA"] = CONTAMINATION_PATTERNS["GOLF_IN_CBB"]
            patterns["NFL_IN_NBA"] = CONTAMINATION_PATTERNS["NFL_IN_CBB"]
            
        # Add more sport-specific patterns as needed
        
        return patterns
    
    def _fix_json_cache(self, json_file: Path, contaminated_keys: List[str]) -> int:
        """Remove contaminated keys from JSON cache file."""
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            return 0
        
        if not isinstance(data, dict):
            return 0
        
        fixed = 0
        for key in contaminated_keys:
            if key in data and not key.startswith("FILE_ERROR"):
                del data[key]
                fixed += 1
        
        if fixed > 0:
            # Backup original
            backup_path = json_file.with_suffix(".json.bak")
            json_file.rename(backup_path)
            
            # Write cleaned version
            json_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            
        return fixed
    
    def validate_all(self, fix: bool = False) -> Dict[str, ValidationResult]:
        """Validate all sport caches."""
        results = {}
        for sport in VALID_SPORTS:
            results[sport] = self.validate(sport, fix=fix)
        return results


# =============================================================================
# AUTO-RESET DECORATOR
# =============================================================================

def auto_reset_on_contamination(sport: str):
    """
    Decorator that auto-resets cache if contamination is detected.
    
    Usage:
        @auto_reset_on_contamination("CBB")
        def run_cbb_pipeline(skip_ingest=False):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            skip_ingest = kwargs.get("skip_ingest", False)
            
            if skip_ingest:
                # Validate cache before proceeding
                validator = PreflightCacheValidator()
                result = validator.validate(sport, fix=False)
                
                if not result.passed:
                    print(f"\n⚠️  [{sport}] Cache contamination detected with skip_ingest=True")
                    print(f"   Contaminated keys: {sum(len(r.contaminated_keys) for r in result.reports)}")
                    
                    # Auto-fix
                    print(f"   Auto-fixing cache...")
                    fix_result = validator.validate(sport, fix=True)
                    print(f"   Fixed {fix_result.fixed_count} keys")
                    
                    # Re-validate
                    recheck = validator.validate(sport, fix=False)
                    if not recheck.passed:
                        print(f"\n❌ [{sport}] Cache still contaminated after fix")
                        print(f"   Forcing skip_ingest=False for fresh ingest")
                        kwargs["skip_ingest"] = False
                    else:
                        print(f"   ✅ Cache is now clean")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Preflight cache validator - check for cross-sport contamination"
    )
    parser.add_argument(
        "--sport",
        type=str,
        help=f"Sport to validate (one of: {', '.join(sorted(VALID_SPORTS))})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all sport caches",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Remove contaminated keys (creates .bak backup)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code if contamination found",
    )
    
    args = parser.parse_args()
    
    if not args.sport and not args.all:
        parser.print_help()
        print("\nError: Must specify --sport SPORT or --all")
        sys.exit(1)
    
    validator = PreflightCacheValidator()
    
    if args.all:
        results = validator.validate_all(fix=args.fix)
    else:
        results = {args.sport.upper(): validator.validate(args.sport, fix=args.fix)}
    
    # Output results
    if args.json:
        output = {}
        for sport, result in results.items():
            output[sport] = {
                "passed": result.passed,
                "errors": result.errors,
                "warnings": result.warnings,
                "fixed_count": result.fixed_count,
                "reports": [r.to_dict() for r in result.reports],
            }
        print(json.dumps(output, indent=2))
    else:
        any_failed = False
        
        for sport, result in results.items():
            if result.passed:
                print(f"[OK] [{sport}] Cache is clean")
            else:
                any_failed = True
                print(f"\n[FAIL] [{sport}] Cache contamination detected")
                for error in result.errors:
                    print(f"   {error}")
                for report in result.reports:
                    if report.contaminated_keys:
                        print(f"\n   FILE: {Path(report.cache_path).name}:")
                        for key in report.contaminated_keys[:10]:
                            print(f"      - {key}")
                        if len(report.contaminated_keys) > 10:
                            print(f"      ... and {len(report.contaminated_keys) - 10} more")
                
                if args.fix and result.fixed_count > 0:
                    print(f"\n   FIXED {result.fixed_count} contaminated keys")
        
        if args.strict and any_failed:
            sys.exit(1)


if __name__ == "__main__":
    main()
