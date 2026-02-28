"""
Contextual Adjustments - Layer 2 Evidence Generation
Detects lineup changes, injuries, and adjusts projections accordingly
"""
import os
import requests
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path


@dataclass
class ContextualEvidence:
    """Evidence bundle for contextual adjustments"""
    player: str
    stat: str
    mu_adjustment: float  # Delta to add to mean (e.g., +1.3 assists)
    sigma_adjustment: float  # Delta to add to std dev (e.g., -0.3 for less variance)
    confidence_delta: float  # Percentage points to add/subtract
    reasoning: str
    source: str  # 'serpapi', 'manual', 'deepseek'
    timestamp: str


class ContextualAdjuster:
    """
    Detects game context (injuries, lineup changes) and generates evidence
    for Truth Engine adjustments
    """
    
    def __init__(self):
        self.serpapi_key = os.getenv('SERPAPI_API_KEY')
        self.deepseek_key = os.getenv('DEEPSEEK_API_KEY')
        self.cache_file = Path("state/contextual_cache.json")
        self.cache = self._load_cache()
        
        # Manual overrides (set via menu or API)
        self.manual_absences = self._load_manual_absences()
    
    def _load_cache(self) -> Dict:
        """Load cached contextual checks to avoid API spam"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """Save cache to disk"""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def _load_manual_absences(self) -> Dict:
        """Load manual absence flags set via menu"""
        absence_file = Path("state/manual_absences.json")
        if absence_file.exists():
            try:
                with open(absence_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def set_manual_absence(self, player: str, team: str, reason: str = "injury"):
        """Manually flag a player as out (via menu option)"""
        self.manual_absences[player] = {
            "team": team,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        absence_file = Path("state/manual_absences.json")
        absence_file.parent.mkdir(parents=True, exist_ok=True)
        with open(absence_file, 'w') as f:
            json.dump(self.manual_absences, f, indent=2)
    
    def clear_manual_absences(self):
        """Clear all manual absence flags"""
        self.manual_absences = {}
        absence_file = Path("state/manual_absences.json")
        if absence_file.exists():
            absence_file.unlink()
    
    def check_player_absence(self, player: str, team: str) -> Optional[str]:
        """
        Check if key player is out tonight
        
        Returns reason if absent, None if playing
        """
        # Check manual overrides first
        if player in self.manual_absences:
            return self.manual_absences[player]['reason']
        
        # Check cache (avoid spamming SerpApi)
        cache_key = f"{player}_{team}_{datetime.now().strftime('%Y-%m-%d')}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Check SerpApi if available
        if self.serpapi_key and self.serpapi_key != "c3529a06a7cbfae2437fd725af5ba09079acb07a7bb354444d74646d720fd5ee":
            try:
                result = self._check_serpapi_injury(player, team)
                self.cache[cache_key] = result
                self._save_cache()
                return result
            except Exception as e:
                print(f"  [WARN] SerpApi check failed: {e}")
        
        return None
    
    def _check_serpapi_injury(self, player: str, team: str) -> Optional[str]:
        """Use SerpApi to check injury status"""
        url = "https://serpapi.com/search.json"
        params = {
            "q": f"{player} injury status today OR {player} out tonight",
            "api_key": self.serpapi_key,
            "num": 3
        }
        
        response = requests.get(url, params=params, timeout=5)
        if response.status_code != 200:
            return None
        
        data = response.json()
        results = data.get('organic_results', [])
        
        # Look for injury keywords in snippets
        injury_keywords = ['out', 'ruled out', 'injured', 'dnp', 'sidelined', 'questionable']
        for result in results:
            snippet = result.get('snippet', '').lower()
            if any(keyword in snippet for keyword in injury_keywords):
                return snippet[:100]  # Return reason
        
        return None
    
    def generate_adjustment(
        self,
        player: str,
        team: str,
        opponent: str,
        stat: str,
        mu: float,
        sigma: float,
        absent_teammate: Optional[str] = None
    ) -> Optional[ContextualEvidence]:
        """
        Generate contextual adjustment evidence
        
        Args:
            player: Player being projected
            team: Player's team
            opponent: Opponent team
            stat: Stat being projected (points, assists, rebounds, etc.)
            mu: Current mean projection
            sigma: Current std dev
            absent_teammate: Key teammate who is out (if any)
        
        Returns:
            ContextualEvidence if adjustment needed, None otherwise
        """
        
        # Rule 1: Primary ball handler out → Secondary playmaker gets boost
        if absent_teammate and stat in ['assists', 'ast']:
            # Lookup table for primary/secondary playmakers
            playmaker_pairs = {
                "Luka Doncic": ["LeBron James", "Kyrie Irving"],  # If Luka out, LeBron/Kyrie facilitate
                "Damian Lillard": ["Giannis Antetokounmpo"],
                "Stephen Curry": ["Draymond Green"],
                "Chris Paul": ["Devin Booker"],
                "Trae Young": ["Dejounte Murray"],
                # Add more as needed
            }
            
            affected_players = playmaker_pairs.get(absent_teammate, [])
            
            if player in affected_players:
                # Calculate adjustment
                usage_boost = 0.15  # 15% usage increase
                mu_delta = mu * usage_boost  # Proportional boost
                sigma_delta = -sigma * 0.10  # 10% less variance (more predictable role)
                confidence_delta = 5.0  # +5% confidence
                
                return ContextualEvidence(
                    player=player,
                    stat=stat,
                    mu_adjustment=mu_delta,
                    sigma_adjustment=sigma_delta,
                    confidence_delta=confidence_delta,
                    reasoning=f"{absent_teammate} OUT → {player} primary ball handler (+{usage_boost*100:.0f}% usage)",
                    source='rule_based',
                    timestamp=datetime.now().isoformat()
                )
        
        # Rule 2: Star scorer out → Secondary scorer gets points boost
        if absent_teammate and stat in ['points', 'pts']:
            scorer_pairs = {
                "Joel Embiid": ["Tyrese Maxey", "Tobias Harris"],
                "Kevin Durant": ["Devin Booker"],
                "LeBron James": ["Anthony Davis"],
                # Add more
            }
            
            affected_players = scorer_pairs.get(absent_teammate, [])
            
            if player in affected_players:
                usage_boost = 0.12  # 12% usage increase for scoring
                mu_delta = mu * usage_boost
                sigma_delta = -sigma * 0.05  # Slight variance reduction
                confidence_delta = 3.0
                
                return ContextualEvidence(
                    player=player,
                    stat=stat,
                    mu_adjustment=mu_delta,
                    sigma_adjustment=sigma_delta,
                    confidence_delta=confidence_delta,
                    reasoning=f"{absent_teammate} OUT → {player} primary scorer (+{usage_boost*100:.0f}% usage)",
                    source='rule_based',
                    timestamp=datetime.now().isoformat()
                )
        
        # No adjustment needed
        return None
    
    def check_and_adjust(
        self,
        player: str,
        team: str,
        opponent: str,
        stat: str,
        mu: float,
        sigma: float
    ) -> Optional[ContextualEvidence]:
        """
        Main entry point: Check for context and generate adjustment if needed
        
        Returns:
            ContextualEvidence if adjustment needed, None otherwise
        """
        
        # Get list of key teammates (could be expanded with API)
        key_teammates = self._get_key_teammates(team)
        
        # Check if any key teammate is out
        for teammate in key_teammates:
            absence_reason = self.check_player_absence(teammate, team)
            if absence_reason:
                # Generate adjustment for affected player
                evidence = self.generate_adjustment(
                    player=player,
                    team=team,
                    opponent=opponent,
                    stat=stat,
                    mu=mu,
                    sigma=sigma,
                    absent_teammate=teammate
                )
                
                if evidence:
                    return evidence
        
        return None
    
    def _get_key_teammates(self, team: str) -> List[str]:
        """
        Get list of key players for a team
        
        TODO: Could be enhanced with NBA API to get current roster
        For now, hardcode stars
        """
        team_stars = {
            "DAL": ["Luka Doncic", "Kyrie Irving"],
            "LAL": ["LeBron James", "Anthony Davis"],
            "GSW": ["Stephen Curry", "Klay Thompson"],
            "BOS": ["Jayson Tatum", "Jaylen Brown"],
            "MIL": ["Giannis Antetokounmpo", "Damian Lillard"],
            "PHI": ["Joel Embiid", "Tyrese Maxey"],
            "PHX": ["Kevin Durant", "Devin Booker"],
            "ATL": ["Trae Young", "Dejounte Murray"],
            # Add more teams
        }
        
        return team_stars.get(team, [])


def apply_contextual_adjustment(
    mu: float,
    sigma: float,
    evidence: Optional[ContextualEvidence]
) -> tuple[float, float, str]:
    """
    Apply contextual evidence to base projection
    
    Args:
        mu: Base mean projection
        sigma: Base std dev
        evidence: Contextual evidence (or None)
    
    Returns:
        (adjusted_mu, adjusted_sigma, reasoning)
    """
    if not evidence:
        return mu, sigma, "no_context"
    
    adjusted_mu = mu + evidence.mu_adjustment
    adjusted_sigma = max(0.1, sigma + evidence.sigma_adjustment)  # Never go below 0.1
    
    return adjusted_mu, adjusted_sigma, evidence.reasoning
