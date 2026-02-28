"""
DataGolf API Client
===================
Fetches strokes gained data, rankings, predictions, and course fit.

API Documentation: https://datagolf.com/api-access

Requires:
- DATAGOLF_API_KEY in .env or environment variable
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json
import requests
from functools import lru_cache


# Project root import
import sys
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from golf.config import DATAGOLF_CONFIG


class DataGolfClient:
    """
    Client for DataGolf API.
    Handles authentication, rate limiting, and response caching.
    """
    
    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[Path] = None):
        """
        Initialize DataGolf client.
        
        Args:
            api_key: DataGolf API key (falls back to DATAGOLF_API_KEY env var)
            cache_dir: Directory for caching responses
        """
        self.api_key = api_key or os.getenv("DATAGOLF_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DataGolf API key required. Set DATAGOLF_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.base_url = DATAGOLF_CONFIG["base_url"]
        self.rate_limit = DATAGOLF_CONFIG["rate_limit_per_minute"]
        self._last_request_time = 0
        
        # Cache setup
        self.cache_dir = cache_dir or Path(__file__).parent.parent / "data" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _rate_limit_wait(self):
        """Enforce rate limiting."""
        min_interval = 60.0 / self.rate_limit
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()
    
    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make authenticated API request.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response as dict
        """
        self._rate_limit_wait()
        
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params["key"] = self.api_key
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        return response.json()
    
    def _get_cached(self, cache_key: str, max_age_hours: int = 4) -> Optional[Dict]:
        """Check for valid cached response."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            return None
        
        # Check age
        mtime = cache_file.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600
        if age_hours > max_age_hours:
            return None
        
        with open(cache_file) as f:
            return json.load(f)
    
    def _set_cached(self, cache_key: str, data: Dict):
        """Save response to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)
    
    # =========================================================================
    # PUBLIC API METHODS
    # =========================================================================
    
    def get_rankings(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get current DataGolf rankings (SG-based world ranking).
        
        Returns:
            List of players with ranking, SG total, skill estimates
        """
        cache_key = "dg_rankings"
        
        if not force_refresh:
            cached = self._get_cached(cache_key, max_age_hours=12)
            if cached:
                return cached.get("rankings", [])
        
        data = self._request("/preds/get-dg-rankings")
        self._set_cached(cache_key, data)
        
        return data.get("rankings", [])
    
    def get_skill_decompositions(
        self,
        tour: str = "pga",
        force_refresh: bool = False
    ) -> List[Dict]:
        """
        Get strokes gained decomposition for all players.
        
        Args:
            tour: "pga", "euro", "kft" (Korn Ferry)
            
        Returns:
            List with sg_ott, sg_app, sg_arg, sg_putt for each player
        """
        cache_key = f"sg_decomp_{tour}"
        
        if not force_refresh:
            cached = self._get_cached(cache_key, max_age_hours=12)
            if cached:
                return cached.get("players", [])
        
        data = self._request(
            "/preds/skill-decompositions",
            params={"tour": tour}
        )
        self._set_cached(cache_key, data)
        
        return data.get("players", [])
    
    def get_player_skill(self, player_name: str) -> Optional[Dict]:
        """
        Get SG decomposition for a specific player.
        
        Args:
            player_name: Player name (case-insensitive search)
            
        Returns:
            Dict with sg_ott, sg_app, sg_arg, sg_putt, sg_total, or None
        """
        players = self.get_skill_decompositions()
        
        name_lower = player_name.lower().strip()
        for p in players:
            if name_lower in p.get("player_name", "").lower():
                return {
                    "player_name": p.get("player_name"),
                    "player_id": p.get("dg_id"),
                    "sg_ott": p.get("sg_ott", 0),
                    "sg_app": p.get("sg_app", 0),
                    "sg_arg": p.get("sg_arg", 0),
                    "sg_putt": p.get("sg_putt", 0),
                    "sg_total": p.get("sg_total", 0),
                    "driving_dist": p.get("driving_dist"),
                    "driving_acc": p.get("driving_acc"),
                }
        
        return None
    
    def get_pre_tournament_predictions(
        self,
        tour: str = "pga",
        event_id: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict:
        """
        Get pre-tournament predictions for current/upcoming event.
        
        Returns:
            {
                "event_name": str,
                "baseline_preds": [
                    {"player_name": str, "win_prob": float, "top_5": float, ...}
                ]
            }
        """
        cache_key = f"pre_tourney_{tour}_{event_id or 'current'}"
        
        if not force_refresh:
            cached = self._get_cached(cache_key, max_age_hours=4)
            if cached:
                return cached
        
        params = {"tour": tour, "file_format": "json"}
        if event_id:
            params["event_id"] = event_id
        
        data = self._request("/preds/pre-tournament-preds", params=params)
        self._set_cached(cache_key, data)
        
        return data
    
    def get_live_predictions(self, tour: str = "pga") -> Dict:
        """
        Get in-play tournament predictions (during live event).
        
        Returns:
            Current win/top5/top10/make_cut probabilities based on live scores
        """
        # No caching for live data
        return self._request(
            "/preds/in-play-tournament-preds",
            params={"tour": tour, "file_format": "json"}
        )
    
    def get_matchup_predictions(
        self,
        player_1: str,
        player_2: str,
        rounds: str = "tournament",  # "tournament" or "round_1", "round_2", etc.
    ) -> Optional[Dict]:
        """
        Calculate head-to-head matchup probability.
        
        Args:
            player_1: First player name
            player_2: Second player name  
            rounds: "tournament" for full event, "round_X" for single round
            
        Returns:
            {
                "player_1": str,
                "player_2": str,
                "p1_win_prob": float,
                "p2_win_prob": float,
                "tie_prob": float,  # For H2H purposes, ties usually split
            }
        """
        preds = self.get_pre_tournament_predictions()
        baseline = preds.get("baseline_preds", [])
        
        p1_data = None
        p2_data = None
        
        for p in baseline:
            name = p.get("player_name", "").lower()
            if player_1.lower() in name:
                p1_data = p
            if player_2.lower() in name:
                p2_data = p
        
        if not p1_data or not p2_data:
            return None
        
        # Use DataGolf's inherent skill estimates for H2H
        # Better player wins more often, weighted by SG differential
        p1_skill = p1_data.get("sg_total", 0)
        p2_skill = p2_data.get("sg_total", 0)
        
        # Approximate H2H probability from SG differential
        # ~0.50 strokes = ~55% win rate over 72 holes
        sg_diff = p1_skill - p2_skill
        
        if rounds == "tournament":
            # Tournament-long matchup (4 rounds)
            p1_win_prob = 0.50 + (sg_diff * 0.10)  # 10% per stroke advantage
        else:
            # Single round (more variance)
            p1_win_prob = 0.50 + (sg_diff * 0.05)  # 5% per stroke advantage
        
        # Clamp to valid range
        p1_win_prob = max(0.20, min(0.80, p1_win_prob))
        p2_win_prob = 1.0 - p1_win_prob
        
        return {
            "player_1": p1_data.get("player_name"),
            "player_2": p2_data.get("player_name"),
            "p1_win_prob": round(p1_win_prob, 4),
            "p2_win_prob": round(p2_win_prob, 4),
            "sg_differential": round(sg_diff, 3),
            "rounds": rounds,
        }
    
    def get_course_history(
        self,
        course_id: str,
        years: int = 5
    ) -> List[Dict]:
        """
        Get historical results at a specific course.
        
        Args:
            course_id: Course identifier
            years: Number of years to look back
            
        Returns:
            List of past tournament results with SG data
        """
        # DataGolf historical endpoint
        data = self._request(
            "/historical-raw-data/event-list",
            params={"file_format": "json"}
        )
        
        # Filter by course
        events = [
            e for e in data.get("events", [])
            if course_id.lower() in e.get("course", "").lower()
        ]
        
        return events[:years * 4]  # ~4 events per year max
    
    def calculate_course_fit(
        self,
        player_name: str,
        course_type: str = "balanced"
    ) -> Optional[Dict]:
        """
        Calculate player's course fit based on SG profile.
        
        Args:
            player_name: Player name
            course_type: One of "balanced", "ball_strikers", "bombers", 
                        "putting_premium", "short_game"
                        
        Returns:
            {
                "course_fit_score": float (0-100),
                "strengths": List[str],
                "weaknesses": List[str],
                "expected_sg_adjustment": float
            }
        """
        from golf.config import SG_WEIGHTS_BY_COURSE_TYPE
        
        player = self.get_player_skill(player_name)
        if not player:
            return None
        
        weights = SG_WEIGHTS_BY_COURSE_TYPE.get(course_type, SG_WEIGHTS_BY_COURSE_TYPE["balanced"])
        
        # Calculate weighted SG for this course type
        weighted_sg = (
            player["sg_ott"] * weights["sg_ott"] +
            player["sg_app"] * weights["sg_app"] +
            player["sg_arg"] * weights["sg_arg"] +
            player["sg_putt"] * weights["sg_putt"]
        )
        
        # Convert to fit score (0-100 scale)
        # +2.0 SG = ~90 fit, 0.0 SG = ~50 fit, -2.0 SG = ~10 fit
        fit_score = 50 + (weighted_sg * 20)
        fit_score = max(0, min(100, fit_score))
        
        # Identify strengths/weaknesses
        strengths = []
        weaknesses = []
        
        sg_categories = [
            ("Driving (OTT)", player["sg_ott"], weights["sg_ott"]),
            ("Approach (APP)", player["sg_app"], weights["sg_app"]),
            ("Short Game (ARG)", player["sg_arg"], weights["sg_arg"]),
            ("Putting (PUTT)", player["sg_putt"], weights["sg_putt"]),
        ]
        
        for name, sg, weight in sg_categories:
            if sg > 0.3 and weight >= 0.25:
                strengths.append(f"{name}: +{sg:.2f} (key skill)")
            elif sg < -0.3 and weight >= 0.25:
                weaknesses.append(f"{name}: {sg:.2f} (liability)")
        
        return {
            "player_name": player["player_name"],
            "course_type": course_type,
            "course_fit_score": round(fit_score, 1),
            "weighted_sg": round(weighted_sg, 3),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "expected_sg_adjustment": round(weighted_sg - player["sg_total"], 3),
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_tournament_field(tour: str = "pga") -> List[Dict]:
    """Get current tournament field with predictions."""
    client = DataGolfClient()
    preds = client.get_pre_tournament_predictions(tour=tour)
    return preds.get("baseline_preds", [])


def get_player_sg(player_name: str) -> Optional[Dict]:
    """Quick lookup of player strokes gained."""
    client = DataGolfClient()
    return client.get_player_skill(player_name)


if __name__ == "__main__":
    # Demo/test
    import sys
    
    if os.getenv("DATAGOLF_API_KEY"):
        client = DataGolfClient()
        print("DataGolf Client initialized successfully")
        
        # Test rankings
        print("\n--- Top 10 DG Rankings ---")
        rankings = client.get_rankings()[:10]
        for r in rankings:
            print(f"{r.get('dg_rank', '?')}. {r.get('player_name')} (SG: {r.get('datagolf_rank', '?')})")
    else:
        print("Set DATAGOLF_API_KEY to test API client")
        print("\nDemo mode - showing structure only:")
        print("  client = DataGolfClient(api_key='...')")
        print("  rankings = client.get_rankings()")
        print("  player = client.get_player_skill('Scottie Scheffler')")
        print("  course_fit = client.calculate_course_fit('Scottie Scheffler', 'putting_premium')")
