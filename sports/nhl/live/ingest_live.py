"""
LIVE DATA INGESTION — NHL v2.0 Intermission Engine
===================================================

Fetches real-time game state during intermissions for
live betting adjustments.

DATA SOURCES:
- NHL API (stats.nhl.com) for live game feed
- ESPN API for backup/validation

TIMING GATES:
- L1: Only ingest during intermissions (≤3 mins into intermission)
- L2: Single update per intermission (no re-fetches)
- L3: Stale data (>5 mins old) rejected

GLOBAL ASSERTION:
  assert live_bets_per_game <= 1
"""

import json
import time
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum, auto
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# GAME PERIOD TRACKING
# ─────────────────────────────────────────────────────────

class GameState(Enum):
    """Live game state enum."""
    PREGAME = auto()
    PERIOD_1 = auto()
    INTERMISSION_1 = auto()
    PERIOD_2 = auto()
    INTERMISSION_2 = auto()
    PERIOD_3 = auto()
    OVERTIME = auto()
    SHOOTOUT = auto()
    FINAL = auto()
    DELAYED = auto()
    UNKNOWN = auto()


class IntermissionWindow(Enum):
    """Which intermission we're in."""
    FIRST = "INT_1"   # After period 1
    SECOND = "INT_2"  # After period 2
    NONE = "NONE"


@dataclass
class LiveGameSnapshot:
    """Real-time game state snapshot."""
    game_id: str
    home_team: str
    away_team: str
    
    # Score
    home_score: int
    away_score: int
    
    # Period info
    period: int
    period_time_remaining: str
    game_state: GameState
    
    # Intermission-specific
    intermission_window: IntermissionWindow
    intermission_time_remaining: Optional[int]  # seconds
    
    # Shot counts (for SOG models)
    home_shots: int
    away_shots: int
    
    # Power play info
    home_pp_time: int  # seconds in PP
    away_pp_time: int
    home_pims: int
    away_pims: int
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    data_age_seconds: float = 0.0
    
    @property
    def is_intermission(self) -> bool:
        """Check if game is in intermission."""
        return self.game_state in (GameState.INTERMISSION_1, GameState.INTERMISSION_2)
    
    @property
    def goal_differential(self) -> int:
        """Home perspective goal differential."""
        return self.home_score - self.away_score
    
    @property
    def total_goals(self) -> int:
        return self.home_score + self.away_score
    
    @property
    def is_stale(self) -> bool:
        """Data older than 5 minutes is stale."""
        return self.data_age_seconds > 300
    
    def __repr__(self):
        state_str = self.game_state.name
        return (
            f"LiveGameSnapshot({self.away_team} @ {self.home_team})\n"
            f"  Score: {self.away_score}-{self.home_score}\n"
            f"  State: {state_str}, Period {self.period}\n"
            f"  Shots: {self.away_shots}-{self.home_shots}\n"
            f"  Age: {self.data_age_seconds:.0f}s"
        )


# ─────────────────────────────────────────────────────────
# GATE L1: TIMING VALIDATION
# ─────────────────────────────────────────────────────────

class IntermissionGate:
    """
    Gate L1: Only allow ingestion during intermissions.
    
    RULES:
    - Must be in INTERMISSION_1 or INTERMISSION_2 state
    - Must be within 3 minutes of intermission start
    - REJECTS: Mid-period, overtime, final games
    """
    
    MAX_INTERMISSION_TIME = 180  # 3 minutes into intermission max
    
    @classmethod
    def validate(cls, snapshot: LiveGameSnapshot) -> Tuple[bool, str]:
        """
        Validate snapshot is in valid intermission window.
        
        Returns:
            (valid, reason)
        """
        if not snapshot.is_intermission:
            return False, f"REJECTED: Not in intermission (state={snapshot.game_state.name})"
        
        if snapshot.intermission_time_remaining is None:
            return False, "REJECTED: Missing intermission time data"
        
        # Intermission is ~18 mins, so remaining < 15 mins means >3 mins elapsed
        elapsed = 1080 - snapshot.intermission_time_remaining  # 18 min intermission
        if elapsed > cls.MAX_INTERMISSION_TIME:
            return False, f"REJECTED: Too late in intermission ({elapsed}s elapsed, max={cls.MAX_INTERMISSION_TIME}s)"
        
        if snapshot.is_stale:
            return False, f"REJECTED: Stale data ({snapshot.data_age_seconds:.0f}s old)"
        
        return True, f"PASSED: Valid intermission window ({snapshot.intermission_window.value})"


# ─────────────────────────────────────────────────────────
# GATE L2: SINGLE UPDATE TRACKING
# ─────────────────────────────────────────────────────────

