"""
TENNIS PLAYER PROFILER
Extracts real historical stats from Tennis Abstract database for Monte Carlo simulation

Bridges: tennis_stats.db → Monte Carlo Engine (with JSON fallback for ITF players)

SOP v2.1 Compliant - Data-Driven Calibration
"""

import sqlite3
import math
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

# GOVERNANCE: never hardcode tier thresholds; import canonical thresholds.
try:
    from config.thresholds import implied_tier
except Exception:  # pragma: no cover
    implied_tier = None  # type: ignore

# Optional: physics-style match simulator for opponent-aware props.
try:
    from tennis.engines.physics.match_simulator import simulate_match_best_of_3
    from tennis.engines.physics.params import derive_point_params
    from tennis.engines.physics.poisson import poisson
except Exception:  # pragma: no cover
    simulate_match_best_of_3 = None  # type: ignore
    derive_point_params = None  # type: ignore
    poisson = None  # type: ignore

try:
    from tennis.injury_gate import apply_injury_adjustment
except Exception:  # pragma: no cover
    apply_injury_adjustment = None  # type: ignore


# ============================================================================
# NAME ALIASES: Map Underdog spellings → Sackmann spellings
# ============================================================================
NAME_ALIASES = {
    "xinyu wang": "xin yu wang",
    "xinyu": "xin yu",
    # Add more as discovered
}


# ============================================================================
# SECTION 1: PLAYER PROFILE DATACLASS
# ============================================================================

