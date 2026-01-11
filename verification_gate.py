"""
Pre-Output Verification Gate
Validates all data before any report/cheatsheet generation.
Catches team mismatches, stale data, and inconsistencies.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import requests
from nba_api.stats.endpoints import leaguedashplayerstats
import time

# Known team trades/transfers for 2025-26 season
KNOWN_TEAM_CHANGES = {
    "Jordan Clarkson": ("UTA", "NYK", "2025-12-20"),
    "De'Aaron Fox": ("SAC", "SAS", "2026-01-02"),  # Traded to Spurs
    # Add other known changes here
}

NBA_TEAMS = {
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
}


class VerificationError(Exception):
    """Raised when critical verification checks fail"""
    pass


class VerificationGate:
    """Gate that validates all data before output generation"""
    
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.corrections = []
        self._nba_stats_cache = None  # Cache for official NBA stats
        
    def _fetch_nba_official_stats(self) -> Dict[str, dict]:
        """Fetch official NBA season averages for cross-validation"""
        if self._nba_stats_cache is not None:
            return self._nba_stats_cache
        
        print("\n🔍 Fetching official NBA stats for cross-validation...")
        try:
            stats = leaguedashplayerstats.LeagueDashPlayerStats(
                season='2025-26',
                per_mode_detailed='PerGame'
            )
            df = stats.get_data_frames()[0]
            
            # Create lookup dict: player_name -> {team, pts, reb, ast, etc.}
            stats_dict = {}
            for _, row in df.iterrows():
                stats_dict[row['PLAYER_NAME']] = {
                    'team': row['TEAM_ABBREVIATION'],
                    'points': row['PTS'],
                    'rebounds': row['REB'],
                    'assists': row['AST'],
                    'pts+reb+ast': row['PTS'] + row['REB'] + row['AST'],
                    'pra': row['PTS'] + row['REB'] + row['AST'],
                    '3pm': row['FG3M'],
                }
            
            self._nba_stats_cache = stats_dict
            print(f"   ✅ Loaded stats for {len(stats_dict)} players")
            return stats_dict
            
        except Exception as e:
            self.warnings.append(f"⚠️  Could not fetch NBA official stats: {e}")
            return {}
    
    def verify_against_official_stats(self, picks: List[dict]) -> List[dict]:
        """Cross-validate predictions against official NBA season averages"""
        print("\n🔍 VERIFICATION: Cross-checking against NBA official stats...")
        
        official_stats = self._fetch_nba_official_stats()
        if not official_stats:
            self.warnings.append("⚠️  Skipping NBA stats cross-validation (fetch failed)")
            return picks
        
        discrepancies = 0
        for pick in picks:
            player = pick.get('player', '')
            mu = pick.get('mu')
            stat = pick.get('stat', '')
            
            if player not in official_stats:
                continue  # Player not in official stats (bench/inactive)
            
            official = official_stats[player]
            
            # Check team match
            pick_team = pick.get('team')
            official_team = official['team']
            if pick_team != official_team and pick_team not in ['', None]:
                self.warnings.append(
                    f"⚠️  {player}: Team mismatch (ours: {pick_team}, NBA: {official_team})"
                )
            
            # Check stat average discrepancy
            if mu is not None and stat in official:
                official_avg = official[stat]
                diff_pct = abs(mu - official_avg) / official_avg if official_avg > 0 else 0
                
                # Flag if our average differs by >50% from official
                # (We use 10-game rolling avg, so some variance from season avg is expected)
                if diff_pct > 0.50:
                    discrepancies += 1
                    self.warnings.append(
                        f"⚠️  {player} {stat}: Our avg {mu:.1f} vs NBA {official_avg:.1f} ({diff_pct*100:.0f}% diff)"
                    )
                    pick['official_avg_discrepancy'] = True
                    pick['official_avg'] = official_avg
        
        if discrepancies > 0:
            print(f"   ⚠️  Found {discrepancies} statistical discrepancies (>50% difference)")
        else:
            print(f"   ✅ All averages within 50% of official NBA stats")
        
        return picks
    
    def verify_team_accuracy(self, picks: List[dict]) -> List[dict]:
        """Cross-check player teams against known current rosters"""
        print("\n🔍 VERIFICATION: Checking team assignments...")
        
        corrected_picks = []
        for pick in picks:
            player = pick.get('player', '')
            current_team = pick.get('team', '')
            
            # Check against known team changes
            if player in KNOWN_TEAM_CHANGES:
                old_team, new_team, trade_date = KNOWN_TEAM_CHANGES[player]
                if current_team == old_team:
                    self.corrections.append(
                        f"⚠️  {player}: Outdated team {old_team} → {new_team} (traded {trade_date})"
                    )
                    pick['team'] = new_team
                    pick['team_corrected'] = True
                    pick['previous_team'] = old_team
            
            # Validate team code exists
            if current_team and current_team not in NBA_TEAMS:
                self.errors.append(
                    f"❌ {player}: Invalid team code '{current_team}'"
                )
                continue  # Skip invalid picks
                
            corrected_picks.append(pick)
        
        print(f"   ✅ Verified {len(corrected_picks)} picks")
        if self.corrections:
            for corr in self.corrections:
                print(f"   {corr}")
        
        return corrected_picks
    
    def verify_data_freshness(self, picks: List[dict], max_age_hours: int = 24) -> bool:
        """Check if hydration data is recent enough"""
        print("\n🔍 VERIFICATION: Checking data freshness...")
        
        meta_path = Path('.hydration_meta.json')
        if not meta_path.exists():
            self.warnings.append("⚠️  No hydration metadata found - cannot verify freshness")
            return True  # Allow but warn
        
        try:
            meta = json.load(open(meta_path))
            hydration_time = datetime.fromisoformat(meta.get('timestamp'))
            age_hours = (datetime.now(timezone.utc) - hydration_time).total_seconds() / 3600
            
            if age_hours > max_age_hours:
                self.warnings.append(
                    f"⚠️  Data is {age_hours:.1f} hours old (limit: {max_age_hours}h)"
                )
                self.warnings.append("   Consider re-running hydration for latest stats")
            else:
                print(f"   ✅ Data is {age_hours:.1f} hours old (fresh)")
                
        except Exception as e:
            self.warnings.append(f"⚠️  Could not verify data age: {e}")
        
        return True
    
    def verify_stat_consistency(self, picks: List[dict]) -> List[dict]:
        """Check for statistical anomalies that suggest data issues"""
        print("\n🔍 VERIFICATION: Checking statistical consistency...")
        
        anomalies = []
        validated_picks = []
        
        for pick in picks:
            mu = pick.get('mu')
            sigma = pick.get('sigma')
            line = pick.get('line')
            stat = pick.get('stat', '')
            player = pick.get('player', '')
            
            # Check for impossible values
            if mu is not None and mu < 0:
                anomalies.append(f"❌ {player} {stat}: negative average ({mu})")
                continue
                
            if sigma is not None and sigma < 0:
                anomalies.append(f"❌ {player} {stat}: negative std dev ({sigma})")
                continue
            
            # Check for extreme volatility
            if mu and sigma and sigma > mu * 2:
                self.warnings.append(
                    f"⚠️  {player} {stat}: High volatility (σ={sigma:.1f}, μ={mu:.1f})"
                )
            
            # Check for unrealistic averages by stat type
            stat_limits = {
                'points': (0, 50),
                'rebounds': (0, 25),
                'assists': (0, 20),
                'pts+reb+ast': (0, 80),
                'pra': (0, 80),
                '3pm': (0, 12),
            }
            
            if stat in stat_limits and mu is not None:
                min_val, max_val = stat_limits[stat]
                if not (min_val <= mu <= max_val):
                    anomalies.append(
                        f"❌ {player} {stat}: Unrealistic average {mu} (range: {min_val}-{max_val})"
                    )
                    continue
            
            validated_picks.append(pick)
        
        if anomalies:
            print(f"   ⚠️  Found {len(anomalies)} statistical anomalies:")
            for anom in anomalies[:5]:  # Show first 5
                print(f"      {anom}")
            if len(anomalies) > 5:
                print(f"      ... and {len(anomalies) - 5} more")
        else:
            print(f"   ✅ All {len(validated_picks)} picks passed statistical checks")
        
        return validated_picks
    
    def verify_roster_status(self, picks: List[dict]) -> List[dict]:
        """Check players are active/available based on roster files"""
        print("\n🔍 VERIFICATION: Checking roster status...")
        
        roster_path = Path('data_center/rosters/NBA_active_roster_current.csv')
        if not roster_path.exists():
            self.warnings.append("⚠️  No roster file found - cannot verify player status")
            return picks
        
        try:
            import csv
            with open(roster_path) as f:
                roster_data = list(csv.DictReader(f))
            
            active_players = {
                row['player_name']: row['status'] 
                for row in roster_data
            }
            
            verified_picks = []
            for pick in picks:
                player = pick.get('player', '')
                status = active_players.get(player)
                
                if status == 'ACTIVE':
                    pick['roster_verified'] = True
                elif status in ('QUESTIONABLE', 'DOUBTFUL'):
                    pick['injury_risk'] = True
                    self.warnings.append(f"⚠️  {player}: Listed as {status}")
                elif status is None:
                    self.warnings.append(f"⚠️  {player}: Not found in active roster")
                
                verified_picks.append(pick)
            
            print(f"   ✅ Checked {len(verified_picks)} picks against roster")
            
            return verified_picks
            
        except Exception as e:
            self.warnings.append(f"⚠️  Roster verification failed: {e}")
            return picks
    
    def run_full_verification(self, picks: List[dict]) -> Tuple[List[dict], bool]:
        """Run all verification checks and return (validated_picks, passed)"""
        print("\n" + "="*70)
        print("  🛡️  PRE-OUTPUT VERIFICATION GATE")
        print("="*70)
        
        # Run all checks
        picks = self.verify_team_accuracy(picks)
        picks = self.verify_against_official_stats(picks)  # NEW: NBA Stats API cross-check
        picks = self.verify_stat_consistency(picks)
        picks = self.verify_roster_status(picks)
        self.verify_data_freshness(picks)
        
        # Print summary
        print("\n" + "="*70)
        print("  📊 VERIFICATION SUMMARY")
        print("="*70)
        
        if self.corrections:
            print(f"\n✅ Auto-corrections: {len(self.corrections)}")
            for corr in self.corrections:
                print(f"   {corr}")
        
        if self.warnings:
            print(f"\n⚠️  Warnings: {len(self.warnings)}")
            for warn in self.warnings[:10]:  # Show first 10
                print(f"   {warn}")
            if len(self.warnings) > 10:
                print(f"   ... and {len(self.warnings) - 10} more warnings")
        
        if self.errors:
            print(f"\n❌ CRITICAL ERRORS: {len(self.errors)}")
            for err in self.errors:
                print(f"   {err}")
            print("\n⛔ VERIFICATION FAILED - Cannot generate output")
            return picks, False
        
        print(f"\n✅ VERIFICATION PASSED")
        print(f"   {len(picks)} picks validated and ready for output")
        print("="*70 + "\n")
        
        return picks, True
    
    def save_verification_report(self, output_dir: Path = None):
        """Save detailed verification report to file"""
        if output_dir is None:
            output_dir = Path('outputs')
        
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = output_dir / f'verification_report_{timestamp}.json'
        
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'corrections': self.corrections,
            'warnings': self.warnings,
            'errors': self.errors,
            'passed': len(self.errors) == 0
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Verification report saved: {report_path}")


if __name__ == '__main__':
    # Test verification on current picks
    picks = json.load(open('picks_hydrated.json'))
    
    gate = VerificationGate()
    verified_picks, passed = gate.run_full_verification(picks)
    gate.save_verification_report()
    
    if not passed:
        exit(1)
