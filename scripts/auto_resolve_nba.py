"""
Auto-Resolve NBA Picks from NBA API
Fetches box scores automatically and updates calibration_history.csv
"""
import sys
import io

# Force UTF-8 encoding for stdout and stderr (Windows-safe)
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='replace')
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add project root (go up from scripts/ to project root)
sys.path.insert(0, str(Path(__file__).parent.parent))

from calibration.unified_tracker import UnifiedCalibration

try:
    from telegram_push import _send as telegram_send
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

def auto_resolve_nba_picks(days_back: int = 7, verbose: bool = True):
    """
    Auto-resolve NBA picks from last N days using NBA API
    
    Args:
        days_back: How many days back to check for unresolved picks
        verbose: Print progress messages
    """
    try:
        from nba_api.stats.endpoints import playergamelogs
        from nba_api.stats.static import players as nba_players
    except ImportError:
        print("ERROR: nba_api not installed. Run: pip install nba_api")
        return
    
    cal = UnifiedCalibration()
    
    # Get unresolved NBA picks from last N days
    today = datetime.now()
    cutoff = today - timedelta(days=days_back)
    
    unresolved = [
        p for p in cal.picks 
        if p.sport.lower() == "nba" 
        and p.actual is None 
        and datetime.fromisoformat(p.date) >= cutoff
    ]
    
    if not unresolved:
        print(f"No unresolved NBA picks from last {days_back} days")
        return
    
    if verbose:
        print(f"Found {len(unresolved)} unresolved NBA picks from last {days_back} days")
        print()
    
    # Group by player for efficient API calls
    by_player = {}
    for pick in unresolved:
        if pick.player not in by_player:
            by_player[pick.player] = []
        by_player[pick.player].append(pick)
    
    # Stat name mapping (picks use lowercase, NBA API uses uppercase)
    stat_map = {
        "points": "PTS",
        "pts": "PTS",
        "rebounds": "REB",
        "reb": "REB",
        "assists": "AST",
        "ast": "AST",
        "3pm": "FG3M",
        "threes": "FG3M",
        "steals": "STL",
        "stl": "STL",
        "blocks": "BLK",
        "blk": "BLK",
        "turnovers": "TOV",
        "tov": "TOV",
    }
    
    # Combo stats need calculation
    combo_stats = {
        "pra": ["PTS", "REB", "AST"],
        "pts+reb+ast": ["PTS", "REB", "AST"],
        "pr": ["PTS", "REB"],
        "pts+reb": ["PTS", "REB"],
        "pa": ["PTS", "AST"],
        "pts+ast": ["PTS", "AST"],
        "ra": ["REB", "AST"],
        "reb+ast": ["REB", "AST"],
    }
    
    updated_count = 0
    failed_count = 0
    prediction_errors = []  # Track biggest misses
    
    # Calculate baseline stats before updates
    resolved_picks = [p for p in cal.picks if p.sport.lower() == "nba" and p.hit is not None]
    baseline_hit_rate = len([p for p in resolved_picks if p.hit]) / len(resolved_picks) if resolved_picks else 0.0
    stat_hits = {}
    for pick in resolved_picks:
        if pick.stat not in stat_hits:
            stat_hits[pick.stat] = {"total": 0, "hits": 0}
        stat_hits[pick.stat]["total"] += 1
        if pick.hit:
            stat_hits[pick.stat]["hits"] += 1
    
    if verbose:
        print(f"📊 Baseline: {len(resolved_picks)} resolved picks, {baseline_hit_rate:.1%} hit rate\n")
    
    # Fetch results for each player
    for player_name, picks in by_player.items():
        try:
            if verbose:
                print(f"Fetching games for {player_name}...")
            
            # Get player ID
            all_players = nba_players.get_players()
            player_match = [p for p in all_players if p['full_name'].lower() == player_name.lower()]
            
            if not player_match:
                # Try partial match
                player_match = [p for p in all_players if player_name.lower() in p['full_name'].lower()]
            
            if not player_match:
                if verbose:
                    print(f"  ⚠️  Player not found: {player_name}")
                failed_count += len(picks)
                continue
            
            player_id = player_match[0]['id']
            
            # Fetch game logs from last N days
            date_from = (today - timedelta(days=days_back)).strftime("%m/%d/%Y")
            logs = playergamelogs.PlayerGameLogs(
                player_id_nullable=player_id,
                season_nullable="2025-26",
                date_from_nullable=date_from
            )
            
            games_df = logs.get_data_frames()[0]
            
            if games_df.empty:
                if verbose:
                    print(f"  ⚠️  No games found for {player_name}")
                continue
            
            # Process each pick for this player
            for pick in picks:
                pick_date = datetime.fromisoformat(pick.date).date()
                
                # Find matching game
                games_df['GAME_DATE'] = pd.to_datetime(games_df['GAME_DATE'])
                game_row = games_df[games_df['GAME_DATE'].dt.date == pick_date]
                
                if game_row.empty:
                    if verbose:
                        print(f"  ⚠️  No game on {pick_date} for {player_name}")
                    failed_count += 1
                    continue
                
                # Extract stat value
                stat_lower = pick.stat.lower()
                
                # Handle combo stats
                if stat_lower in combo_stats:
                    components = combo_stats[stat_lower]
                    actual = sum(float(game_row[comp].iloc[0]) for comp in components)
                else:
                    # Single stat
                    nba_stat = stat_map.get(stat_lower)
                    if not nba_stat:
                        if verbose:
                            print(f"  ⚠️  Unknown stat: {pick.stat}")
                        failed_count += 1
                        continue
                    
                    actual = float(game_row[nba_stat].iloc[0])
                
                # Update pick with actual result
                pick.actual = actual
                pick.hit = (
                    actual > pick.line if pick.direction.lower() == "higher"
                    else actual < pick.line
                )
                pick.compute_brier()
                
                # Track prediction error for analysis
                error_magnitude = abs(pick.probability - (100 if pick.hit else 0))
                prediction_errors.append({
                    "player": pick.player,
                    "stat": pick.stat,
                    "direction": pick.direction,
                    "line": pick.line,
                    "predicted": pick.probability,
                    "actual": actual,
                    "hit": pick.hit,
                    "error": error_magnitude
                })
                
                # Success message
                hit_emoji = "✅" if pick.hit else "❌"
                if verbose:
                    print(f"  {hit_emoji} {pick.player} {pick.stat} {pick.direction} {pick.line}: "
                          f"Predicted {pick.probability:.1f}%, Actual {actual:.1f}, Hit={pick.hit}")
                
                updated_count += 1
        
        except Exception as e:
            if verbose:
                print(f"  ⚠️  Error fetching {player_name}: {e}")
            failed_count += len([p for p in picks if p.actual is None])
            continue
    
    # Save all updates
    if updated_count > 0:
        cal.save()
        
        # Calculate new stats after updates
        resolved_picks_after = [p for p in cal.picks if p.sport.lower() == "nba" and p.hit is not None]
        new_hit_rate = len([p for p in resolved_picks_after if p.hit]) / len(resolved_picks_after) if resolved_picks_after else 0.0
        
        # Calculate best performing stat
        stat_performance = {}
        for pick in resolved_picks_after:
            if pick.stat not in stat_performance:
                stat_performance[pick.stat] = {"total": 0, "hits": 0}
            stat_performance[pick.stat]["total"] += 1
            if pick.hit:
                stat_performance[pick.stat]["hits"] += 1
        
        best_stat = None
        best_rate = 0.0
        for stat, data in stat_performance.items():
            if data["total"] >= 5:  # Minimum sample size
                rate = data["hits"] / data["total"]
                if rate > best_rate:
                    best_rate = rate
                    best_stat = stat
        
        # Print comprehensive summary
        print("\n" + "="*60)
        print("📊 AUTO-RESOLVE SUMMARY")
        print("="*60)
        print(f"✅ Resolved {updated_count} picks")
        print(f"📈 Hit rate: {baseline_hit_rate:.1%} → {new_hit_rate:.1%} "
              f"({'+' if new_hit_rate >= baseline_hit_rate else ''}{(new_hit_rate - baseline_hit_rate):.1%})")
        if best_stat:
            print(f"🔥 Best stat: {best_stat.upper()} ({best_rate:.1%})")
        
        # Show biggest misses (top 5)
        if prediction_errors:
            sorted_errors = sorted(prediction_errors, key=lambda x: x["error"], reverse=True)
            misses = [e for e in sorted_errors if not e["hit"]][:5]
            
            if misses:
                print(f"\n❌ Biggest Misses:")
                for miss in misses:
                    direction_symbol = "H" if miss["direction"].lower() == "higher" else "L"
                    print(f"   {miss['player']} {miss['stat'].upper()} {miss['line']}{direction_symbol} → "
                          f"Predicted {miss['predicted']:.0f}%, Actual {miss['actual']:.1f} (MISS)")
        
        print("="*60 + "\n")
        
        # Send Telegram notification (best-effort)
        if TELEGRAM_AVAILABLE:
            try:
                telegram_msg = (
                    f"📊 *NBA Auto-Resolve Summary*\n\n"
                    f"✅ Resolved {updated_count} picks\n"
                    f"📈 Hit rate: {baseline_hit_rate:.1%} → {new_hit_rate:.1%} "
                    f"({'+'if new_hit_rate >= baseline_hit_rate else ''}{(new_hit_rate - baseline_hit_rate):.1%})\n"
                )
                if best_stat:
                    telegram_msg += f"🔥 Best stat: {best_stat.upper()} ({best_rate:.0%})\n"
                
                # Add top 3 biggest misses if available
                if prediction_errors:
                    sorted_errors = sorted(prediction_errors, key=lambda x: x["error"], reverse=True)
                    misses = [e for e in sorted_errors if not e["hit"]][:3]
                    if misses:
                        telegram_msg += f"\n❌ *Top Misses:*\n"
                        for miss in misses:
                            direction_symbol = "H" if miss["direction"].lower() == "higher" else "L"
                            telegram_msg += (
                                f"• {miss['player']} {miss['stat'].upper()} {miss['line']}{direction_symbol} "
                                f"({miss['predicted']:.0f}% → {miss['actual']:.1f})\n"
                            )
                
                telegram_send(telegram_msg)
                if verbose:
                    print("📱 Telegram notification sent\n")
            except Exception as e:
                if verbose:
                    print(f"⚠️  Telegram notification failed: {e}\n")
    
    if failed_count > 0:
        print(f"⚠️  Failed to update {failed_count} picks\n")
    
    return updated_count, failed_count


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-resolve NBA picks from NBA API")
    parser.add_argument("--days", type=int, default=7, help="Days back to check (default: 7)")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress messages")
    
    args = parser.parse_args()
    
    auto_resolve_nba_picks(days_back=args.days, verbose=not args.quiet)
