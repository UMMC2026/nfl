#!/usr/bin/env python3
"""
DAILY_GAMES_REPORT_GATING.py

Enforces: "No Daily Games Report → No edges allowed"

This gating module is called by:
  - nfl_edge_generator.py (before confidence estimation)
  - nba_edge_generator.py (before confidence estimation)
  - cbb_edge_generator.py (before confidence estimation)
  - cheat_sheet_builder.py (before entry building)
  - generate_resolved_ledger.py (for calibration input)

If report missing or invalid → abort with SOP violation message
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# ===== CONFIGURATION =====
REPORTS_DIR = Path("reports")
REPORT_NAME_PATTERN = "DAILY_GAMES_REPORT_{date}.md"
REPORT_JSON_PATTERN = "DAILY_GAMES_REPORT_{date}.json"

# ===== GATING LOGIC =====

class DailyGamesReportGate:
    """
    Master gating controller. All edge systems check in before running.
    """

    def __init__(self, date: str = None):
        """
        Initialize gate with target date.
        
        Args:
            date: YYYY-MM-DD format (default: today)
        """
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        self.report_md_path = REPORTS_DIR / f"DAILY_GAMES_REPORT_{self.date}.md"
        self.report_json_path = REPORTS_DIR / f"DAILY_GAMES_REPORT_{self.date}.json"
        self.report_data = None
        self.status = None
        self.error_msg = None

    def validate_report_exists(self) -> bool:
        """Check if report files exist."""
        md_exists = self.report_md_path.exists()
        json_exists = self.report_json_path.exists()
        
        if not (md_exists and json_exists):
            self.status = "MISSING"
            self.error_msg = f"Daily Games Report missing for {self.date}. MD: {md_exists}, JSON: {json_exists}"
            return False
        
        return True

    def validate_report_structure(self) -> bool:
        """Validate JSON report contains all required sections."""
        try:
            with open(self.report_json_path, 'r') as f:
                self.report_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            self.status = "INVALID"
            self.error_msg = f"Report JSON parse error: {e}"
            return False

        required_sections = [
            "report_meta",
            "nfl",
            "nba",
            "cbb",
            "tennis",
            "soccer",
            "daily_summary"
        ]

        missing_sections = [s for s in required_sections if s not in self.report_data]
        if missing_sections:
            self.status = "INCOMPLETE"
            self.error_msg = f"Report missing sections: {missing_sections}"
            return False

        return True

    def get_confidence_caps(self, sport: str) -> Optional[Dict[str, float]]:
        """
        Extract confidence caps from report for a given sport.
        
        Used by edge generators to cap probabilities based on game context.
        
        Args:
            sport: 'NFL', 'NBA', 'CFB', 'CBB', 'TENNIS', 'SOCCER'
            
        Returns:
            Dict with keys like 'core', 'alt', 'td' and cap values
            or None if sport not in report
        """
        if not self.report_data:
            return None

        sport_key = sport.lower()
        if sport_key not in self.report_data:
            return None

        # Extract volume suppression + variance to adjust caps
        sport_data = self.report_data[sport_key]
        
        caps = {
            "core": 0.70,  # Base cap (NFL passing, NBA shooting)
            "alt": 0.65,   # Alternative stat (TD, 3-pt shooting)
            "td": 0.55     # Touchdown plays (highest variance)
        }

        # Adjust based on report context
        if "games" in sport_data:
            games = sport_data["games"]
            if games:
                first_game = games[0]
                
                # If volume_suppression is HIGH, reduce caps
                if first_game.get("volume_suppression") == "VERY_HIGH":
                    caps["core"] *= 0.95  # 70% → 66.5%
                    caps["alt"] *= 0.95
                elif first_game.get("volume_suppression") == "HIGH":
                    caps["core"] *= 0.97  # 70% → 68%
                    caps["alt"] *= 0.97
                
                # If variance is HIGH, reduce TD cap
                if first_game.get("variance") == "HIGH":
                    caps["td"] *= 0.95  # 55% → 52%

        return caps

    def get_game_context(self, sport: str, player_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve game context for edge checking.
        
        Used by edge generators to validate script alignment before confidence assignment.
        
        Args:
            sport: 'NFL', 'NBA', 'CFB', 'CBB', 'TENNIS', 'SOCCER'
            player_name: Optional filter for specific player/match
            
        Returns:
            Context dict with game script, defensive ratings, etc.
        """
        if not self.report_data:
            return None

        sport_key = sport.lower()
        if sport_key not in self.report_data:
            return None

        sport_data = self.report_data[sport_key]
        
        # Return all games/matches for sport
        games_key = "games" if sport in ["NFL", "NBA", "CBB"] else "matches"
        
        return {
            "sport": sport,
            "date": self.date,
            games_key: sport_data.get(games_key, []),
            "context": sport_data.get("context", ""),
            "report_status": self.report_data.get("report_status", "")
        }

    def check_clearance(self, sport: str) -> tuple[bool, str]:
        """
        Main gating function. Call before edge generation.
        
        Returns:
            (is_cleared, message)
        """
        if not self.validate_report_exists():
            return False, f"SOP VIOLATION: {self.error_msg}"

        if not self.validate_report_structure():
            return False, f"SOP VIOLATION: {self.error_msg}"

        self.status = "OPERATIONAL"
        return True, f"Gating PASSED for {sport} — proceeding with edge generation"

    def abort_if_missing(self, system: str, sport: str) -> None:
        """
        Convenience function for early abort in edge generators.
        
        Usage:
            gate = DailyGamesReportGate(date="2026-01-03")
            gate.abort_if_missing("nfl_edge_generator", "NFL")
            # If no report: raises SystemExit
        """
        is_cleared, message = self.check_clearance(sport)
        
        if not is_cleared:
            print(f"\n❌ {system.upper()} ABORT")
            print(f"   {message}")
            print(f"\n   Action Required: Generate {REPORTS_DIR}/DAILY_GAMES_REPORT_{self.date}.md")
            print(f"   Status: SOP violation — edge generation blocked")
            raise SystemExit(1)