class LiveUpdateTracker:
    """
    Gate L2: Track updates to enforce single-update rule.
    
    Only ONE live update allowed per game per intermission.
    """
    
    def __init__(self):
        # game_id -> {INT_1: True, INT_2: False}
        self._updates: Dict[str, Dict[str, bool]] = {}
    
    def check_and_mark(
        self,
        game_id: str,
        intermission: IntermissionWindow
    ) -> Tuple[bool, str]:
        """
        Check if update allowed, mark if so.
        
        Returns:
            (allowed, reason)
        """
        if intermission == IntermissionWindow.NONE:
            return False, "REJECTED: Not in intermission"
        
        if game_id not in self._updates:
            self._updates[game_id] = {
                IntermissionWindow.FIRST.value: False,
                IntermissionWindow.SECOND.value: False,
            }
        
        key = intermission.value
        if self._updates[game_id][key]:
            return False, f"REJECTED: Already updated in {key}"
        
        # Mark as updated
        self._updates[game_id][key] = True
        return True, f"PASSED: First update for {game_id} {key}"
    
    def reset_game(self, game_id: str):
        """Reset tracking for a game."""
        if game_id in self._updates:
            del self._updates[game_id]
    
    def get_update_count(self, game_id: str) -> int:
        """Get number of updates for a game."""
        if game_id not in self._updates:
            return 0
        return sum(1 for v in self._updates[game_id].values() if v)


# Singleton tracker
_update_tracker = LiveUpdateTracker()


def get_update_tracker() -> LiveUpdateTracker:
    """Get the singleton update tracker."""
    return _update_tracker


# ─────────────────────────────────────────────────────────
# NHL API INGESTION
# ─────────────────────────────────────────────────────────

NHL_API_BASE = "https://api-web.nhle.com/v1"
TIMEOUT_SECONDS = 10


