#!/usr/bin/env python3
"""src/sources/odds_api_box_scores.py

Sport-specific box score fetchers for automated result ingestion.

Each sport has a dedicated fetcher that retrieves actual player stats
from completed games to auto-resolve pick results.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class NBABoxScoreFetcher:
    """Fetch NBA player stats from completed games."""
    
    def __init__(self):
        try:
            from nba_api.stats.endpoints import boxscoretraditionalv2, leaguegamefinder
            self.BoxScore = boxscoretraditionalv2.BoxScoreTraditionalV2
            self.GameFinder = leaguegamefinder.LeagueGameFinder
        except ImportError as e:
            logger.error(f"nba_api not available: {e}")
            self.BoxScore = None
            self.GameFinder = None
    
    def find_game_id(
        self, 
        team_abbrev: str, 
        game_date: datetime
    ) -> Optional[str]:
        """
        Find NBA game ID for a team on a specific date.
        
        Args:
            team_abbrev: Team abbreviation (e.g., 'LAL', 'BOS')
            game_date: Date of the game
            
        Returns:
            Game ID or None if not found
        """
        if not self.GameFinder:
            return None
        
        try:
            date_str = game_date.strftime("%Y-%m-%d")
            
            # Query games for the team on that date
            games = self.GameFinder(
                team_id_nullable=None,
                date_from_nullable=date_str,
                date_to_nullable=date_str
            ).get_data_frames()[0]
            
            team_games = games[games['TEAM_ABBREVIATION'] == team_abbrev]
            
            if len(team_games) == 0:
                logger.warning(f"No game found for {team_abbrev} on {date_str}")
                return None
            
            game_id = team_games.iloc[0]['GAME_ID']
            return game_id
            
        except Exception as e:
            logger.error(f"Error finding game ID: {e}")
            return None
    
    def fetch_player_stats(
        self, 
        game_id: str, 
        player_name: str
    ) -> Optional[Dict[str, float]]:
        """
        Fetch player stats from NBA game box score.
        
        Args:
            game_id: NBA game ID
            player_name: Player full name
            
        Returns:
            Dict mapping stat types to actual values or None
        """
        if not self.BoxScore:
            return None
        
        try:
            # Fetch box score
            box = self.BoxScore(game_id=game_id)
            player_stats = box.player_stats.get_data_frame()
            
            # Find player row
            player_row = player_stats[
                player_stats['PLAYER_NAME'].str.lower() == player_name.lower()
            ]
            
            if len(player_row) == 0:
                logger.warning(f"Player {player_name} not found in game {game_id}")
                return None
            
            row = player_row.iloc[0]
            
            # Map to our canonical stat types
            stats = {
                "points": float(row['PTS']),
                "rebounds": float(row['REB']),
                "assists": float(row['AST']),
                "3pm": float(row['FG3M']),
                "blocks": float(row['BLK']),
                "steals": float(row['STL']),
                "turnovers": float(row['TO']),
            }
            
            # Computed combo stats
            stats["blocks+steals"] = stats["blocks"] + stats["steals"]
            stats["pra"] = stats["points"] + stats["rebounds"] + stats["assists"]
            stats["points+assists"] = stats["points"] + stats["assists"]
            stats["points+rebounds"] = stats["points"] + stats["rebounds"]
            stats["rebounds+assists"] = stats["rebounds"] + stats["assists"]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error fetching box score for game {game_id}: {e}")
            return None


class NHLBoxScoreFetcher:
    """Fetch NHL player/goalie stats from completed games."""
    
    def __init__(self):
        """Initialize NHL stats fetcher."""
        pass
    
    def fetch_player_stats(
        self,
        game_id: str,
        player_name: str
    ) -> Optional[Dict[str, float]]:
        """
        Fetch NHL player stats from game.
        
        TODO: Implement using NHL API game feed endpoint:
        https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore
        
        Args:
            game_id: NHL game ID
            player_name: Player name
            
        Returns:
            Dict with stats (sog, goals, assists, etc.) or None
        """
        logger.warning("NHL box score fetching not yet implemented")
        return None


class TennisMatchScoreFetcher:
    """Fetch tennis match scores and stats."""
    
    def __init__(self):
        """Initialize tennis stats fetcher."""
        pass
    
    def fetch_match_stats(
        self,
        match_id: str,
        player_name: str
    ) -> Optional[Dict[str, float]]:
        """
        Fetch tennis player match stats.
        
        For tennis, the OddsAPI scores endpoint provides:
        - Total games won
        - Sets won
        
        Additional stats (aces, double faults) require integration with:
        - Tennis-Data.co.uk
        - ATP/WTA official APIs
        - Or Sackmann tennis_atp/tennis_wta datasets
        
        Args:
            match_id: Match identifier
            player_name: Player name
            
        Returns:
            Dict with match stats or None
        """
        logger.warning("Tennis match stats fetching not yet implemented")
        return None


class GolfTournamentScoreFetcher:
    """Fetch golf tournament scores and finishing positions."""
    
    def __init__(self):
        """Initialize golf stats fetcher."""
        self.datagolf_api_key = None  # Set from env if available
    
    def fetch_player_result(
        self,
        tournament_id: str,
        player_name: str
    ) -> Optional[Dict[str, float]]:
        """
        Fetch golf player tournament result.
        
        TODO: Implement using DataGolf API:
        GET https://feeds.datagolf.com/preds/live-tournament-stats
        
        Args:
            tournament_id: Tournament identifier
            player_name: Player name
            
        Returns:
            Dict with finishing_position, total_score, etc. or None
        """
        logger.warning("Golf tournament results fetching not yet implemented")
        return None


class BoxScoreRouter:
    """Routes box score fetching to sport-specific implementations."""
    
    def __init__(self):
        """Initialize all sport-specific fetchers."""
        self.nba_fetcher = NBABoxScoreFetcher()
        self.nhl_fetcher = NHLBoxScoreFetcher()
        self.tennis_fetcher = TennisMatchScoreFetcher()
        self.golf_fetcher = GolfTournamentScoreFetcher()
    
    def fetch_stats(
        self,
        sport: str,
        event_id: str,
        player_name: str,
        team: Optional[str] = None,
        game_date: Optional[datetime] = None
    ) -> Optional[Dict[str, float]]:
        """
        Route to appropriate sport-specific fetcher.
        
        Args:
            sport: Sport name (NBA, NHL, Tennis, Golf)
            event_id: Event/game identifier
            player_name: Player name
            team: Team abbreviation (for NBA/NHL)
            game_date: Game date (for NBA/NHL game ID lookup)
            
        Returns:
            Dict of stat_type -> actual_value or None
        """
        sport = sport.upper()
        
        if sport == "NBA":
            # For NBA, we need to find the game ID first
            if not team or not game_date:
                logger.error("NBA requires team and game_date")
                return None
            
            game_id = self.nba_fetcher.find_game_id(team, game_date)
            if not game_id:
                return None
            
            return self.nba_fetcher.fetch_player_stats(game_id, player_name)
        
        elif sport == "NHL":
            return self.nhl_fetcher.fetch_player_stats(event_id, player_name)
        
        elif sport == "TENNIS":
            return self.tennis_fetcher.fetch_match_stats(event_id, player_name)
        
        elif sport == "GOLF":
            return self.golf_fetcher.fetch_player_result(event_id, player_name)
        
        else:
            logger.error(f"Unsupported sport: {sport}")
            return None
