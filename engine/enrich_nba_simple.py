"""
NBA usage/minutes enrichment with real NBA API data.

Fetches actual usage% and minutes from NBA API when available,
falls back to stat-type estimates if API fails or player not found.
"""

from typing import Dict, List, Optional
import time

# Cache for NBA API results (avoid repeated calls)
_nba_stats_cache = {}
_nba_api_failures = 0
_nba_api_disabled = False

# LeagueDashPlayerStats returns all players; fetch once and reuse.
_league_dash_df = None
_league_dash_last_fetch = 0.0
_league_dash_ttl_seconds = 60 * 60  # 1 hour


def _nba_api_timeout_seconds(default: int = 10) -> int:
    """Best-effort timeout for nba_api calls.

    nba_api endpoints accept a `timeout` kwarg (seconds). Keeping this low prevents
    full-slate analysis from hanging when stats.nba.com is slow or blocked.
    """
    try:
        import os

        raw = os.getenv("NBA_API_TIMEOUT_SECONDS", "").strip()
        if raw:
            v = int(float(raw))
            return max(3, min(30, v))
    except Exception:
        pass
    return default


def get_real_nba_stats(player_name: str) -> Optional[Dict]:
    """
    Fetch real usage% and minutes from NBA API.
    
    Returns dict with:
        - usage_rate: actual usage % from current season
        - minutes_avg: actual minutes per game
        - minutes_std: estimated std (15% of avg)
        - position: player position (G, F, C, G-F, F-C, etc.)
        - specialist_flags: list of stat specializations (REB_SPECIALIST, 3PM_SPECIALIST, etc.)
        - shooting_profile: estimated shooting style for 3PM specialist classification
    """
    global _nba_api_failures, _nba_api_disabled
    
    # If NBA API is disabled due to too many failures, skip immediately
    if _nba_api_disabled:
        return None
    
    # Check cache first
    if player_name in _nba_stats_cache:
        return _nba_stats_cache[player_name]
    
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats

        global _league_dash_df, _league_dash_last_fetch

        # Fetch league-wide player stats once per run (or reuse recent cache).
        # If this fetch fails, disable NBA API enrichment for the remainder of the run
        # to avoid N players × retry latency.
        now = time.time()
        if _league_dash_df is None or (now - float(_league_dash_last_fetch)) > float(_league_dash_ttl_seconds):
            try:
                stats = leaguedashplayerstats.LeagueDashPlayerStats(
                    season="2025-26",
                    per_mode_detailed="PerGame",
                    timeout=_nba_api_timeout_seconds(10),
                )
                _league_dash_df = stats.get_data_frames()[0]
                _league_dash_last_fetch = now
            except Exception:
                _nba_api_failures += 1
                _nba_api_disabled = True
                print("[!] NBA API unavailable (LeagueDashPlayerStats) - using fallback estimates")
                _nba_stats_cache[player_name] = None
                return None

        df = _league_dash_df
        if df is None or getattr(df, "empty", False):
            _nba_stats_cache[player_name] = None
            return None
        
        # Find player (case-insensitive partial match)
        player_row = df[df['PLAYER_NAME'].str.contains(player_name, case=False, na=False)]
        
        if player_row.empty:
            _nba_stats_cache[player_name] = None
            return None
        
        # Extract stats
        usage_pct = player_row['USG_PCT'].values[0] if 'USG_PCT' in player_row.columns else None
        minutes = player_row['MIN'].values[0] if 'MIN' in player_row.columns else None
        
        if usage_pct is None or minutes is None:
            _nba_stats_cache[player_name] = None
            return None
        
        # Get position (important for BIG_MAN_3PM detection)
        position = ""
        if 'TEAM_ABBREVIATION' in player_row.columns:
            # Try to get position from common player data
            try:
                from nba_api.stats.endpoints import commonplayerinfo
                player_id = player_row['PLAYER_ID'].values[0]
                player_info = commonplayerinfo.CommonPlayerInfo(
                    player_id=player_id,
                    timeout=_nba_api_timeout_seconds(6),
                )
                info_df = player_info.get_data_frames()[0]
                if 'POSITION' in info_df.columns and len(info_df) > 0:
                    position = str(info_df['POSITION'].values[0]).upper()
            except Exception:
                pass
        
        # Detect stat specializations
        specialist_flags = []
        
        # Rebound specialist: >= 8.0 RPG
        reb = player_row['REB'].values[0] if 'REB' in player_row.columns else 0
        if reb >= 8.0:
            specialist_flags.append('REB_SPECIALIST')
        
        # 3PM specialist: >= 2.5 3PM per game
        threes = player_row['FG3M'].values[0] if 'FG3M' in player_row.columns else 0
        threes_attempted = player_row['FG3A'].values[0] if 'FG3A' in player_row.columns else 0
        if threes >= 2.5:
            specialist_flags.append('3PM_SPECIALIST')
        
        # BIG_MAN_3PM: Center/PF with >= 2.5 3PA (stretch bigs)
        is_big = position in ('C', 'PF', 'C-F', 'F-C', 'CENTER', 'POWER FORWARD')
        if is_big and threes_attempted >= 2.5:
            specialist_flags.append('BIG_MAN_3PM')
        
        # Steal specialist: >= 1.5 STL per game
        steals = player_row['STL'].values[0] if 'STL' in player_row.columns else 0
        if steals >= 1.5:
            specialist_flags.append('STL_SPECIALIST')
        
        # Block specialist: >= 1.0 BLK per game
        blocks = player_row['BLK'].values[0] if 'BLK' in player_row.columns else 0
        if blocks >= 1.0:
            specialist_flags.append('BLK_SPECIALIST')
        
        # FG Made specialist: >= 9.0 FGM per game (high volume scorers)
        fgm = player_row['FGM'].values[0] if 'FGM' in player_row.columns else 0
        if fgm >= 9.0:
            specialist_flags.append('FGM_SPECIALIST')
        
        # Assist specialist: >= 7.0 APG
        assists = player_row['AST'].values[0] if 'AST' in player_row.columns else 0
        if assists >= 7.0:
            specialist_flags.append('AST_SPECIALIST')
        
        # Estimate shooting profile for 3PM classification
        # This helps stat_specialist_engine make better decisions
        shooting_profile = {}
        if threes_attempted > 0:
            shooting_profile['avg_3pa'] = float(threes_attempted)
            shooting_profile['avg_3pm'] = float(threes)
            # Estimate pick_and_pop_rate for bigs (heuristic: bigs with high 3PA tend to be P&P)
            if is_big:
                # Rough estimate: 25-40% pick_and_pop for stretch bigs
                shooting_profile['pick_and_pop_rate'] = 0.30 if threes_attempted >= 4 else 0.25
            # Estimate assisted rate for role players vs self-creators
            # High usage = self-creator, low usage = catch-and-shoot
            if usage_pct:
                if usage_pct < 20:
                    shooting_profile['assisted_3pa_rate'] = 0.75  # Likely catch-and-shoot
                    shooting_profile['pullup_3pa_rate'] = 0.15
                elif usage_pct < 25:
                    shooting_profile['assisted_3pa_rate'] = 0.55
                    shooting_profile['pullup_3pa_rate'] = 0.30
                else:
                    shooting_profile['assisted_3pa_rate'] = 0.35  # Self-creator
                    shooting_profile['pullup_3pa_rate'] = 0.50
        
        result = {
            'usage_rate': float(usage_pct),
            'minutes_avg': float(minutes),
            'minutes_std': float(minutes) * 0.15,  # Estimate CV
            'position': position,
            'specialist_flags': specialist_flags,
            'shooting_profile': shooting_profile,
            'stats': {
                'reb': float(reb),
                'fg3m': float(threes),
                'fg3a': float(threes_attempted),
                'stl': float(steals),
                'blk': float(blocks),
                'fgm': float(fgm),
                'ast': float(assists)
            }
        }
        
        _nba_stats_cache[player_name] = result
        return result
        
    except Exception as e:
        _nba_api_failures += 1
        
        # Disable NBA API after 5 consecutive failures to avoid cascade timeouts
        if _nba_api_failures >= 5:
            _nba_api_disabled = True
            print(f"[!] NBA API disabled after {_nba_api_failures} failures - using fallback estimates")
        
        # API failed - cache None to avoid retrying
        _nba_stats_cache[player_name] = None
        return None