@dataclass
class TennisPlayerProfile:
    """
    Player profile for Monte Carlo simulation.
    All stats derived from real historical data.
    """
    player_name: str
    
    # Sample size
    n_matches: int = 0
    n_wins: int = 0
    
    # Serve stats (per match averages)
    avg_aces: float = 0.0
    std_aces: float = 0.0
    avg_double_faults: float = 0.0
    std_double_faults: float = 0.0
    
    # Service game stats
    avg_service_games: float = 0.0
    serve_hold_rate: float = 0.65  # Default
    
    # Break point stats
    avg_bp_faced: float = 0.0
    bp_save_rate: float = 0.60  # Default
    
    # Games won
    avg_games_won: float = 0.0
    std_games_won: float = 0.0
    
    # Win rate
    win_rate: float = 0.50
    
    # Surface splits
    hard_win_rate: float = 0.50
    clay_win_rate: float = 0.50
    grass_win_rate: float = 0.50
    
    # Surface-specific aces
    hard_avg_aces: float = 0.0
    clay_avg_aces: float = 0.0
    grass_avg_aces: float = 0.0
    
    # Confidence (based on sample size)
    confidence: float = 0.0
    
    # Last updated
    as_of_date: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON/display"""
        return {
            'player_name': self.player_name,
            'n_matches': self.n_matches,
            'win_rate': f"{self.win_rate:.1%}",
            'avg_aces': f"{self.avg_aces:.1f} ± {self.std_aces:.1f}",
            'avg_df': f"{self.avg_double_faults:.1f}",
            'serve_hold': f"{self.serve_hold_rate:.1%}",
            'bp_save': f"{self.bp_save_rate:.1%}",
            'avg_games_won': f"{self.avg_games_won:.1f} ± {self.std_games_won:.1f}",
            'confidence': f"{self.confidence:.0%}",
        }


# ============================================================================
# SECTION 2: PROFILER CLASS
# ============================================================================

class TennisPlayerProfiler:
    """
    Extracts player profiles from Tennis Abstract database.
    Falls back to JSON stats file for ITF/Qualifier players without detailed stats.
    
    Usage:
        profiler = TennisPlayerProfiler()
        profile = profiler.get_profile("Carlos Alcaraz")
        print(profile.avg_aces, profile.std_aces)
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent / "data" / "tennis_stats.db"
        
        self.db_path = str(db_path)
        self.conn = None
        self._connect()
        
        # Profile cache
        self._cache: Dict[str, TennisPlayerProfile] = {}
        
        # Load JSON stats for fallback (ITF players)
        self._json_stats = self._load_json_stats()
    
    def _load_json_stats(self) -> Dict:
        """Load player_stats.json for ITF player fallback"""
        json_path = Path(__file__).parent / "data" / "player_stats.json"
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Could not load player_stats.json: {e}")
        return {}
    
    def _normalize_name(self, name: str) -> str:
        """Normalize player name for lookup — handles Underdog truncation & junk"""
        import re
        cleaned = name.strip()
        # Strip ellipsis characters (Underdog UI truncation)
        cleaned = cleaned.replace('…', '').replace('...', '').strip()
        # Strip schedule/time suffixes like " - Thu 5:00AM CST"
        cleaned = re.sub(r'\s*-\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b.*$', '', cleaned, flags=re.IGNORECASE).strip()
        # Strip standalone time patterns like "10:30AM CST" at end
        cleaned = re.sub(r'\s+\d{1,2}:\d{2}\s*(AM|PM|am|pm)?\s*(CST|EST|PST|MST|CT|ET|PT)?\s*$', '', cleaned).strip()
        name_lower = cleaned.lower()
        # Check aliases
        if name_lower in NAME_ALIASES:
            name_lower = NAME_ALIASES[name_lower]
        return name_lower
    
    def _get_json_profile(self, player_name: str, surface: str = None) -> Optional[TennisPlayerProfile]:
        """
        Fallback: Create profile from JSON stats (ITF/Qualifier players)
        """
        normalized = self._normalize_name(player_name)
        
        # Direct lookup
        stats = self._json_stats.get(normalized)
        
        # Fuzzy search if not found
        if not stats:
            for key, val in self._json_stats.items():
                if normalized in key or key in normalized:
                    stats = val
                    break
        
        if not stats:
            return None
        
        # Extract stats from JSON
        overall_win_rate = stats.get('win_pct_L10', 0.5)
        n_matches = stats.get('matches_analyzed', 0)
        ace_pct = stats.get('ace_pct_L10', 0.028)  # Tour avg ~2.8%
        fs_pct = stats.get('first_serve_pct_L10', 0.60)
        
        # Surface-specific win rate (with sanity check)
        win_rate = overall_win_rate
        surface_form = stats.get('surface_form_L10', {})
        if surface and surface.upper() in surface_form:
            surface_wr = surface_form[surface.upper()]
            # Only use surface-specific if it's reasonable (not 0% or 100% from tiny sample)
            # Blend with overall when extreme
            if 0.10 < surface_wr < 0.90:
                win_rate = surface_wr
            else:
                # Blend: 70% overall + 30% surface (dampen extreme values)
                win_rate = 0.7 * overall_win_rate + 0.3 * surface_wr
        
        # Estimate aces based on ace% (assume ~60 serve points per match)
        estimated_serve_points = 60
        avg_aces = ace_pct * estimated_serve_points if ace_pct else 3.0
        
        profile = TennisPlayerProfile(
            player_name=stats.get('name', player_name),
            n_matches=n_matches,
            n_wins=int(n_matches * win_rate),
            win_rate=win_rate,
            # Estimated serve stats from ace%
            avg_aces=avg_aces,
            std_aces=avg_aces * 0.6,  # ~60% variance typical
            avg_double_faults=2.5,  # Tour average
            std_double_faults=1.5,
            avg_service_games=10.0,
            serve_hold_rate=0.55 + (win_rate * 0.20),  # Correlated with win rate
            avg_bp_faced=4.0,
            bp_save_rate=0.55 + (win_rate * 0.15),
            avg_games_won=12.0 if win_rate > 0.5 else 9.0,
            std_games_won=4.0,
            confidence=min(0.6, n_matches / 20),  # Lower confidence for ITF
            as_of_date=stats.get('stats_updated', datetime.now().strftime("%Y-%m-%d"))
        )
        
        return profile
    
    def _connect(self):
        """Connect to database"""
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    def get_profile(
        self, 
        player_name: str, 
        surface: str = None,
        n_matches: int = None
    ) -> Optional[TennisPlayerProfile]:
        """
        Get player profile from database.
        Falls back to JSON stats for ITF/Qualifier players.
        
        Args:
            player_name: Player name (fuzzy match)
            surface: Filter by surface ('Hard', 'Clay', 'Grass')
            n_matches: Limit to last N matches
        
        Returns:
            TennisPlayerProfile or None if not found
        """
        # Normalize name (handle aliases like "Xinyu Wang" → "Xin Yu Wang")
        normalized_name = self._normalize_name(player_name)
        
        # Check cache
        cache_key = f"{normalized_name}_{surface}_{n_matches}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        cursor = self.conn.cursor()
        
        # Find player - try both original and normalized
        search_names = [player_name, normalized_name] if normalized_name != player_name.lower().strip() else [player_name]
        player_row = None
        
        for search_name in search_names:
            cursor.execute(
                "SELECT player_id, player_name FROM players WHERE player_name LIKE ?",
                (f"%{search_name}%",)
            )
            rows = cursor.fetchall()
            if rows:
                if len(rows) == 1:
                    player_row = rows[0]
                else:
                    # Multiple matches (e.g. "Tsitsipas" → Pavlos, Petros, Stefanos)
                    # Prefer the player with the most match_stats (most data)
                    best_row, best_n = None, -1
                    for r in rows:
                        cursor.execute("SELECT COUNT(*) FROM match_stats WHERE player_id=?", (r['player_id'],))
                        n = cursor.fetchone()[0]
                        if n > best_n:
                            best_n = n
                            best_row = r
                    player_row = best_row
                break
        
        if not player_row:
            # Try JSON fallback for ITF players (use cleaned name)
            display_name = normalized_name.title() if normalized_name != player_name.lower().strip() else player_name
            json_profile = self._get_json_profile(normalized_name, surface)
            if not json_profile:
                # Also try the original name (may have different casing)
                json_profile = self._get_json_profile(player_name, surface)
            if json_profile:
                warn_key = f"_json_fallback_{normalized_name}"
                if warn_key not in self._cache:
                    print(f"📊 {display_name}: Using JSON stats (ITF/Qualifier data)")
                    self._cache[warn_key] = True
                self._cache[cache_key] = json_profile
                return json_profile
            
            # Only warn once per player (track in cache)
            warn_key = f"_warned_{normalized_name}"
            if warn_key not in self._cache:
                print(f"⚠️ Player not found: {display_name}")
                self._cache[warn_key] = True
            return None
        
        player_id = player_row['player_id']
        actual_name = player_row['player_name']
        
        # Build query
        surface_filter = ""
        params = [player_id]
        
        if surface:
            surface_filter = "AND m.surface = ?"
            params.append(surface)
        
        limit_clause = ""
        if n_matches:
            limit_clause = f"LIMIT {n_matches}"
        
        # Get stats
        query = f"""
            SELECT 
                ms.aces,
                ms.double_faults,
                ms.service_games_played,
                ms.service_games_won,
                ms.break_points_faced,
                ms.break_points_saved,
                ms.total_games_won,
                m.surface,
                CASE WHEN m.winner_id = ? THEN 1 ELSE 0 END as won
            FROM match_stats ms
            JOIN matches m ON ms.match_id = m.match_id
            WHERE ms.player_id = ?
            {surface_filter}
            ORDER BY m.match_date DESC
            {limit_clause}
        """
        
        cursor.execute(query, [player_id, player_id] + params[1:])
        rows = cursor.fetchall()
        
        if not rows and surface:
            # No matches for requested surface - try all surfaces as fallback
            warn_key = f"_warned_surface_{actual_name}_{surface}"
            if warn_key not in self._cache:
                # Check what surfaces they have data for
                cursor.execute("""
                    SELECT DISTINCT m.surface, COUNT(*) as cnt
                    FROM match_stats ms
                    JOIN matches m ON ms.match_id = m.match_id
                    WHERE ms.player_id = ?
                    GROUP BY m.surface
                """, [player_id])
                available = cursor.fetchall()
                if available:
                    surfaces_str = ", ".join(f"{s[0]}({s[1]})" for s in available)
                    print(f"⚠️ {actual_name}: No {surface} data, has: {surfaces_str} - using all surfaces")
                self._cache[warn_key] = True
            
            # Retry without surface filter
            query_all = f"""
                SELECT 
                    ms.aces,
                    ms.double_faults,
                    ms.service_games_played,
                    ms.service_games_won,
                    ms.break_points_faced,
                    ms.break_points_saved,
                    ms.total_games_won,
                    m.surface,
                    CASE WHEN m.winner_id = ? THEN 1 ELSE 0 END as won
                FROM match_stats ms
                JOIN matches m ON ms.match_id = m.match_id
                WHERE ms.player_id = ?
                ORDER BY m.match_date DESC
                {limit_clause}
            """
            cursor.execute(query_all, [player_id, player_id])
            rows = cursor.fetchall()
        
        if not rows:
            # Try fallback: Get basic match data without detailed stats
            # This handles Challenger/Futures/ITF players who have matches but no serve stats
            
            # First try JSON stats (may have better L10 data)
            json_profile = self._get_json_profile(actual_name, surface)
            if json_profile:
                warn_key = f"_json_nostats_{actual_name}"
                if warn_key not in self._cache:
                    print(f"📊 {actual_name}: Using JSON stats (no detailed match stats in DB)")
                    self._cache[warn_key] = True
                self._cache[cache_key] = json_profile
                return json_profile
            
            warn_key = f"_warned_nodata_{actual_name}"
            if warn_key not in self._cache:
                print(f"⚠️ No match data for: {actual_name}")
                self._cache[warn_key] = True
            
            # Check if they have matches at all
            cursor.execute("""
                SELECT COUNT(*) as n, 
                       SUM(CASE WHEN winner_id = ? THEN 1 ELSE 0 END) as wins
                FROM matches
                WHERE player1_id = ? OR player2_id = ?
            """, [player_id, player_id, player_id])
            basic = cursor.fetchone()
            
            if basic and basic['n'] > 0:
                # Create minimal profile based on win rate
                n_matches = basic['n']
                n_wins = basic['wins'] or 0
                win_rate = n_wins / n_matches if n_matches > 0 else 0.5
                
                profile = TennisPlayerProfile(
                    player_name=actual_name,
                    n_matches=n_matches,
                    n_wins=n_wins,
                    win_rate=win_rate,
                    # Use tour averages for serve stats
                    avg_aces=4.0,  # Tour average
                    std_aces=3.0,
                    avg_double_faults=2.5,
                    std_double_faults=1.5,
                    avg_service_games=10.0,
                    serve_hold_rate=0.65,
                    avg_bp_faced=4.0,
                    bp_save_rate=0.60,
                    avg_games_won=12.0 if win_rate > 0.5 else 8.0,
                    std_games_won=4.0,
                    confidence=0.3,  # Low confidence due to missing stats
                    as_of_date=datetime.now().strftime("%Y-%m-%d")
                )
                self._cache[cache_key] = profile
                return profile
            
            return None
        
        # Calculate stats
        profile = self._calculate_profile(actual_name, rows)
        
        # Get surface splits
        profile = self._add_surface_splits(profile, player_id, cursor)
        
        # Cache and return
        self._cache[cache_key] = profile
        return profile
    
    def _calculate_profile(
        self, 
        player_name: str, 
        rows: List[sqlite3.Row]
    ) -> TennisPlayerProfile:
        """Calculate profile from query results"""
        
        n = len(rows)
        
        # Extract values
        aces = [r['aces'] or 0 for r in rows]
        dfs = [r['double_faults'] or 0 for r in rows]
        svc_played = [r['service_games_played'] or 0 for r in rows]
        svc_won = [r['service_games_won'] or 0 for r in rows]
        bp_faced = [r['break_points_faced'] or 0 for r in rows]
        bp_saved = [r['break_points_saved'] or 0 for r in rows]
        games_won = [r['total_games_won'] or 0 for r in rows]
        wins = [r['won'] for r in rows]
        
        # Calculate means
        avg_aces = sum(aces) / n if n > 0 else 0
        avg_df = sum(dfs) / n if n > 0 else 0
        avg_svc = sum(svc_played) / n if n > 0 else 0
        avg_games = sum(games_won) / n if n > 0 else 0
        
        # Calculate std devs
        def std(vals, mean):
            if len(vals) < 2:
                return 0
            variance = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
            return math.sqrt(variance)
        
        std_aces = std(aces, avg_aces)
        std_games = std(games_won, avg_games)
        
        # Calculate rates
        total_svc_played = sum(svc_played)
        total_svc_won = sum(svc_won)
        serve_hold = total_svc_won / total_svc_played if total_svc_played > 0 else 0.65
        
        total_bp_faced = sum(bp_faced)
        total_bp_saved = sum(bp_saved)
        bp_save = total_bp_saved / total_bp_faced if total_bp_faced > 0 else 0.60
        
        win_rate = sum(wins) / n if n > 0 else 0.50
        
        # Confidence based on sample size (sigmoid)
        confidence = 1 / (1 + math.exp(-0.1 * (n - 10)))
        
        return TennisPlayerProfile(
            player_name=player_name,
            n_matches=n,
            n_wins=sum(wins),
            avg_aces=avg_aces,
            std_aces=std_aces,
            avg_double_faults=avg_df,
            std_double_faults=std(dfs, avg_df),
            avg_service_games=avg_svc,
            serve_hold_rate=serve_hold,
            avg_bp_faced=sum(bp_faced) / n if n > 0 else 0,
            bp_save_rate=bp_save,
            avg_games_won=avg_games,
            std_games_won=std_games,
            win_rate=win_rate,
            confidence=confidence,
            as_of_date=datetime.now().strftime('%Y-%m-%d')
        )
    
    def _add_surface_splits(
        self, 
        profile: TennisPlayerProfile, 
        player_id: int,
        cursor
    ) -> TennisPlayerProfile:
        """Add surface-specific stats to profile"""
        
        for surface in ['Hard', 'Clay', 'Grass']:
            cursor.execute("""
                SELECT 
                    COUNT(*) as n,
                    SUM(CASE WHEN m.winner_id = ? THEN 1 ELSE 0 END) as wins,
                    AVG(ms.aces) as avg_aces
                FROM match_stats ms
                JOIN matches m ON ms.match_id = m.match_id
                WHERE ms.player_id = ? AND m.surface = ?
            """, (player_id, player_id, surface))
            
            row = cursor.fetchone()
            
            if row and row['n'] > 0:
                win_rate = row['wins'] / row['n']
                avg_aces = row['avg_aces'] or 0
                
                if surface == 'Hard':
                    profile.hard_win_rate = win_rate
                    profile.hard_avg_aces = avg_aces
                elif surface == 'Clay':
                    profile.clay_win_rate = win_rate
                    profile.clay_avg_aces = avg_aces
                elif surface == 'Grass':
                    profile.grass_win_rate = win_rate
                    profile.grass_avg_aces = avg_aces
        
        return profile
    
    def get_head_to_head(self, player1: str, player2: str) -> Dict:
        """Get head-to-head record between two players"""
        cursor = self.conn.cursor()
        
        # Find player IDs
        cursor.execute(
            "SELECT player_id, player_name FROM players WHERE player_name LIKE ?",
            (f"%{player1}%",)
        )
        p1 = cursor.fetchone()
        
        cursor.execute(
            "SELECT player_id, player_name FROM players WHERE player_name LIKE ?",
            (f"%{player2}%",)
        )
        p2 = cursor.fetchone()
        
        if not p1 or not p2:
            return {'matches': 0, 'p1_wins': 0, 'p2_wins': 0}
        
        # Find H2H matches
        cursor.execute("""
            SELECT 
                m.match_date,
                m.tournament_name,
                m.surface,
                m.score,
                m.winner_id
            FROM matches m
            WHERE (m.player1_id = ? AND m.player2_id = ?)
               OR (m.player1_id = ? AND m.player2_id = ?)
            ORDER BY m.match_date DESC
        """, (p1['player_id'], p2['player_id'], p2['player_id'], p1['player_id']))
        
        matches = cursor.fetchall()
        
        p1_wins = sum(1 for m in matches if m['winner_id'] == p1['player_id'])
        p2_wins = len(matches) - p1_wins
        
        return {
            'player1': p1['player_name'],
            'player2': p2['player_name'],
            'matches': len(matches),
            'p1_wins': p1_wins,
            'p2_wins': p2_wins,
            'history': [dict(m) for m in matches]
        }
    
    def compare_players(self, player1: str, player2: str) -> Dict:
        """Compare two players side-by-side"""
        p1 = self.get_profile(player1)
        p2 = self.get_profile(player2)
        
        if not p1 or not p2:
            return None
        
        h2h = self.get_head_to_head(player1, player2)
        
        return {
            'player1': p1.to_dict(),
            'player2': p2.to_dict(),
            'head_to_head': h2h,
            'comparison': {
                'aces_edge': p1.player_name if p1.avg_aces > p2.avg_aces else p2.player_name,
                'serve_edge': p1.player_name if p1.serve_hold_rate > p2.serve_hold_rate else p2.player_name,
                'bp_save_edge': p1.player_name if p1.bp_save_rate > p2.bp_save_rate else p2.player_name,
                'win_rate_edge': p1.player_name if p1.win_rate > p2.win_rate else p2.player_name,
            }
        }


