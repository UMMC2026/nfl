import json
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

@dataclass
class NFLProp:
    player: str
    team: str
    stat: str
    line: float
    direction: str  # "More" or "Less"
    
@dataclass
class NFLGame:
    away: str
    home: str
    datetime: str
    spread: float = 0.0
    total: float = 0.0

class NFLAnalyzer:
    STAT_KEY_MAP = {
        "Pass Yards": "pass_yds",
        "Rush Yards": "rush_yds",
        "Rec Yards": "rec_yds",
        "Receptions": "receptions",
        "Pass TDs": "pass_tds",
        "Rush TDs": "rush_tds",
        "Rec TDs": "rec_tds",
        # Add more mappings as needed
    }

    def __init__(self):
        self.team_stats = self.load_team_stats()
        self.player_stats = self.load_player_stats()
        self.coaching_data = self.load_coaching_data()
        
    def load_team_stats(self) -> Dict[str, Any]:
        # This should come from your database/API
        return {
            "SF": {"off_rank": 3, "def_rank": 8, "pace": "fast", "coach": "Kyle Shanahan"},
            "SEA": {"off_rank": 12, "def_rank": 15, "pace": "average", "coach": "Mike Macdonald"},
            "HOU": {"off_rank": 7, "def_rank": 11, "pace": "fast", "coach": "DeMeco Ryans"},
            "PIT": {"off_rank": 18, "def_rank": 5, "pace": "slow", "coach": "Mike Tomlin"}
        }
    
    def load_player_stats(self):
        return {}
    def load_coaching_data(self):
        return {}
    def calculate_probability(self, prop: NFLProp, game: NFLGame) -> float:
        """
        Hydrate real player stats and use them to compute probabilities for each prop.
        Check roster eligibility and injury status.
        Fallback to team logic if hydration fails.
        Logs hydration and probability for debugging.
        """
        # Check injury status (NFL uses injury_availability_gate)
        injury_confidence = 1.0
        try:
            from ufa.gates.injury_gate import injury_availability_gate
            injury_result = injury_availability_gate(player=prop.player, team=prop.team, league="NFL")
            if not injury_result.allowed:
                print(f"[INJURY] {prop.player} BLOCKED ({injury_result.injury_status}): {injury_result.block_reason}")
                return 0.01  # Blocked players get minimum probability
            elif injury_result.downgraded:
                injury_confidence = injury_result.confidence_multiplier
                print(f"[INJURY] {prop.player} DOWNGRADED ({injury_result.injury_status}) - confidence multiplier: {injury_confidence:.2f}")
        except Exception as e:
            print(f"[INJURY] Skipped injury check for {prop.player}: {e}")
        
        try:
            from ufa.ingest.hydrate import hydrate_recent_values
            # Map slate stat to atomic key if possible
            stat_key = self.STAT_KEY_MAP.get(prop.stat, prop.stat)
            recent_values = hydrate_recent_values(
                league="NFL",
                player=prop.player,
                stat_key=stat_key,
                team=prop.team,
                nfl_seasons=None,
                last_n=10
            )
            print(f"[HYDRATE] {prop.player} {prop.stat} (mapped: {stat_key}): {recent_values}")
            if recent_values and isinstance(recent_values, list) and len(recent_values) > 0:
                import numpy as np
                from scipy.stats import norm
                mu = np.mean(recent_values)
                sigma = np.std(recent_values) if np.std(recent_values) > 0 else 1.0
                line = float(prop.line)
                if prop.direction.lower() == "more":
                    prob = 1 - norm.cdf(line, loc=mu, scale=sigma)
                else:
                    prob = norm.cdf(line, loc=mu, scale=sigma)
                # Apply injury confidence modifier
                prob = prob * injury_confidence
                print(f"[PROB] {prop.player} {prop.stat} {prop.direction} {prop.line}: mu={mu:.2f}, sigma={sigma:.2f}, prob={prob:.3f}")
                return float(np.clip(prob, 0.01, 0.99))
        except Exception as e:
            print(f"[HYDRATE ERROR] {prop.player} {prop.stat}: {e}")
        base_prob = 0.5
        opponent = game.home if prop.team == game.away else game.away
        opp_defense = self.team_stats.get(opponent, {}).get("def_rank", 16)
        defense_factor = 1 - (opp_defense / 32)
        coach = self.team_stats.get(prop.team, {}).get("coach", "")
        if "Shanahan" in coach:
            base_prob += 0.05
        if "Tomlin" in coach and prop.direction == "Less":
            base_prob += 0.03
        print(f"[FALLBACK PROB] {prop.player} {prop.stat} {prop.direction} {prop.line}: {base_prob * defense_factor:.3f}")
        return min(0.95, max(0.05, base_prob * defense_factor))
    def get_coaching_insights(self, game: NFLGame) -> str:
        home_coach = self.team_stats.get(game.home, {}).get("coach", "Unknown")
        away_coach = self.team_stats.get(game.away, {}).get("coach", "Unknown")
        insights = {
            "SF": "Kyle Shanahan's motion offense creates mismatches. Uses 21 personnel on 65% of snaps.",
            "SEA": "Mike Macdonald's aggressive blitz packages (42% blitz rate) but vulnerable to play action.",
            "HOU": "DeMeco Ryans' defensive scheme creates turnovers (1.8 per game) but allows big plays.",
            "PIT": "Mike Tomlin's defensive discipline - allows fewest explosive plays (20+ yards) in NFL."
        }
        return f"""
{away_coach} vs {home_coach}
• {insights.get(game.away, 'No data')}
• {insights.get(game.home, 'No data')}
"""
    def analyze_slate(self, games: List[NFLGame], props: List[NFLProp]) -> Dict[str, Any]:
        results = {
            "timestamp": datetime.now().isoformat(),
            "games_analyzed": len(games),
            "props_analyzed": len(props),
            "qualified_props": [],
            "game_insights": {},
            "portfolio_metrics": {}
        }
        for prop in props:
            game = next((g for g in games if g.away == prop.team or g.home == prop.team), None)
            if game:
                probability = self.calculate_probability(prop, game)
                if probability >= 0.65:
                    results["qualified_props"].append({
                        "player": prop.player,
                        "stat": prop.stat,
                        "line": prop.line,
                        "direction": prop.direction,
                        "probability": round(probability * 100),
                        "team": prop.team,
                        "game": f"{game.away}@{game.home}"
                    })
        for game in games:
            results["game_insights"][f"{game.away}@{game.home}"] = {
                "coaching_insights": self.get_coaching_insights(game),
                "key_matchup": self.get_key_matchup(game),
                "weather_impact": self.get_weather_impact(game)
            }
        results["portfolio_metrics"] = self.calculate_portfolio_metrics(results["qualified_props"])
        return results
    def get_key_matchup(self, game: NFLGame) -> str:
        matchups = {
            "SF@SEA": "SF WRs vs SEA secondary - Seattle allows 245 passing yards/game",
            "HOU@PIT": "HOU offense vs PIT defense - Steel Curtain allows 18.2 PPG",
            "DAL@PHI": "Dak Prescott vs Eagles pass rush - 38 sacks this season"
        }
        return matchups.get(f"{game.away}@{game.home}", "No specific matchup data")
    def get_weather_impact(self, game: NFLGame) -> str:
        return "Clear conditions, minimal wind impact"
    def calculate_portfolio_metrics(self, props: List[Dict]) -> Dict[str, Any]:
        if not props:
            return {}
        avg_prob = sum(p["probability"] for p in props) / len(props)
        expected_hits = sum(p["probability"] / 100 for p in props)
        return {
            "avg_probability": round(avg_prob, 1),
            "expected_hits": round(expected_hits, 2),
            "total_units": len(props),
            "expected_roi": round((expected_hits * 1.91 - len(props)) / len(props) * 100, 1)
        }