def estimate_usage_from_stat(stat: str) -> float:
    """Fallback: estimate usage from stat type"""
    if stat in ["points", "pts", "scoring"]:
        return 25.0
    elif stat in ["pts+reb+ast", "pra", "pts+reb", "pts+ast"]:
        return 26.0
    elif stat in ["assists", "ast"]:
        return 24.0
    elif stat in ["rebounds", "reb", "rebounding"]:
        return 20.0
    elif stat in ["3-pointers", "3pm", "threes"]:
        return 23.0
    elif stat in ["blocks", "blk", "steals", "stl"]:
        return 19.0
    else:
        return 22.0  # Default


def estimate_minutes_from_stat(stat: str) -> float:
    """Fallback: estimate minutes from stat type"""
    if stat in ["points", "pts", "scoring"]:
        return 30.0
    elif stat in ["pts+reb+ast", "pra", "pts+reb", "pts+ast"]:
        return 32.0
    elif stat in ["assists", "ast"]:
        return 30.0
    elif stat in ["rebounds", "reb", "rebounding"]:
        return 28.0
    elif stat in ["3-pointers", "3pm", "threes"]:
        return 29.0
    elif stat in ["blocks", "blk", "steals", "stl"]:
        return 26.0
    else:
        return 28.0  # Default


