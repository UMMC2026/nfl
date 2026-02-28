"""
FUOOM DATA LAYER - Unified Access to All Databases
One import, all data.

Usage:
    from fuoom_data import data
    
    # Player stats (fast, indexed)
    stats = data.get_player_stats("Cam Thomas")
    
    # Validate projection (detect μ=8.7 bugs)
    valid = data.validate_projection("Cam Thomas", "points", 8.7)
    
    # Pick history
    history = data.get_pick_history("Cam Thomas")
    
    # Log picks from slate
    data.log_slate("outputs/FILE.json")
    
    # Get calibration report
    report = data.get_calibration_report()
"""

from pathlib import Path
from datetime import date, datetime
from typing import Optional, Dict, List, Any

from pick_history_db import PickHistoryDB
from player_stats_db import PlayerStatsDB
from opponent_defense_db import OpponentDefenseDB
from home_away_splits_db import HomeAwaySplitsDB
from injury_tracker_db import InjuryTrackerDB

# ═══════════════════════════════════════════════════════════════════
# UNIFIED DATA LAYER
# ═══════════════════════════════════════════════════════════════════

class FuoomData:
    """
    Unified data access layer for FUOOM betting system.
    
    Provides single interface to:
    - Player stats cache (SQLite)
    - Pick history database (SQLite)
    - Opponent defense rankings
    - Home/away splits
    - Injury tracking
    - Validation utilities
    - Calibration queries
    """
    
    def __init__(self):
        self.stats_db = PlayerStatsDB()
        self.picks_db = PickHistoryDB()
        self.defense_db = OpponentDefenseDB()
        self.splits_db = HomeAwaySplitsDB()
        self.injury_db = InjuryTrackerDB()
    
    # ═══════════════════════════════════════════════════════════════
    # PLAYER STATS
    # ═══════════════════════════════════════════════════════════════
    
    def get_player_stats(self, player_name: str, update: bool = False) -> Optional[Dict]:
        """
        Get player stats from cache.
        
        Args:
            player_name: Full player name
            update: If True, refresh from API first
        
        Returns:
            Dict with all cached stats
        """
        if update:
            self.stats_db.update_player(player_name)
        return self.stats_db.get_player(player_name)
    
    def get_stat(self, player_name: str, stat: str) -> Optional[Dict]:
        """
        Get specific stat for player.
        
        Returns:
            Dict with mu, sigma, n, team
        """
        return self.stats_db.get_stat(player_name, stat)
    
    def update_player_stats(self, player_name: str, force: bool = False) -> bool:
        """Update player stats from NBA API"""
        return self.stats_db.update_player(player_name, force)
    
    def update_stats_from_slate(self, json_file: str, force: bool = False) -> Dict:
        """Update stats for all players in a slate"""
        return self.stats_db.update_from_json(json_file, force)
    
    def get_team_players(self, team: str) -> List[Dict]:
        """Get all cached players for a team"""
        return self.stats_db.get_team_players(team)
    
    # ═══════════════════════════════════════════════════════════════
    # OPPONENT DEFENSE
    # ═══════════════════════════════════════════════════════════════
    
    def get_defense_rank(self, opponent: str, stat: str) -> Optional[Dict]:
        """
        Get defensive ranking for opponent.
        
        Example:
            data.get_defense_rank("DET", "points")
            # → {'rank': 29, 'avg_allowed': 118.5, 'rating': 'TERRIBLE'}
        """
        return self.defense_db.get_defense_rank(opponent, stat)
    
    def get_matchup_context(self, player_name: str, stat: str, opponent: str) -> str:
        """
        Get formatted matchup context for narratives.
        
        Example:
            data.get_matchup_context("Cam Thomas", "points", "DET")
            # → "vs DET 🎯(ranks 29th defending PTS, allows 118.5)"
        """
        return self.defense_db.get_matchup_context(player_name, stat, opponent)
    
    def get_matchup_adjustment(self, stat: str, opponent: str) -> Dict:
        """
        Get projection adjustment based on opponent defense.
        
        Example:
            data.get_matchup_adjustment("points", "DET")
            # → {'adjustment_pct': 7, 'direction': 'up', 'reason': 'DET terrible defense'}
        """
        return self.defense_db.get_matchup_adjustment(stat, opponent)
    
    # ═══════════════════════════════════════════════════════════════
    # HOME/AWAY SPLITS
    # ═══════════════════════════════════════════════════════════════
    
    def get_player_splits(self, player_name: str) -> Optional[Dict]:
        """
        Get home/away performance splits.
        
        Example:
            data.get_player_splits("Stephen Curry")
            # → {'home_pts_avg': 28.3, 'away_pts_avg': 24.1, ...}
        """
        return self.splits_db.get_player_splits(player_name)
    
    def get_location_adjustment(self, player_name: str, stat: str, is_home: bool) -> Dict:
        """
        Get projection adjustment based on game location.
        
        Example:
            data.get_location_adjustment("Stephen Curry", "points", is_home=False)
            # → {'adjustment': -4.2, 'pct_diff': -14.8%}
        """
        return self.splits_db.get_location_adjustment(player_name, stat, is_home)
    
    def update_player_splits(self, player_name: str, force: bool = False) -> bool:
        """Update home/away splits for a player"""
        return self.splits_db.update_player(player_name, force)
    
    # ═══════════════════════════════════════════════════════════════
    # VALIDATION
    # ═══════════════════════════════════════════════════════════════
    
    def validate_projection(self, player_name: str, stat: str, mu: float) -> Dict:
        """
        Validate a projection against cached data.
        
        Returns:
            Dict with is_valid, actual_avg, pct_diff, warning
        
        Example:
            result = data.validate_projection("Cam Thomas", "points", 8.7)
            # Returns: {'is_valid': False, 'warning': 'SUSPICIOUS_PROJECTION', ...}
        """
        return self.stats_db.validate_projection(player_name, stat, mu)
    
    def validate_slate(self, json_file: str) -> List[Dict]:
        """
        Validate all projections in a slate file.
        
        Returns:
            List of validation results (only suspicious ones)
        """
        import json
        
        with open(json_file, encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            picks = data.get('results', data.get('picks', []))
        else:
            picks = data
        
        issues = []
        for pick in picks:
            player = pick.get('player', pick.get('player_name'))
            stat = pick.get('stat', pick.get('market'))
            mu = pick.get('mu')
            
            if player and stat and mu:
                result = self.validate_projection(player, stat, mu)
                if result.get('is_valid') is False:
                    issues.append({
                        'player': player,
                        'stat': stat,
                        'projected': mu,
                        **result
                    })
        
        return issues
    
    # ═══════════════════════════════════════════════════════════════
    # PICK HISTORY
    # ═══════════════════════════════════════════════════════════════
    
    def log_pick(self, pick: Dict, slate_date: date = None, slate_name: str = None) -> int:
        """Log a single pick to history database"""
        return self.picks_db.log_pick(pick, slate_date, slate_name)
    
    def log_slate(self, json_file: str) -> int:
        """Log all picks from a slate file"""
        return self.picks_db.log_from_json(json_file)
    
    def resolve_pick(self, player_name: str, stat: str, actual_value: float, 
                     slate_date: date = None) -> List[bool]:
        """Resolve pick(s) with actual result"""
        return self.picks_db.resolve_by_player(player_name, stat, actual_value, slate_date)
    
    def get_pick_history(self, player_name: str, limit: int = 50) -> List[Dict]:
        """Get all picks for a player"""
        return self.picks_db.get_player_history(player_name, limit)
    
    def get_unresolved_picks(self, slate_date: date = None) -> List[Dict]:
        """Get picks awaiting resolution"""
        return self.picks_db.get_unresolved_picks(slate_date)
    
    # ═══════════════════════════════════════════════════════════════
    # ANALYTICS
    # ═══════════════════════════════════════════════════════════════
    
    def get_hit_rate(self, player_name: str = None, stat: str = None, 
                     direction: str = None, tier: str = None) -> Dict:
        """
        Get hit rate with optional filters.
        
        Examples:
            data.get_hit_rate()                           # Overall
            data.get_hit_rate(player_name="Cam Thomas")   # By player
            data.get_hit_rate(stat="points")              # By stat
            data.get_hit_rate(direction="lower")          # By direction
        """
        return self.picks_db.get_hit_rate(player_name, stat, direction, tier)
    
    def get_calibration_report(self, sport: str = None) -> List[Dict]:
        """
        Get calibration data - predicted vs actual hit rates.
        
        Returns:
            List of dicts with confidence bucket, predicted, actual, delta
        """
        return self.picks_db.get_calibration_report(sport)
    
    def get_stat_performance(self) -> List[Dict]:
        """Get hit rate breakdown by stat type"""
        return self.picks_db.get_stat_performance()
    
    def get_direction_performance(self) -> Dict:
        """Get hit rate breakdown by direction (higher/lower)"""
        return self.picks_db.get_direction_performance()
    
    def get_tier_performance(self) -> List[Dict]:
        """Get hit rate breakdown by tier"""
        return self.picks_db.get_tier_performance()
    
    def get_daily_summary(self, slate_date: date = None) -> Dict:
        """Get summary stats for a specific day"""
        return self.picks_db.get_daily_summary(slate_date)
    
    # ═══════════════════════════════════════════════════════════════
    # INJURY TRACKING
    # ═══════════════════════════════════════════════════════════════
    
    def get_player_injury(self, player_name: str) -> Optional[Dict]:
        """Get injury status for a player"""
        return self.injury_db.get_player_status(player_name)
    
    def is_injured(self, player_name: str) -> bool:
        """Check if player has injury status"""
        return self.injury_db.is_injured(player_name)
    
    def should_skip_player(self, player_name: str) -> bool:
        """Check if player should be skipped (OUT/DOUBTFUL)"""
        return self.injury_db.should_skip(player_name)
    
    def check_slate_injuries(self, json_file: str) -> Dict:
        """Check all players in slate for injuries"""
        return self.injury_db.check_slate(json_file)
    
    def get_injury_warning(self, player_name: str) -> Optional[str]:
        """Get formatted injury warning for narratives"""
        return self.injury_db.get_injury_warning(player_name)
    
    def get_all_injuries(self) -> List[Dict]:
        """Get all active injuries"""
        return self.injury_db.get_all_injuries()
    
    # ═══════════════════════════════════════════════════════════════
    # CROSS-DATABASE QUERIES
    # ═══════════════════════════════════════════════════════════════
    
    def find_suspicious_projections(self) -> List[Dict]:
        """
        Find all picks where projection differs significantly from cached average.
        
        This is the query that would have caught the Cam Thomas μ=8.7 bug!
        """
        return self.picks_db.find_suspicious_projections(self.stats_db.get_connection())
    
    def get_player_profile(self, player_name: str) -> Dict:
        """
        Get complete player profile with stats, splits, and pick history.
        
        Returns:
            Dict with cached stats, splits, pick history, and hit rates
        """
        stats = self.get_player_stats(player_name, update=True)
        splits = self.get_player_splits(player_name)
        history = self.get_pick_history(player_name, limit=20)
        hit_rate = self.get_hit_rate(player_name=player_name)
        
        # Update splits if not cached
        if not splits:
            self.update_player_splits(player_name)
            splits = self.get_player_splits(player_name)
        
        return {
            'player_name': player_name,
            'stats': stats,
            'splits': splits,
            'pick_history': history,
            'hit_rate': hit_rate,
            'generated_at': datetime.now().isoformat()
        }
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        return {
            'stats_cache': self.stats_db.get_stats(),
            'pick_history': self.picks_db.get_stats(),
            'splits': self.splits_db.get_stats(),
            'defense': {'teams': 30}  # Hardcoded data
        }
    
    def export_all(self, output_dir: str = "exports"):
        """Export all databases to CSV"""
        Path(output_dir).mkdir(exist_ok=True)
        self.stats_db.export_to_csv(f"{output_dir}/player_stats.csv")
        self.picks_db.export_to_csv(f"{output_dir}/pick_history.csv")
        print(f"✅ Exported all data to {output_dir}/")
    
    def print_dashboard(self):
        """Print quick system dashboard"""
        stats = self.get_stats()
        
        print("=" * 80)
        print("📊 FUOOM DATA DASHBOARD")
        print("=" * 80)
        print()
        
        # Stats cache
        sc = stats['stats_cache']
        print(f"📊 PLAYER STATS CACHE")
        print(f"   Players: {sc['total_players']} ({sc['fresh_cache']} fresh)")
        print(f"   Teams: {sc['unique_teams']}")
        print()
        
        # Pick history
        ph = stats['pick_history']
        print(f"📋 PICK HISTORY")
        print(f"   Total picks: {ph['total_picks']}")
        print(f"   Resolved: {ph['resolved_picks']}")
        print(f"   Pending: {ph['pending_picks']}")
        print(f"   Unique players: {ph['unique_players']}")
        print(f"   Slates: {ph['unique_slates']}")
        print()
        
        # Performance summary (if any resolved)
        if ph['resolved_picks'] > 0:
            overall = self.get_hit_rate()
            print(f"📈 PERFORMANCE")
            print(f"   Overall hit rate: {overall['hit_rate']:.1f}%")
            print(f"   Sample size: {overall['total']} picks")
            
            # By stat
            stat_perf = self.get_stat_performance()
            if stat_perf:
                print(f"\n   By Stat:")
                for sp in stat_perf[:5]:
                    print(f"      {sp['stat']}: {sp['hit_rate']:.1f}% ({sp['total_picks']} picks)")
        
        print()
        print("=" * 80)


# ═══════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════

# Global instance for easy import
data = FuoomData()

# Convenience functions at module level
get_player_stats = data.get_player_stats
get_stat = data.get_stat
validate_projection = data.validate_projection
log_slate = data.log_slate
get_hit_rate = data.get_hit_rate
get_calibration_report = data.get_calibration_report
get_defense_rank = data.get_defense_rank
get_matchup_context = data.get_matchup_context
get_matchup_adjustment = data.get_matchup_adjustment
get_player_splits = data.get_player_splits
get_location_adjustment = data.get_location_adjustment
get_player_injury = data.get_player_injury
is_injured = data.is_injured
should_skip_player = data.should_skip_player
get_injury_warning = data.get_injury_warning
check_slate_injuries = data.check_slate_injuries


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='FUOOM Data Layer')
    parser.add_argument('--dashboard', action='store_true', help='Show system dashboard')
    parser.add_argument('--player', type=str, help='Get complete player profile')
    parser.add_argument('--validate', type=str, help='Validate slate file')
    parser.add_argument('--log', type=str, help='Log picks from slate file')
    parser.add_argument('--calibration', action='store_true', help='Show calibration report')
    parser.add_argument('--export', action='store_true', help='Export all data to CSV')
    
    args = parser.parse_args()
    
    data_layer = FuoomData()
    
    if args.dashboard:
        data_layer.print_dashboard()
    
    elif args.player:
        profile = data_layer.get_player_profile(args.player)
        
        print("=" * 80)
        print(f"👤 {args.player} PROFILE")
        print("=" * 80)
        
        if profile['stats']:
            s = profile['stats']
            print(f"\n📊 CURRENT STATS (L10)")
            print(f"   Team: {s.get('team')}")
            print(f"   PPG: {s.get('points_L10', 0):.1f} (σ={s.get('points_L10_std', 0):.1f})")
            print(f"   RPG: {s.get('rebounds_L10', 0):.1f}")
            print(f"   APG: {s.get('assists_L10', 0):.1f}")
            print(f"   3PM: {s.get('fg3_made_L10', 0):.1f}")
        
        if profile['hit_rate']['total'] > 0:
            hr = profile['hit_rate']
            print(f"\n📈 PICK PERFORMANCE")
            print(f"   Hit rate: {hr['hit_rate']:.1f}%")
            print(f"   Record: {hr['hits']}/{hr['total']}")
        
        if profile['pick_history']:
            print(f"\n📋 RECENT PICKS")
            for pick in profile['pick_history'][:5]:
                result = '✅' if pick['hit'] else '❌' if pick['hit'] is not None else '⏳'
                print(f"   {result} {pick['slate_date']} | {pick['stat']} {pick['direction']} {pick['line']}")
    
    elif args.validate:
        print(f"🔍 Validating {args.validate}...")
        issues = data_layer.validate_slate(args.validate)
        
        if issues:
            print(f"\n⚠️  FOUND {len(issues)} SUSPICIOUS PROJECTIONS:")
            for issue in issues:
                print(f"   ❌ {issue['player']} {issue['stat']}: projected {issue['projected']:.1f} but avg is {issue['actual_avg']:.1f} ({issue['pct_diff']:+.1f}%)")
        else:
            print("✅ All projections look valid!")
    
    elif args.log:
        count = data_layer.log_slate(args.log)
        print(f"✅ Logged {count} picks from {args.log}")
    
    elif args.calibration:
        report = data_layer.get_calibration_report()
        
        print("=" * 80)
        print("📊 CALIBRATION REPORT")
        print("=" * 80)
        print()
        
        if report:
            print(f"{'Confidence':<15} {'Predicted':<12} {'Actual':<12} {'Delta':<10} {'N':<8}")
            print("-" * 60)
            for row in report:
                print(f"{row['confidence_bucket']:<15} {row['predicted_rate']:<12.1f} {row['actual_rate']:<12.1f} {row['delta']:<10.1f} {row['sample_size']:<8}")
        else:
            print("No resolved picks yet. Run --log to add picks, then resolve them.")
    
    elif args.export:
        data_layer.export_all()
    
    else:
        print("Usage:")
        print()
        print("  # Show dashboard")
        print("  python fuoom_data.py --dashboard")
        print()
        print("  # Get player profile")
        print('  python fuoom_data.py --player "Cam Thomas"')
        print()
        print("  # Validate slate")
        print("  python fuoom_data.py --validate outputs/FILE.json")
        print()
        print("  # Log picks")
        print("  python fuoom_data.py --log outputs/FILE.json")
        print()
        print("  # Calibration report")
        print("  python fuoom_data.py --calibration")
        print()
        print("  # Export all data")
        print("  python fuoom_data.py --export")
