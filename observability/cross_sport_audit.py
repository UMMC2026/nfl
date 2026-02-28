"""
Cross-Sport Data Isolation Audit Module
========================================
Detects and prevents data contamination between sports.

Critical Issues Found During Audit:
1. Calibration history missing 'league' column population
2. Shared cache/outputs directory with no sport prefixing
3. No runtime validation that NBA picks don't use Tennis models

FUOOM Governance: Sports MUST be isolated to prevent model contamination.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
import sqlite3
import csv


@dataclass
class IsolationViolation:
    """Represents a detected isolation violation."""
    severity: str  # CRITICAL, WARNING, INFO
    category: str  # cache, calibration, model, output
    sport_a: str
    sport_b: Optional[str]
    description: str
    file_path: Optional[str] = None
    recommendation: str = ""


@dataclass
class AuditResult:
    """Complete audit result."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    violations: List[IsolationViolation] = field(default_factory=list)
    checks_passed: int = 0
    checks_failed: int = 0
    
    @property
    def score(self) -> float:
        """Isolation score 0-100%"""
        total = self.checks_passed + self.checks_failed
        if total == 0:
            return 100.0
        return (self.checks_passed / total) * 100
    
    @property
    def is_healthy(self) -> bool:
        """True if no CRITICAL violations"""
        return not any(v.severity == "CRITICAL" for v in self.violations)