def enrich_nba_usage_minutes_simple(props: List[Dict]) -> List[Dict]:
    """
    Add usage_rate and minutes_projected to NBA props.
    
    Tries to fetch real NBA API data first, falls back to estimates if unavailable.
    
    Args:
        props: List of prop dicts with player, stat, team
    
    Returns:
        Props with added usage_rate, minutes_projected fields
    """
    enriched = []
    api_success_count = 0
    fallback_count = 0
    
    for prop in props:
        enriched_prop = prop.copy()
        
        # Skip if already has usage/minutes
        if "usage_rate" in prop or "minutes_projected" in prop:
            enriched.append(enriched_prop)
            continue
        
        stat = prop.get("stat", "")
        player = prop.get("player", "")
        
        # Try to get real NBA API data
        real_stats = get_real_nba_stats(player)
        
        if real_stats:
            # Use real data from NBA API
            enriched_prop["usage_rate"] = real_stats['usage_rate']
            enriched_prop["minutes_projected"] = real_stats['minutes_avg']
            enriched_prop["minutes_std_estimate"] = real_stats['minutes_std']
            enriched_prop["data_source"] = "nba_api"
            enriched_prop["specialist_flags"] = real_stats.get('specialist_flags', [])
            enriched_prop["stat_averages"] = real_stats.get('stats', {})
            
            # Position for BIG_MAN_3PM detection
            if real_stats.get('position'):
                enriched_prop["position"] = real_stats['position']
            
            # Shooting profile for specialist classification
            shooting_profile = real_stats.get('shooting_profile', {})
            if shooting_profile:
                enriched_prop["avg_3pa"] = shooting_profile.get('avg_3pa')
                enriched_prop["avg_3pm"] = shooting_profile.get('avg_3pm')
                enriched_prop["pick_and_pop_rate"] = shooting_profile.get('pick_and_pop_rate')
                enriched_prop["assisted_3pa_rate"] = shooting_profile.get('assisted_3pa_rate')
                enriched_prop["pullup_3pa_rate"] = shooting_profile.get('pullup_3pa_rate')
            
            api_success_count += 1
        else:
            # Fall back to stat-type estimates
            usage_estimate = estimate_usage_from_stat(stat)
            minutes_estimate = estimate_minutes_from_stat(stat)
            
            # Adjust for known players (manual overrides)
            stars = ["Luka Doncic", "LeBron James", "Kevin Durant", "Stephen Curry", 
                     "Giannis Antetokounmpo", "Joel Embiid", "Nikola Jokic", "Damian Lillard",
                     "Jayson Tatum", "Devin Booker", "Shai Gilgeous-Alexander", "Anthony Edwards",
                     "Tyrese Maxey", "LaMelo Ball", "Tyrese Haliburton"]
            if player in stars:
                usage_estimate = 30.0
                minutes_estimate = 35.0
            
            # Common bench scorers (high usage but low minutes)
            bench_scorers = ["Jordan Clarkson", "CJ McCollum", "Malik Monk", "Immanuel Quickley"]
            if player in bench_scorers:
                usage_estimate = 26.0
                minutes_estimate = 24.0
            
            enriched_prop["usage_rate"] = usage_estimate
            enriched_prop["minutes_projected"] = minutes_estimate
            enriched_prop["data_source"] = "estimate"
            fallback_count += 1
        
        enriched.append(enriched_prop)
        
        # Small delay to avoid API rate limits (every 10 calls)
        if api_success_count > 0 and api_success_count % 10 == 0:
            time.sleep(0.5)
    
    # Print summary
    if api_success_count > 0:
        print(f"   NBA API: {api_success_count} players | Estimates: {fallback_count} players")
    
    return enriched