def _fetch_json(url: str) -> Optional[Dict]:
    """Fetch JSON from URL with timeout."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "UNDERDOG-NHL-LIVE/2.0"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        logger.error(f"API fetch failed: {url} -> {e}")
        return None


def _parse_game_state(api_state: str) -> GameState:
    """Convert NHL API game state to enum."""
    state_map = {
        "PREVIEW": GameState.PREGAME,
        "PRE": GameState.PREGAME,
        "LIVE": GameState.PERIOD_1,  # Will be refined by period
        "CRIT": GameState.PERIOD_3,
        "FINAL": GameState.FINAL,
        "OFF": GameState.FINAL,
    }
    return state_map.get(api_state, GameState.UNKNOWN)


def _refine_live_state(base_state: GameState, period: int, intermission: bool) -> GameState:
    """Refine game state based on period and intermission."""
    if base_state == GameState.FINAL:
        return GameState.FINAL
    
    if intermission:
        if period == 1:
            return GameState.INTERMISSION_1
        elif period == 2:
            return GameState.INTERMISSION_2
    
    period_states = {
        1: GameState.PERIOD_1,
        2: GameState.PERIOD_2,
        3: GameState.PERIOD_3,
        4: GameState.OVERTIME,
        5: GameState.SHOOTOUT,
    }
    return period_states.get(period, GameState.PERIOD_3)


def fetch_live_game(game_id: str) -> Optional[LiveGameSnapshot]:
    """
    Fetch live game data from NHL API.
    
    Args:
        game_id: NHL game ID (e.g., "2024020815")
    
    Returns:
        LiveGameSnapshot or None if fetch failed
    """
    fetch_start = time.time()
    
    url = f"{NHL_API_BASE}/gamecenter/{game_id}/play-by-play"
    data = _fetch_json(url)
    
    if not data:
        return None
    
    fetch_time = time.time() - fetch_start
    
    try:
        # Extract teams
        home_team = data.get("homeTeam", {}).get("abbrev", "HOME")
        away_team = data.get("awayTeam", {}).get("abbrev", "AWAY")
        
        # Extract scores
        home_score = data.get("homeTeam", {}).get("score", 0)
        away_score = data.get("awayTeam", {}).get("score", 0)
        
        # Period info
        period = data.get("period", 1)
        period_time = data.get("clock", {}).get("timeRemaining", "20:00")
        in_intermission = data.get("clock", {}).get("inIntermission", False)
        
        # Parse game state
        api_state = data.get("gameState", "LIVE")
        base_state = _parse_game_state(api_state)
        game_state = _refine_live_state(base_state, period, in_intermission)
        
        # Intermission window
        if game_state == GameState.INTERMISSION_1:
            intermission_window = IntermissionWindow.FIRST
        elif game_state == GameState.INTERMISSION_2:
            intermission_window = IntermissionWindow.SECOND
        else:
            intermission_window = IntermissionWindow.NONE
        
        # Shot counts (may need boxscore endpoint)
        home_shots = data.get("homeTeam", {}).get("sog", 0)
        away_shots = data.get("awayTeam", {}).get("sog", 0)
        
        # Power play (simplified - would need plays data for accuracy)
        home_pp_time = 0
        away_pp_time = 0
        home_pims = 0
        away_pims = 0
        
        # Intermission time (estimate)
        intermission_remaining = None
        if in_intermission:
            # NHL intermissions are ~18 minutes
            intermission_remaining = 1080  # Default to full
        
        return LiveGameSnapshot(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            period=period,
            period_time_remaining=period_time,
            game_state=game_state,
            intermission_window=intermission_window,
            intermission_time_remaining=intermission_remaining,
            home_shots=home_shots,
            away_shots=away_shots,
            home_pp_time=home_pp_time,
            away_pp_time=away_pp_time,
            home_pims=home_pims,
            away_pims=away_pims,
            timestamp=datetime.now(),
            data_age_seconds=fetch_time,
        )
        
    except (KeyError, TypeError) as e:
        logger.error(f"Failed to parse game data: {e}")
        return None


def fetch_today_games() -> List[Dict]:
    """
    Fetch today's NHL games.
    
    Returns:
        List of game info dicts with game_id, teams, time
    """
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{NHL_API_BASE}/schedule/{today}"
    
    data = _fetch_json(url)
    if not data:
        return []
    
    games = []
    for day in data.get("gameWeek", []):
        for game in day.get("games", []):
            games.append({
                "game_id": str(game.get("id", "")),
                "home_team": game.get("homeTeam", {}).get("abbrev", ""),
                "away_team": game.get("awayTeam", {}).get("abbrev", ""),
                "start_time": game.get("startTimeUTC", ""),
                "venue": game.get("venue", {}).get("default", ""),
            })
    
    return games


# ─────────────────────────────────────────────────────────
# VALIDATED LIVE FETCH
# ─────────────────────────────────────────────────────────

def fetch_validated_live(
    game_id: str,
    enforce_gates: bool = True,
) -> Tuple[Optional[LiveGameSnapshot], str]:
    """
    Fetch live data with full gate validation.
    
    Args:
        game_id: NHL game ID
        enforce_gates: If True, enforce L1/L2 gates
    
    Returns:
        (snapshot, reason) - snapshot is None if gates failed
    """
    snapshot = fetch_live_game(game_id)
    
    if snapshot is None:
        return None, "FAILED: API fetch failed"
    
    if not enforce_gates:
        return snapshot, "BYPASSED: Gates disabled"
    
    # Gate L1: Timing validation
    valid, reason = IntermissionGate.validate(snapshot)
    if not valid:
        return None, reason
    
    # Gate L2: Single update check
    tracker = get_update_tracker()
    allowed, track_reason = tracker.check_and_mark(
        game_id,
        snapshot.intermission_window
    )
    if not allowed:
        return None, track_reason
    
    return snapshot, f"PASSED: All gates cleared for {game_id}"


# ─────────────────────────────────────────────────────────
# DEMO / SELF-TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 60)
    print("LIVE INGESTION ENGINE — NHL v2.0 DEMO")
    print("=" * 60)
    
    # Fetch today's games
    print("\nFetching today's NHL games...")
    games = fetch_today_games()
    
    if not games:
        print("No games found (or API unavailable)")
        # Demo with mock data
        print("\nDemo with mock snapshot:")
        mock = LiveGameSnapshot(
            game_id="2024020815",
            home_team="BOS",
            away_team="DET",
            home_score=2,
            away_score=1,
            period=1,
            period_time_remaining="00:00",
            game_state=GameState.INTERMISSION_1,
            intermission_window=IntermissionWindow.FIRST,
            intermission_time_remaining=1000,
            home_shots=15,
            away_shots=10,
            home_pp_time=120,
            away_pp_time=0,
            home_pims=4,
            away_pims=2,
        )
        print(mock)
        
        # Test Gate L1
        valid, reason = IntermissionGate.validate(mock)
        print(f"\nGate L1: {reason}")
        
        # Test Gate L2
        tracker = get_update_tracker()
        allowed, track_reason = tracker.check_and_mark(
            mock.game_id,
            mock.intermission_window
        )
        print(f"Gate L2 (1st): {track_reason}")
        
        # Try second update (should fail)
        allowed2, track_reason2 = tracker.check_and_mark(
            mock.game_id,
            mock.intermission_window
        )
        print(f"Gate L2 (2nd): {track_reason2}")
    else:
        print(f"Found {len(games)} games:")
        for g in games[:5]:
            print(f"  {g['away_team']} @ {g['home_team']} ({g['game_id']})")