# ============================================================================
# SECTION 3: MONTE CARLO INTEGRATION
# ============================================================================

class CalibratedTennisMC:
    """
    Monte Carlo simulation using real player profiles.
    
    Key improvement over generic MC:
    - Uses actual player ace rates, DF rates, serve hold rates
    - Uses historical variance for confidence calculation
    - Surface-specific adjustments
    """
    
    N_SIMULATIONS = 2000
    
    # Optional player_stats.json (used elsewhere in tennis module) can provide
    # per-surface return points won. We use it as a light opponent signal.
    _PLAYER_STATS_CACHE: Optional[Dict] = None

    def __init__(self, profiler: TennisPlayerProfiler = None, mode: Optional[str] = None):
        self.profiler = profiler or TennisPlayerProfiler()
        self.mode = (mode or os.getenv("TENNIS_PROP_MC_MODE", "hybrid")).strip().lower()
        import random as _random
        self._rng = _random.Random()
    
    def simulate_prop(
        self,
        player_name: str,
        stat_type: str,
        line: float,
        direction: str,
        opponent: str = None,
        surface: str = "Hard"
    ) -> Dict:
        """
        Simulate a prop using real player data.
        
        Args:
            player_name: Player name
            stat_type: 'aces', 'games_won', 'double_faults', etc.
            line: Betting line
            direction: 'HIGHER' or 'LOWER'
            opponent: Optional opponent name
            surface: Court surface
        
        Returns:
            Dict with probability, confidence, tier
        """
        # Get player profile
        profile = self.profiler.get_profile(player_name, surface=surface)
        
        if not profile:
            return {
                'error': f'Player not found: {player_name}',
                'probability': 0.50,
                'confidence': 0.0,
                'tier': 'NO_PLAY'
            }
        
        # Get opponent profile for adjustment
        opp_profile = None
        if opponent:
            opp_profile = self.profiler.get_profile(opponent, surface=surface)

        # Hard gate: in strict physics mode, we require opponent context.
        if self.mode == "physics":
            if not opponent:
                return {
                    'error': 'Physics mode requires opponent name',
                    'probability': 0.50,
                    'confidence': 0.0,
                    'tier': 'NO_PLAY'
                }
            if not opp_profile:
                return {
                    'error': f'Opponent not found: {opponent}',
                    'probability': 0.50,
                    'confidence': 0.0,
                    'tier': 'NO_PLAY'
                }
        
        # Choose backend (physics-style match simulation when possible)
        stat_norm = (stat_type or "").lower().strip().replace(" ", "_")
        use_physics = (
            self.mode in ("physics", "hybrid")
            and opp_profile is not None
            and simulate_match_best_of_3 is not None
            and derive_point_params is not None
            and self._physics_supports(stat_norm)
        )

        # Run simulation
        hits = 0
        results = []
        
        for _ in range(self.N_SIMULATIONS):
            if use_physics:
                value = self._simulate_stat_physics(profile, stat_norm, surface, opp_profile)
            else:
                value = self._simulate_stat(profile, stat_type, surface, opp_profile)
            results.append(value)
            
            if direction.upper() == 'HIGHER':
                if value > line:
                    hits += 1
            else:
                if value < line:
                    hits += 1
        
        # Calculate probability
        probability = hits / self.N_SIMULATIONS

        # Injury adjustment (shrinks toward 50% if returning from injury)
        injury_details = {}
        if apply_injury_adjustment is not None:
            try:
                probability, injury_details = apply_injury_adjustment(
                    probability,
                    player_name=profile.player_name,
                    opponent_name=opp_profile.player_name if opp_profile else None,
                )
            except Exception:
                injury_details = {}
        
        # Calculate simulation stats
        import statistics as stats
        sim_mean = stats.mean(results)
        sim_std = stats.stdev(results) if len(results) > 1 else 0
        
        # Confidence calculation (SOP v2.1 compliant)
        # Raw probability → edge percentage
        CAPS = {
            'aces': 70,
            'double_faults': 65,
            'games_won': 72,
            'sets_won': 68,
            'games_played': 70,
            'total_games': 70,
            'fantasy_score': 65,  # High variance stat
            'breakpoints_won': 62,  # Very volatile
            'break_points_won': 62,
        }
        cap = CAPS.get(stat_type.lower(), 70)
        
        # Edge is how much the probability exceeds 50%
        # e.g., 65% prob → 15% edge → 65 confidence score
        raw_confidence = probability * 100
        
        # Apply data quality factor (more matches = higher confidence)
        # But don't destroy the raw probability
        data_quality_factor = min(1.0, profile.n_matches / 25)  # Max at 25 matches
        
        # Confidence = raw probability (capped) * data quality
        confidence = min(raw_confidence, cap) * (0.85 + 0.15 * data_quality_factor)
        
        # Assign tier based on RAW probability (not confidence score)
        # GOVERNANCE: tiers are derived from config/thresholds.py (single source of truth).
        if implied_tier is not None:
            tier = implied_tier(probability, "TENNIS")
            # Local UX uses NO_PLAY bucket for anything below LEAN.
            if tier == "AVOID":
                tier = "NO_PLAY"
        else:
            # Conservative fallback if thresholds module isn't available.
            tier = "NO_PLAY"
        
        # Apply stat-specific cap (some stats can't be SLAM)
        if stat_type.lower() in ['double_faults', 'tiebreakers'] and tier == 'SLAM':
            tier = 'STRONG'  # These stats too volatile for SLAM
        
        # ── CONTEXT ENRICHMENT ──────────────────────────────────────
        # Attach opponent, H2H, ranking, serve/return stats, narrative
        # so downstream (reports, Telegram, AI) has full match context.
        match_context = None
        try:
            from tennis.player_context_memory import MatchContextBuilder
            ctx_builder = MatchContextBuilder(
                profiler=self.profiler,
            )
            match_context = ctx_builder.build_match_context(
                player_name=profile.player_name,
                opponent_name=opp_profile.player_name if opp_profile else (opponent or None),
                surface=surface,
                player_profile=profile,
                opponent_profile=opp_profile,
            ).to_dict()
        except Exception:
            match_context = None
        # ────────────────────────────────────────────────────────────

        return {
            'player': profile.player_name,
            'stat': stat_type,
            'line': line,
            'direction': direction,
            'probability': probability,
            'confidence': confidence,
            'tier': tier,
            'simulation': {
                'mean': sim_mean,
                'std': sim_std,
                'n': self.N_SIMULATIONS,
            },
            'physics_mode': bool(use_physics),
            'injury_gate': injury_details,
            'profile_data': {
                'n_matches': profile.n_matches,
                'historical_mean': getattr(profile, f'avg_{stat_type.lower()}', None),
                'historical_std': getattr(profile, f'std_{stat_type.lower()}', None),
            },
            'match_context': match_context,
        }

    def _physics_supports(self, stat_norm: str) -> bool:
        return stat_norm in {
            'games_won',
            'games_played',
            'total_games',
            '1st_set_games',
            '1st_set_games_won',
            'sets_won',
            'sets_played',
            'aces',
            'double_faults',
            'tiebreakers',
            'tiebreakers_played',
        }

    def _surface_norm(self, surface: str) -> str:
        s = (surface or '').strip().upper()
        if s in ('HARD', 'CLAY', 'GRASS', 'INDOOR'):
            return s
        # Common variants
        if s.startswith('INDOOR'):
            return 'INDOOR'
        return 'HARD'

    def _load_player_stats(self) -> Dict:
        if self._PLAYER_STATS_CACHE is not None:
            return self._PLAYER_STATS_CACHE
        try:
            path = Path(__file__).parent / 'player_stats.json'
            if path.exists():
                self._PLAYER_STATS_CACHE = json.loads(path.read_text(encoding='utf-8'))
            else:
                self._PLAYER_STATS_CACHE = {}
        except Exception:
            self._PLAYER_STATS_CACHE = {}
        return self._PLAYER_STATS_CACHE or {}

    def _get_return_win_pct(self, player_name: str, surface: str) -> Optional[float]:
        stats = self._load_player_stats()
        if not stats or not isinstance(stats, dict):
            return None
        # Try direct key match first; fallback to case-insensitive search.
        ps = stats.get(player_name)
        if ps is None:
            key = player_name.strip().lower()
            for k, v in stats.items():
                if isinstance(k, str) and k.strip().lower() == key:
                    ps = v
                    break
        if not isinstance(ps, dict):
            return None
        surf = self._surface_norm(surface).lower()
        return_win = ps.get(f'return_win_{surf}', ps.get('return_win'))
        try:
            if return_win is None:
                return None
            f = float(return_win)
            if 0.0 <= f <= 1.0:
                return f
        except Exception:
            return None
        return None

    def _simulate_stat_physics(
        self,
        profile: TennisPlayerProfile,
        stat_norm: str,
        surface: str,
        opponent: TennisPlayerProfile,
    ) -> float:
        r = getattr(self, "_rng", None)
        if r is None:
            import random as _random
            r = _random.Random()

        # Derive point-level parameters (opponent-aware if return stats available).
        a_ret = self._get_return_win_pct(profile.player_name, surface)
        b_ret = self._get_return_win_pct(opponent.player_name, surface)

        params = derive_point_params(
            a_hold=profile.serve_hold_rate,
            b_hold=opponent.serve_hold_rate,
            a_return_win=a_ret,
            b_return_win=b_ret,
            a_strength=profile.win_rate,
            b_strength=opponent.win_rate,
        )

        sample = simulate_match_best_of_3(
            params.pA_srv_point,
            params.pB_srv_point,
            rng=r,
        )

        # Match-derived stats
        if stat_norm in ('games_played', 'total_games'):
            return float(sample.total_games)
        if stat_norm == 'games_won':
            return float(sample.games_a)
        if stat_norm == 'sets_won':
            return float(sample.sets_a)
        if stat_norm in ('sets_played', 'total_sets'):
            return float(sample.sets_a + sample.sets_b)
        if stat_norm == '1st_set_games':
            return float(sample.first_set_total_games)
        if stat_norm == '1st_set_games_won':
            return float(sample.first_set_games_a)
        if stat_norm in ('tiebreakers', 'tiebreakers_played'):
            return float(1 if sample.had_tiebreak else 0)

        # Serve stats scaled by service games
        surf = self._surface_norm(surface)
        ace_mult = {
            'HARD': 1.0,
            'CLAY': 0.75,
            'GRASS': 1.35,
            'INDOOR': 1.15,
        }.get(surf, 1.0)

        service_games = max(1, int(sample.service_games_a))

        # Convert per-match averages to per-service-game rates.
        denom = float(profile.avg_service_games) if profile.avg_service_games and profile.avg_service_games > 0 else 9.0
        aces_per_sg = max(0.0, float(profile.avg_aces) / denom)
        dfs_per_sg = max(0.0, float(profile.avg_double_faults) / denom)

        # Opponent return pressure (coarse): strong returners reduce aces slightly.
        if b_ret is not None and b_ret > 0.37:
            aces_per_sg *= 0.92

        if stat_norm == 'aces':
            lam = aces_per_sg * service_games * ace_mult
            return float(poisson(lam, rng=r) if poisson is not None else max(0.0, r.gauss(lam, max(1.0, lam**0.5))))

        if stat_norm == 'double_faults':
            # Clay tends to slightly reduce DF via slower pace; keep adjustment mild.
            df_mult = 0.95 if surf == 'CLAY' else 1.0
            lam = dfs_per_sg * service_games * df_mult
            return float(poisson(lam, rng=r) if poisson is not None else max(0.0, r.gauss(lam, max(1.0, lam**0.5))))

        # Fallback: no-op
        return 0.0
    
    def _simulate_stat(
        self, 
        profile: TennisPlayerProfile, 
        stat_type: str,
        surface: str,
        opponent: TennisPlayerProfile = None
    ) -> float:
        """Simulate a single stat value"""
        import random
        
        stat_type = stat_type.lower()
        
        if stat_type == 'aces':
            # Use surface-specific if available
            if surface == 'Hard' and profile.hard_avg_aces > 0:
                mean = profile.hard_avg_aces
            elif surface == 'Clay' and profile.clay_avg_aces > 0:
                mean = profile.clay_avg_aces
            elif surface == 'Grass' and profile.grass_avg_aces > 0:
                mean = profile.grass_avg_aces
            else:
                mean = profile.avg_aces
            
            std = profile.std_aces or mean * 0.3
            
            # Opponent adjustment (better returner = fewer aces)
            if opponent and opponent.bp_save_rate < 0.55:
                mean *= 0.9  # Reduce aces vs good returners
            
            return max(0, random.gauss(mean, std))
        
        elif stat_type == 'double_faults':
            mean = profile.avg_double_faults
            std = profile.std_double_faults or mean * 0.4
            return max(0, random.gauss(mean, std))
        
        elif stat_type == 'games_won':
            mean = profile.avg_games_won
            std = profile.std_games_won or mean * 0.2
            
            # Opponent adjustment
            if opponent:
                # If opponent has higher win rate, reduce expected games
                diff = opponent.win_rate - profile.win_rate
                mean *= (1 - diff * 0.3)
            
            return max(0, random.gauss(mean, std))
        
        elif stat_type in ['sets_won', 'sets']:
            # Based on win probability
            win_prob = profile.win_rate
            if opponent:
                # Adjust based on relative strength
                combined = profile.win_rate + (1 - opponent.win_rate)
                win_prob = combined / 2
            
            # Simulate match
            if random.random() < win_prob:
                return 2  # Won match
            else:
                # Lost - how many sets won?
                return random.choice([0, 1])
        
        elif stat_type == 'games_played' or stat_type == 'total_games':
            # Total games in match
            # Use both players if available
            base_games = profile.avg_games_won * 2  # Rough estimate
            std = profile.std_games_won * 2 if profile.std_games_won else base_games * 0.15
            return max(12, random.gauss(base_games, std))
        
        elif stat_type == 'fantasy_score':
            # Fantasy Score = aces * 1.5 + games_won * 1 + sets_won * 5 + match_win * 10
            # We simulate this based on player's typical performance
            sim_aces = max(0, random.gauss(profile.avg_aces or 3, profile.std_aces or 2))
            sim_games_won = max(0, random.gauss(profile.avg_games_won or 9, profile.std_games_won or 2))
            
            # Match outcome based on win rate
            win_prob = profile.win_rate or 0.5
            if opponent:
                combined = profile.win_rate + (1 - opponent.win_rate)
                win_prob = combined / 2
            
            won_match = random.random() < win_prob
            sim_sets_won = 2 if won_match else random.choice([0, 1])
            match_win_bonus = 10 if won_match else 0
            
            fantasy = (sim_aces * 1.5) + sim_games_won + (sim_sets_won * 5) + match_win_bonus
            return fantasy
        
        elif stat_type == 'breakpoints_won' or stat_type == 'break_points_won':
            # Break points won typically 1-7 per match
            # Correlates with opponent's serve performance and match length
            base_bp = 3.0  # Average break points won per match
            std_bp = 1.5
            
            # Adjust based on opponent (weaker server = more break points)
            if opponent and opponent.serve_hold_rate:
                # Lower serve hold rate = easier to break
                adj = 1 + (0.65 - opponent.serve_hold_rate) * 2
                base_bp *= adj
            
            return max(0, random.gauss(base_bp, std_bp))
        
        else:
            # Generic fallback
            return random.gauss(10, 3)
    
    def analyze_matchup(
        self,
        player1: str,
        player2: str,
        surface: str = "Hard"
    ) -> Dict:
        """Full matchup analysis with prop recommendations"""
        
        p1 = self.profiler.get_profile(player1, surface=surface)
        p2 = self.profiler.get_profile(player2, surface=surface)
        
        if not p1 or not p2:
            return {'error': 'Player not found'}
        
        h2h = self.profiler.get_head_to_head(player1, player2)
        
        # Generate prop recommendations
        props = []
        
        # Aces props
        for player, profile in [(player1, p1), (player2, p2)]:
            # Common ace lines
            for line in [4.5, 6.5, 8.5, 10.5]:
                if abs(profile.avg_aces - line) < 5:  # Only relevant lines
                    result = self.simulate_prop(
                        player, 'aces', line, 'HIGHER',
                        opponent=player2 if player == player1 else player1,
                        surface=surface
                    )
                    if result['tier'] != 'NO_PLAY':
                        props.append(result)
        
        # Games won props
        for player, profile in [(player1, p1), (player2, p2)]:
            for line in [10.5, 12.5, 14.5]:
                if abs(profile.avg_games_won - line) < 5:
                    result = self.simulate_prop(
                        player, 'games_won', line, 'HIGHER',
                        opponent=player2 if player == player1 else player1,
                        surface=surface
                    )
                    if result['tier'] != 'NO_PLAY':
                        props.append(result)
        
        # Sort by confidence
        props.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            'matchup': f"{p1.player_name} vs {p2.player_name}",
            'surface': surface,
            'head_to_head': h2h,
            'player1_profile': p1.to_dict(),
            'player2_profile': p2.to_dict(),
            'recommended_props': props[:10],  # Top 10
            'comparison': {
                'aces': f"{p1.player_name} ({p1.avg_aces:.1f}) vs {p2.player_name} ({p2.avg_aces:.1f})",
                'serve_hold': f"{p1.player_name} ({p1.serve_hold_rate:.1%}) vs {p2.player_name} ({p2.serve_hold_rate:.1%})",
                'win_rate': f"{p1.player_name} ({p1.win_rate:.1%}) vs {p2.player_name} ({p2.win_rate:.1%})",
            }
        }


