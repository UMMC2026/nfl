"""
UFA Learning System Integration Guide

Complete implementation for integrating historical data analysis
into the UFA system using Sportsdata.io and SerpApi.
"""

import os
import asyncio
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

from ufa.analysis.results_learning_loop import UFALearningLoop, LearningReport


@dataclass
class SportsDataGame:
    """Sportsdata.io game data structure."""
    game_id: str
    season: int
    season_type: int  # 1=regular, 2=post, 3=pre
    status: str  # "Final", "InProgress", etc.
    home_team: str
    away_team: str
    home_score: Optional[int]
    away_score: Optional[int]
    date_time: str
    updated: str


@dataclass
class SportsDataPlayerStats:
    """Sportsdata.io player stats structure."""
    player_id: int
    name: str
    team: str
    position: str
    points: float
    rebounds: float
    assists: float
    steals: float
    blocks: float
    turnovers: float
    minutes: int
    field_goals_made: int
    field_goals_attempted: int
    three_pointers_made: int
    three_pointers_attempted: int
    free_throws_made: int
    free_throws_attempted: int


class SportsDataAPI:
    """
    Sportsdata.io API client for bulk historical NBA data.

    Free tier: 1000 calls/day, 10/minute
    Perfect for bulk historical analysis.
    """

    BASE_URL = "https://api.sportsdata.io/v2/json"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Ocp-Apim-Subscription-Key': api_key,
            'User-Agent': 'UFA-Learning-System/1.0'
        })

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make API request with error handling."""
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            # Check rate limit headers
            remaining = response.headers.get('X-RateLimit-Remaining')
            if remaining and int(remaining) < 10:
                print(f"⚠️  Rate limit warning: {remaining} calls remaining")

            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"❌ SportsData API error: {e}")
            raise

    def get_games_by_date(self, date: str) -> List[SportsDataGame]:
        """
        Get all NBA games for a specific date.

        Args:
            date: Date in YYYYMMMDD format (e.g., "20231225")

        Returns:
            List of games with basic info
        """
        endpoint = f"/GamesByDate/{date}"
        data = self._make_request(endpoint)

        games = []
        for game_data in data:
            games.append(SportsDataGame(
                game_id=str(game_data['GameID']),
                season=game_data['Season'],
                season_type=game_data['SeasonType'],
                status=game_data['Status'],
                home_team=game_data['HomeTeam'],
                away_team=game_data['AwayTeam'],
                home_score=game_data.get('HomeTeamRuns') or game_data.get('HomeScore'),
                away_score=game_data.get('AwayTeamRuns') or game_data.get('AwayScore'),
                date_time=game_data['DateTime'],
                updated=game_data['Updated']
            ))

        return games

    def get_player_stats_by_game(self, game_id: str) -> List[SportsDataPlayerStats]:
        """
        Get detailed player stats for a specific game.

        Args:
            game_id: Sportsdata.io game ID

        Returns:
            List of player statistics
        """
        endpoint = f"/PlayerGameStatsByGameID/{game_id}"
        data = self._make_request(endpoint)

        players = []
        for player_data in data:
            players.append(SportsDataPlayerStats(
                player_id=player_data['PlayerID'],
                name=player_data['Name'],
                team=player_data['Team'],
                position=player_data['Position'],
                points=float(player_data.get('Points', 0)),
                rebounds=float(player_data.get('Rebounds', 0)),
                assists=float(player_data.get('Assists', 0)),
                steals=float(player_data.get('Steals', 0)),
                blocks=float(player_data.get('Blocks', 0)),
                turnovers=float(player_data.get('Turnovers', 0)),
                minutes=player_data.get('Minutes', 0),
                field_goals_made=player_data.get('FieldGoalsMade', 0),
                field_goals_attempted=player_data.get('FieldGoalsAttempted', 0),
                three_pointers_made=player_data.get('ThreePointersMade', 0),
                three_pointers_attempted=player_data.get('ThreePointersAttempted', 0),
                free_throws_made=player_data.get('FreeThrowsMade', 0),
                free_throws_attempted=player_data.get('FreeThrowsAttempted', 0)
            ))

        return players

    def get_season_stats(self, season: str = "2024") -> List[Dict]:
        """
        Get season-long player statistics.

        Args:
            season: NBA season (e.g., "2024" for 2023-24)

        Returns:
            List of player season stats
        """
        endpoint = f"/PlayerSeasonStats/{season}"
        return self._make_request(endpoint)


class SerpApiClient:
    """
    SerpApi client for contextual analysis of prediction misses.

    Use when learning loop identifies anomalies that need investigation.
    """

    BASE_URL = "https://serpapi.com/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_game_context(self, player_name: str, game_date: str,
                          additional_terms: List[str] = None) -> Dict:
        """
        Search for contextual information about a player's performance.

        Args:
            player_name: Player name
            game_date: Game date (YYYY-MM-DD)
            additional_terms: Additional search terms like ["injury", "limited", "rest"]

        Returns:
            Search results with snippets and links
        """
        # Format date for search
        date_obj = datetime.strptime(game_date, "%Y-%m-%d")
        search_date = date_obj.strftime("%B %d, %Y")

        # Build search query
        query_parts = [f'"{player_name}" NBA {search_date}']
        if additional_terms:
            query_parts.extend(additional_terms)

        query = " ".join(query_parts)

        params = {
            "api_key": self.api_key,
            "q": query,
            "tbs": "qdr:m",  # Past month
            "num": 5  # Limit results
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"❌ SerpApi error: {e}")
            return {"error": str(e)}

    def extract_context_snippets(self, search_results: Dict) -> List[str]:
        """Extract relevant text snippets from search results."""
        snippets = []

        if "organic_results" in search_results:
            for result in search_results["organic_results"][:3]:  # Top 3 results
                if "snippet" in result:
                    snippets.append(result["snippet"])

        return snippets


class EnhancedUFALearningLoop(UFALearningLoop):
    """
    Enhanced learning loop with external API integrations.

    Extends the base UFALearningLoop with Sportsdata.io for bulk historical
    data and SerpApi for contextual anomaly investigation.
    """

    def __init__(self, data_dir: str = "data_center/results",
                 sportsdata_key: str = None, serpapi_key: str = None):
        super().__init__(data_dir)

        # Load API keys from environment if not provided
        self.sportsdata_key = sportsdata_key or os.getenv("SPORTSDATA_API_KEY")
        self.serpapi_key = serpapi_key or os.getenv("SERPAPI_API_KEY")

        # Initialize API clients
        self.sportsdata = SportsDataAPI(self.sportsdata_key) if self.sportsdata_key else None
        self.serpapi = SerpApiClient(self.serpapi_key) if self.serpapi_key else None

    async def run_enhanced_learning(self, date: str = None) -> Dict:
        """
        Enhanced learning with external data integration.

        Includes:
        1. Standard pattern analysis
        2. Historical performance context
        3. Anomaly investigation with SerpApi
        """
        # Run standard learning analysis
        report = await self.run_nightly_learning(date)

        enhanced_results = {
            "standard_report": report,
            "historical_context": {},
            "anomaly_investigations": []
        }

        # Add historical context if APIs available
        if self.sportsdata:
            enhanced_results["historical_context"] = await self._gather_historical_context(date)

        # Investigate anomalies with SerpApi
        if self.serpapi and report.anomalies:
            enhanced_results["anomaly_investigations"] = await self._investigate_anomalies_with_context(report.anomalies)

        return enhanced_results

    async def _gather_historical_context(self, target_date: str) -> Dict:
        """Gather historical performance context using Sportsdata.io."""
        context = {
            "season_stats": {},
            "recent_games": {},
            "trends": {}
        }

        if not self.sportsdata:
            return context

        try:
            # Get recent games data for context
            # This would be more comprehensive in full implementation
            context["api_status"] = "available"
            context["note"] = "Historical context gathering not yet fully implemented"

        except Exception as e:
            context["error"] = str(e)

        return context

    async def _investigate_anomalies_with_context(self, anomalies: List[Dict]) -> List[Dict]:
        """Investigate anomalies using SerpApi for contextual information."""
        investigations = []

        if not self.serpapi:
            return investigations

        for anomaly in anomalies[:3]:  # Limit to top 3 anomalies
            player = anomaly["player"]
            date = anomaly["date"]

            # Search for context
            search_results = self.serpapi.search_game_context(player, date)

            if "error" not in search_results:
                snippets = self.serpapi.extract_context_snippets(search_results)

                investigation = {
                    "player": player,
                    "date": date,
                    "anomaly": anomaly,
                    "context_snippets": snippets,
                    "search_query": search_results.get("search_parameters", {}).get("q", ""),
                    "potential_causes": self._analyze_context_snippets(snippets, player)
                }
                investigations.append(investigation)

        return investigations

    def _analyze_context_snippets(self, snippets: List[str], player: str) -> List[str]:
        """Analyze context snippets to identify potential causes of misses."""
        causes = []

        for snippet in snippets:
            snippet_lower = snippet.lower()

            # Look for common reasons
            if any(term in snippet_lower for term in ["injury", "injured", "sprain", "strain"]):
                causes.append("Injury mentioned")
            if any(term in snippet_lower for term in ["rest", "rested", "resting"]):
                causes.append("Rest mentioned")
            if any(term in snippet_lower for term in ["limited", "minute restriction", "minutes limited"]):
                causes.append("Limited minutes")
            if any(term in snippet_lower for term in ["illness", "sick", "flu", "virus"]):
                causes.append("Illness mentioned")
            if any(term in snippet_lower for term in ["personal", "family", "emergency"]):
                causes.append("Personal reasons")

        return list(set(causes))  # Remove duplicates


# Integration example
async def example_integration():
    """
    Example of how to integrate the enhanced learning loop.

    This shows the complete workflow from data gathering to analysis.
    """

    # Initialize enhanced learning loop
    learning_loop = EnhancedUFALearningLoop(
        sportsdata_key=os.getenv("SPORTSDATA_API_KEY"),
        serpapi_key=os.getenv("SERPAPI_API_KEY")
    )

    # Run enhanced analysis
    results = await learning_loop.run_enhanced_learning()

    # Process results
    report = results["standard_report"]

    print(f"📊 Learning Analysis Complete")
    print(f"Win Rate: {report.overall_win_rate:.1%}")
    print(f"Patterns Found: {len(report.patterns)}")
    print(f"Anomalies: {len(report.anomalies)}")

    # Show anomaly investigations
    for investigation in results.get("anomaly_investigations", []):
        print(f"\n🔍 Investigation: {investigation['player']}")
        print(f"Potential causes: {investigation.get('potential_causes', [])}")
        if investigation.get("context_snippets"):
            print(f"Context: {investigation['context_snippets'][0][:100]}...")

    return results


# Configuration template
CONFIG_TEMPLATE = """
# .env file configuration for UFA Learning System

# Sportsdata.io API (for bulk historical data)
# Sign up: https://sportsdata.io/
# Free tier: 1000 calls/day
SPORTSDATA_API_KEY=your_sportsdata_api_key_here

# SerpApi (for contextual analysis of anomalies)
# Sign up: https://serpapi.com/
# Free tier: 100 searches/month
SERPAPI_API_KEY=your_serpapi_api_key_here

# Database configuration (optional - for production)
# DATABASE_URL=postgresql://user:pass@localhost:5432/ufa_results
# Or for SQLite: DATABASE_URL=sqlite:///ufa_results.db
"""


if __name__ == "__main__":
    print("UFA Learning System Integration Guide")
    print("=" * 50)
    print("1. Set up API keys in .env file:")
    print(CONFIG_TEMPLATE)
    print("\n2. Run enhanced learning analysis:")
    print("   asyncio.run(example_integration())")
    print("\n3. Integrate into daily pipeline:")
    print("   - Add to daily_pipeline.py")
    print("   - Schedule nightly learning runs")
    print("   - Store results for model refinement")