# ===== INTEGRATION POINTS =====

def gate_nfl_edges(date: str = None) -> Dict[str, float]:
    """
    Called by nfl_edge_generator.py → returns confidence caps or aborts.
    
    Usage:
        from gating import gate_nfl_edges
        caps = gate_nfl_edges(date="2026-01-03")  # Get caps, or abort
    """
    gate = DailyGamesReportGate(date=date)
    gate.abort_if_missing("nfl_edge_generator", "NFL")
    return gate.get_confidence_caps("NFL")


def gate_nba_edges(date: str = None) -> Dict[str, float]:
    """Called by nba_edge_generator.py → returns confidence caps or aborts."""
    gate = DailyGamesReportGate(date=date)
    gate.abort_if_missing("nba_edge_generator", "NBA")
    return gate.get_confidence_caps("NBA")


def gate_cbb_edges(date: str = None) -> Dict[str, float]:
    """Called by cbb_edge_generator.py → returns confidence caps or aborts."""
    gate = DailyGamesReportGate(date=date)
    gate.abort_if_missing("cbb_edge_generator", "CBB")
    return gate.get_confidence_caps("CBB")


def gate_cheat_sheets(date: str = None) -> Dict[str, Any]:
    """
    Called by cheat_sheet_builder.py → returns game context for volume validation.
    
    Usage:
        from gating import gate_cheat_sheets
        context = gate_cheat_sheets(date="2026-01-03")
        games = context["games"]  # All NFL/NBA/CBB games
    """
    gate = DailyGamesReportGate(date=date)
    gate.abort_if_missing("cheat_sheet_builder", "NFL")
    
    # Return combined context for all sports
    all_context = {}
    for sport in ["NFL", "NBA", "CBB"]:
        all_context[sport] = gate.get_game_context(sport)
    
    return all_context


def gate_resolved_ledger(date: str = None) -> Dict[str, Any]:
    """
    Called by generate_resolved_ledger.py → returns report data for calibration.
    
    Usage:
        from gating import gate_resolved_ledger
        report = gate_resolved_ledger(date="2026-01-03")
        nfl_context = report["NFL"]  # For sport-adaptive calibration
    """
    gate = DailyGamesReportGate(date=date)
    gate.abort_if_missing("generate_resolved_ledger", "NFL")
    
    return {
        "nfl": gate.get_game_context("NFL"),
        "nba": gate.get_game_context("NBA"),
        "cbb": gate.get_game_context("CBB"),
        "report_data": gate.report_data
    }


# ===== CLI / TESTING =====

if __name__ == "__main__":
    import sys
    
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    
    gate = DailyGamesReportGate(date=date)
    is_cleared, message = gate.check_clearance("NFL")
    
    print(f"\n{'='*70}")
    print(f"DAILY GAMES REPORT GATING CHECK")
    print(f"{'='*70}")
    print(f"Date: {date}")
    print(f"MD Path: {gate.report_md_path}")
    print(f"JSON Path: {gate.report_json_path}")
    print(f"\nStatus: {gate.status}")
    print(f"Message: {message}")
    print(f"{'='*70}\n")
    
    if not is_cleared:
        sys.exit(1)
    
    # If cleared, show caps
    caps = gate.get_confidence_caps("NFL")
    print(f"NFL Confidence Caps (from report):")
    for key, val in caps.items():
        print(f"  {key}: {val:.0%}")