# ============================================================================
# SECTION 4: CLI / DEMO
# ============================================================================

def main():
    """Demo the profiler and calibrated MC"""
    
    print("=" * 70)
    print("TENNIS PLAYER PROFILER - Real Data from Tennis Abstract")
    print("=" * 70)
    
    profiler = TennisPlayerProfiler()
    mc = CalibratedTennisMC(profiler)
    
    # Test players
    test_players = [
        "Carlos Alcaraz",
        "Novak Djokovic",
        "Aryna Sabalenka",
        "Elena Rybakina"
    ]
    
    print("\n" + "-" * 50)
    print("PLAYER PROFILES (From Tennis Abstract 2024)")
    print("-" * 50)
    
    profiles = {}
    for name in test_players:
        profile = profiler.get_profile(name)
        if profile:
            profiles[name] = profile
            print(f"\n{profile.player_name} ({profile.n_matches} matches)")
            print(f"  Win Rate:    {profile.win_rate:.1%}")
            print(f"  Avg Aces:    {profile.avg_aces:.1f} ± {profile.std_aces:.1f}")
            print(f"  Avg DF:      {profile.avg_double_faults:.1f}")
            print(f"  Serve Hold:  {profile.serve_hold_rate:.1%}")
            print(f"  BP Save:     {profile.bp_save_rate:.1%}")
            print(f"  Avg Games:   {profile.avg_games_won:.1f} ± {profile.std_games_won:.1f}")
            print(f"  Confidence:  {profile.confidence:.0%}")
    
    # Head-to-head
    print("\n" + "-" * 50)
    print("HEAD-TO-HEAD")
    print("-" * 50)
    
    h2h = profiler.get_head_to_head("Alcaraz", "Djokovic")
    if h2h['matches'] > 0:
        print(f"\n{h2h['player1']} vs {h2h['player2']}")
        print(f"  Total: {h2h['matches']} matches")
        print(f"  {h2h['player1']}: {h2h['p1_wins']} wins")
        print(f"  {h2h['player2']}: {h2h['p2_wins']} wins")
    
    # Prop simulation
    print("\n" + "-" * 50)
    print("PROP SIMULATION (AO Finals Lines)")
    print("-" * 50)
    
    # Test some real lines
    test_props = [
        ("Carlos Alcaraz", "aces", 10.5, "HIGHER", "Novak Djokovic"),
        ("Novak Djokovic", "aces", 8.5, "HIGHER", "Carlos Alcaraz"),
        ("Carlos Alcaraz", "games_won", 20.5, "HIGHER", "Novak Djokovic"),
        ("Aryna Sabalenka", "aces", 4.5, "HIGHER", "Elena Rybakina"),
        ("Elena Rybakina", "aces", 7.5, "HIGHER", "Aryna Sabalenka"),
    ]
    
    print("\n{:<25} {:<15} {:<8} {:<10} {:<8} {:<8}".format(
        "Player", "Prop", "Line", "Dir", "Prob", "Tier"
    ))
    print("-" * 80)
    
    for player, stat, line, direction, opponent in test_props:
        result = mc.simulate_prop(player, stat, line, direction, opponent)
        print("{:<25} {:<15} {:<8} {:<10} {:<8} {:<8}".format(
            result['player'][:24],
            stat,
            line,
            direction,
            f"{result['probability']:.1%}",
            result['tier']
        ))
    
    # Full matchup analysis
    print("\n" + "-" * 50)
    print("FULL MATCHUP ANALYSIS: Alcaraz vs Djokovic")
    print("-" * 50)
    
    analysis = mc.analyze_matchup("Alcaraz", "Djokovic", surface="Hard")
    
    print(f"\n{analysis['matchup']} ({analysis['surface']})")
    print(f"\nH2H: {analysis['head_to_head']['p1_wins']}-{analysis['head_to_head']['p2_wins']}")
    
    print("\nRecommended Props:")
    for prop in analysis['recommended_props'][:5]:
        print(f"  [{prop['tier']}] {prop['player']} {prop['direction']} {prop['line']} {prop['stat']}: {prop['confidence']:.1f}%")
    
    profiler.close()
    print("\n✅ Profiler demo complete!")


if __name__ == "__main__":
    main()