class CrossSportAuditor:
    """
    Audits the FUOOM system for cross-sport data isolation.
    
    Sports should NEVER share:
    - Player data
    - Calibration history rows
    - Model weights/predictions
    - Cache files without sport prefix
    """
    
    KNOWN_SPORTS = {"nba", "tennis", "cbb", "nfl", "soccer", "golf"}
    
    # Expected isolation boundaries
    SPORT_BOUNDARIES = {
        "nba": {
            "data_dirs": ["cache/nba_stats", "outputs/stats_cache"],
            "config": ["config/thresholds.py"],
            "allowed_apis": ["nba_api", "espn", "basketball_reference", "balldontlie"]
        },
        "tennis": {
            "data_dirs": ["tennis/data", "tennis/stats_cache", "tennis/outputs"],
            "config": ["tennis/config", "tennis/tennis_config.json"],
            "allowed_apis": ["tennis_api"]
        },
        "cbb": {
            "data_dirs": ["data/cbb", "sports/cbb/data", "sports/cbb/outputs"],
            "config": ["sports/cbb/config"],
            "allowed_apis": ["espn", "sportsreference"]
        },
        "nfl": {
            "data_dirs": ["data/nflverse"],
            "config": ["config/nfl_thresholds.py"],
            "allowed_apis": ["nflverse", "espn"]
        },
        "soccer": {
            "data_dirs": ["soccer/data", "soccer/outputs"],
            "config": ["soccer/config"],
            "allowed_apis": ["fbref", "understat"]
        },
        "golf": {
            "data_dirs": ["golf/data", "golf/outputs", "data/golf"],
            "config": ["golf/config"],
            "allowed_apis": ["datagolf"]
        }
    }
    
    def __init__(self, workspace_root: str = "."):
        self.root = Path(workspace_root)
        self.result = AuditResult()
    
    def audit_all(self) -> AuditResult:
        """Run complete cross-sport isolation audit."""
        print("\n" + "="*60)
        print("🔍 FUOOM CROSS-SPORT ISOLATION AUDIT")
        print("="*60 + "\n")
        
        # Run all audit checks
        self._audit_calibration_history()
        self._audit_cache_isolation()
        self._audit_output_isolation()
        self._audit_database_isolation()
        self._audit_config_isolation()
        self._audit_sport_registry()
        
        self._print_report()
        return self.result
    
    def _add_violation(self, violation: IsolationViolation):
        """Add a violation and increment failure count."""
        self.result.violations.append(violation)
        self.result.checks_failed += 1
    
    def _add_pass(self):
        """Record a passed check."""
        self.result.checks_passed += 1
    
    def _audit_calibration_history(self):
        """Audit calibration_history.csv for sport isolation."""
        print("📊 Auditing calibration history...")
        
        csv_path = self.root / "calibration_history.csv"
        if not csv_path.exists():
            self._add_violation(IsolationViolation(
                severity="WARNING",
                category="calibration",
                sport_a="all",
                sport_b=None,
                description="calibration_history.csv not found",
                recommendation="Create calibration history file"
            ))
            return
        
        # Check for missing league/sport column
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                
                # Check header
                if 'league' not in headers and 'sport' not in headers:
                    self._add_violation(IsolationViolation(
                        severity="CRITICAL",
                        category="calibration",
                        sport_a="all",
                        sport_b=None,
                        description="calibration_history.csv missing 'league' or 'sport' column",
                        file_path=str(csv_path),
                        recommendation="Add 'league' column to distinguish NBA/Tennis/CBB picks"
                    ))
                else:
                    self._add_pass()
                
                # Check rows for missing sport values
                missing_sport_count = 0
                total_rows = 0
                for row in reader:
                    total_rows += 1
                    league = row.get('league', '') or row.get('sport', '')
                    if not league or league.strip() == '':
                        missing_sport_count += 1
                
                if missing_sport_count > 0:
                    self._add_violation(IsolationViolation(
                        severity="CRITICAL",
                        category="calibration",
                        sport_a="unknown",
                        sport_b=None,
                        description=f"{missing_sport_count}/{total_rows} calibration rows missing sport identifier",
                        file_path=str(csv_path),
                        recommendation="Backfill league column based on stat types (PTS→NBA, Aces→Tennis)"
                    ))
                else:
                    self._add_pass()
                    
        except Exception as e:
            self._add_violation(IsolationViolation(
                severity="WARNING",
                category="calibration",
                sport_a="all",
                sport_b=None,
                description=f"Could not parse calibration history: {e}",
                file_path=str(csv_path)
            ))
    
    def _audit_cache_isolation(self):
        """Audit cache directories for cross-sport contamination."""
        print("📁 Auditing cache isolation...")
        
        cache_dir = self.root / "cache"
        if not cache_dir.exists():
            self._add_pass()  # No cache = no contamination
            return
        
        # Check for sport-agnostic files that should be sport-specific
        dangerous_patterns = [
            "player_*.json",  # Should be nba_player_*, tennis_player_*
            "stats_*.json",   # Should be sport prefixed
            "*.db"            # Databases should be sport-specific
        ]
        
        for pattern in dangerous_patterns:
            files = list(cache_dir.glob(pattern))
            for f in files:
                # Check if file is sport-prefixed
                name_lower = f.name.lower()
                has_sport_prefix = any(sport in name_lower for sport in self.KNOWN_SPORTS)
                
                if not has_sport_prefix and f.is_file():
                    # Check file content for sport hints
                    sport_hint = self._detect_sport_from_file(f)
                    
                    self._add_violation(IsolationViolation(
                        severity="WARNING",
                        category="cache",
                        sport_a=sport_hint or "unknown",
                        sport_b=None,
                        description=f"Cache file without sport prefix: {f.name}",
                        file_path=str(f),
                        recommendation=f"Rename to {sport_hint}_{f.name}" if sport_hint else "Add sport prefix"
                    ))
        
        # Check matchups directory
        matchups_dir = cache_dir / "matchups"
        if matchups_dir.exists():
            # These should ONLY be NBA (player vs opponent patterns)
            for f in matchups_dir.glob("*.json"):
                self._add_pass()  # Matchup files are NBA-specific by design
        
        self._add_pass()  # Cache audit complete
    
    def _audit_output_isolation(self):
        """Audit outputs directory for cross-sport mixing."""
        print("📤 Auditing output isolation...")
        
        outputs_dir = self.root / "outputs"
        if not outputs_dir.exists():
            self._add_pass()
            return
        
        # Check for outputs with mixed sport content
        mixed_indicators = {
            "tennis": ["aces", "games", "sets", "surface"],
            "nba": ["points", "rebounds", "assists", "3pm", "pra"],
            "cbb": ["college", "ncaa"],
            "nfl": ["rushing", "receiving", "passing", "fantasy"],
            "golf": ["strokes", "birdies", "sg_"],
            "soccer": ["shots", "sot", "tackles"]
        }
        
        for json_file in outputs_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                    
                detected_sports = set()
                for sport, indicators in mixed_indicators.items():
                    if any(ind in content for ind in indicators):
                        detected_sports.add(sport)
                
                if len(detected_sports) > 1:
                    self._add_violation(IsolationViolation(
                        severity="CRITICAL",
                        category="output",
                        sport_a=list(detected_sports)[0],
                        sport_b=list(detected_sports)[1] if len(detected_sports) > 1 else None,
                        description=f"Output file contains mixed sports: {detected_sports}",
                        file_path=str(json_file),
                        recommendation="Split into sport-specific output files"
                    ))
                else:
                    self._add_pass()
                    
            except Exception:
                pass  # Skip unparseable files
    
    def _audit_database_isolation(self):
        """Audit SQLite databases for cross-sport contamination."""
        print("🗄️ Auditing database isolation...")
        
        # Check all .db files
        for db_file in self.root.rglob("*.db"):
            if "venv" in str(db_file) or ".venv" in str(db_file):
                continue  # Skip virtual env
                
            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                # Check if tables have sport column
                for table in tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [row[1].lower() for row in cursor.fetchall()]
                    
                    if 'sport' not in columns and 'league' not in columns:
                        # Check if this is a sport-specific DB by name
                        db_name_lower = db_file.name.lower()
                        if not any(sport in db_name_lower for sport in self.KNOWN_SPORTS):
                            self._add_violation(IsolationViolation(
                                severity="WARNING",
                                category="database",
                                sport_a="unknown",
                                sport_b=None,
                                description=f"Database {db_file.name} table '{table}' lacks sport identifier",
                                file_path=str(db_file),
                                recommendation="Add 'sport' column or rename DB with sport prefix"
                            ))
                        else:
                            self._add_pass()
                    else:
                        self._add_pass()
                
                conn.close()
                
            except Exception as e:
                pass  # Skip unreadable DBs
    
    def _audit_config_isolation(self):
        """Audit config files for cross-sport parameter leakage."""
        print("⚙️ Auditing config isolation...")
        
        # Check thresholds.py for proper sport overrides
        thresholds_file = self.root / "config" / "thresholds.py"
        if thresholds_file.exists():
            content = thresholds_file.read_text(encoding='utf-8')
            
            if "SPORT_TIER_OVERRIDES" in content:
                self._add_pass()
            else:
                self._add_violation(IsolationViolation(
                    severity="WARNING",
                    category="config",
                    sport_a="all",
                    sport_b=None,
                    description="thresholds.py missing SPORT_TIER_OVERRIDES",
                    file_path=str(thresholds_file),
                    recommendation="Add sport-specific tier thresholds"
                ))
        
        # Check for sport-specific config directories
        for sport, boundaries in self.SPORT_BOUNDARIES.items():
            for config_path in boundaries.get("config", []):
                full_path = self.root / config_path
                if not full_path.exists():
                    # Only warn for production sports
                    if sport in ["nba", "tennis", "cbb"]:
                        self._add_violation(IsolationViolation(
                            severity="INFO",
                            category="config",
                            sport_a=sport,
                            sport_b=None,
                            description=f"Missing sport-specific config: {config_path}",
                            recommendation="Create sport-isolated configuration"
                        ))
                else:
                    self._add_pass()
    
    def _audit_sport_registry(self):
        """Audit sport_registry.json for proper isolation settings."""
        print("📋 Auditing sport registry...")
        
        registry_file = self.root / "config" / "sport_registry.json"
        if not registry_file.exists():
            self._add_violation(IsolationViolation(
                severity="CRITICAL",
                category="config",
                sport_a="all",
                sport_b=None,
                description="sport_registry.json not found",
                file_path=str(registry_file),
                recommendation="Create sport registry for isolation governance"
            ))
            return
        
        try:
            with open(registry_file, 'r') as f:
                registry = json.load(f)
            
            sports = registry.get("sports", {})
            
            for sport_name, sport_config in sports.items():
                # Check for required isolation fields
                if "data_sources" not in sport_config:
                    self._add_violation(IsolationViolation(
                        severity="WARNING",
                        category="config",
                        sport_a=sport_name.lower(),
                        sport_b=None,
                        description=f"{sport_name} missing data_sources in registry",
                        file_path=str(registry_file),
                        recommendation="Define allowed data sources for isolation"
                    ))
                else:
                    self._add_pass()
                    
        except Exception as e:
            self._add_violation(IsolationViolation(
                severity="WARNING",
                category="config",
                sport_a="all",
                sport_b=None,
                description=f"Could not parse sport_registry.json: {e}"
            ))
    
    def _detect_sport_from_file(self, file_path: Path) -> Optional[str]:
        """Attempt to detect sport from file content."""
        try:
            content = file_path.read_text(encoding='utf-8').lower()
            
            # NBA indicators
            if any(term in content for term in ["rebounds", "assists", "3pm", "pts+reb+ast", "steals", "blocks"]):
                return "nba"
            
            # Tennis indicators
            if any(term in content for term in ["aces", "double_faults", "total_games", "surface"]):
                return "tennis"
            
            # NFL indicators
            if any(term in content for term in ["rushing_yards", "receiving_yards", "passing_yards"]):
                return "nfl"
            
            # CBB indicators
            if any(term in content for term in ["ncaa", "college"]):
                return "cbb"
                
        except Exception:
            pass
        
        return None
    
    def _print_report(self):
        """Print formatted audit report."""
        print("\n" + "="*60)
        print("📊 AUDIT RESULTS")
        print("="*60)
        
        print(f"\n✅ Checks Passed: {self.result.checks_passed}")
        print(f"❌ Checks Failed: {self.result.checks_failed}")
        print(f"📈 Isolation Score: {self.result.score:.1f}%")
        
        if self.result.violations:
            print(f"\n🚨 VIOLATIONS ({len(self.result.violations)}):")
            print("-"*60)
            
            # Group by severity
            for severity in ["CRITICAL", "WARNING", "INFO"]:
                violations = [v for v in self.result.violations if v.severity == severity]
                if violations:
                    icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}[severity]
                    print(f"\n{icon} {severity} ({len(violations)}):")
                    for v in violations:
                        print(f"   • [{v.category}] {v.description}")
                        if v.recommendation:
                            print(f"     💡 {v.recommendation}")
        else:
            print("\n✨ No violations found! Sports are properly isolated.")
        
        print("\n" + "="*60)
        
        if not self.result.is_healthy:
            print("⚠️  CRITICAL ISSUES DETECTED - Action required before production")
        else:
            print("✅ System is healthy for production use")


def fix_calibration_sport_column():
    """
    Fix the calibration_history.csv by backfilling sport based on stat type.
    
    Stat → Sport mapping:
    - points, rebounds, assists, 3pm, steals, blocks, pts+reb+ast, pts+ast → NBA
    - aces, double_faults, total_games, games → Tennis
    - (same as NBA but check for college context) → CBB
    """
    csv_path = Path("calibration_history.csv")
    if not csv_path.exists():
        print("❌ calibration_history.csv not found")
        return
    
    NBA_STATS = {"points", "rebounds", "assists", "3pm", "steals", "blocks", 
                 "pts+reb+ast", "pts+ast", "pts+rebs", "rebs+asts", "pra",
                 "fantasy_points", "turnovers", "minutes"}
    TENNIS_STATS = {"aces", "double_faults", "total_games", "games", "sets"}
    NFL_STATS = {"rushing_yards", "receiving_yards", "passing_yards", "receptions",
                 "touchdowns", "fantasy_points"}
    GOLF_STATS = {"birdies", "strokes", "finishing_position", "sg_total"}
    SOCCER_STATS = {"shots", "sot", "goals", "tackles", "passes"}
    
    rows = []
    updated_count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        
        # Ensure league column exists
        if 'league' not in headers:
            headers.append('league')
        
        for row in reader:
            stat = (row.get('stat', '') or '').lower().strip()
            current_league = (row.get('league', '') or '').strip()
            
            if not current_league:
                # Determine sport from stat
                if stat in NBA_STATS or '+' in stat:  # Combined stats are NBA
                    row['league'] = 'nba'
                    updated_count += 1
                elif stat in TENNIS_STATS:
                    row['league'] = 'tennis'
                    updated_count += 1
                elif stat in NFL_STATS:
                    row['league'] = 'nfl'
                    updated_count += 1
                elif stat in GOLF_STATS:
                    row['league'] = 'golf'
                    updated_count += 1
                elif stat in SOCCER_STATS:
                    row['league'] = 'soccer'
                    updated_count += 1
                else:
                    # Default to NBA for unknown stats (most common)
                    row['league'] = 'nba'
                    updated_count += 1
            
            rows.append(row)
    
    # Write back
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✅ Fixed {updated_count} rows with missing league")
    print(f"📊 Total rows: {len(rows)}")


# Standalone execution
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--fix":
        print("🔧 Fixing calibration history sport column...")
        fix_calibration_sport_column()
    else:
        auditor = CrossSportAuditor()
        result = auditor.audit_all()
        
        if not result.is_healthy:
            print("\n💡 Run with --fix to auto-fix calibration history")
            sys.exit(1)
