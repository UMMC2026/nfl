#!/usr/bin/env python3
"""src/sources/odds_api_results.py

Automated postgame result ingestion via OddsAPI /scores endpoint.

This module:
1. Fetches completed game scores from OddsAPI
2. Retrieves player stats from box scores
3. Matches results to outstanding picks in calibration tracker
4. Auto-updates pick results for automated calibration
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sources.odds_api import OddsApiClient
from src.sources.odds_api_box_scores import BoxScoreRouter
from calibration.unified_tracker import CalibrationTracker

logger = logging.getLogger(__name__)


class OddsApiResultsIngester:
    """Automates postgame result ingestion from OddsAPI scores endpoint."""
    
    def __init__(self, sport_key: str = "basketball_nba"):
        """
        Initialize results ingester.
        
        Args:
            sport_key: OddsAPI sport key (default: basketball_nba)
        """
        self.sport_key = sport_key
        self.odds_client = OddsApiClient()
        self.tracker = CalibrationTracker()
        self.box_score_router = BoxScoreRouter()
        
        # Sport normalization for calibration tracker
        self.sport_map = {
            "basketball_nba": "NBA",
            "basketball_ncaab": "CBB",
            "icehockey_nhl": "NHL",
            "tennis_atp": "Tennis",
            "tennis_wta": "Tennis",
            "golf_pga": "Golf"
        }
    
    def fetch_completed_games(
        self, 
        days_from: int = 1
    ) -> List[Dict]:
        """
        Fetch completed games from OddsAPI scores endpoint.
        
        Args:
            days_from: Number of days to look back (1-3, default: 1)
            
        Returns:
            List of completed game score objects
        """
        try:
            logger.info(f"Fetching scores for {self.sport_key} (last {days_from} days)")
            scores, quota = self.odds_client.get_scores(
                sport_key=self.sport_key,
                days_from=days_from
            )
            
            logger.info(
                f"Retrieved {len(scores)} events "
                f"(quota: {quota.remaining} remaining, {quota.last_cost} cost)"
            )
            
            # Filter to completed games only
            completed = [
                s for s in scores 
                if s.get("completed", False)
            ]
            
            logger.info(f"Found {len(completed)} completed games")
            return completed
            
        except Exception as e:
            logger.error(f"Error fetching scores: {e}")
            return []
    
    def extract_game_results(
        self, 
        score_obj: Dict
    ) -> Optional[Dict[str, any]]:
        """
        Extract structured game result from OddsAPI score object.
        
        Args:
            score_obj: OddsAPI score response object
            
        Returns:
            Structured game result or None if incomplete
        """
        try:
            event_id = score_obj.get("id")
            home_team = score_obj.get("home_team")
            away_team = score_obj.get("away_team")
            
            # Score structure in OddsAPI v4
            scores = score_obj.get("scores")
            if not scores or len(scores) < 2:
                logger.warning(f"Incomplete scores for event {event_id}")
                return None
            
            # Parse scores (scores is list of [home_score_obj, away_score_obj])
            home_score = None
            away_score = None
            
            for team_score in scores:
                team_name = team_score.get("name")
                score = team_score.get("score")
                
                if team_name == home_team:
                    home_score = score
                elif team_name == away_team:
                    away_score = score
            
            if home_score is None or away_score is None:
                logger.warning(f"Could not parse scores for event {event_id}")
                return None
            
            return {
                "event_id": event_id,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": int(home_score),
                "away_score": int(away_score),
                "commence_time": score_obj.get("commence_time"),
                "completed": True
            }
            
        except Exception as e:
            logger.error(f"Error extracting game result: {e}")
            return None
    
    def get_outstanding_picks(
        self, 
        sport: str,
        game_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get picks that need results from calibration tracker.
        
        Args:
            sport: Sport name (NBA, CBB, etc.)
            game_date: Optional date filter for picks
            
        Returns:
            List of picks missing results (actual = None)
        """
        outstanding = []
        
        for pick in self.tracker.picks:
            # Filter by sport
            if pick.sport != sport:
                continue
            
            # Skip if result already recorded
            if pick.actual is not None:
                continue
            
            # Optional date filter
            if game_date:
                pick_date = datetime.fromisoformat(pick.run_id.split("_")[0])
                if pick_date.date() != game_date.date():
                    continue
            
            outstanding.append({
                "pick_id": pick.pick_id,
                "entity": pick.entity,
                "market": pick.market,
                "line": pick.line,
                "direction": pick.direction,
                "probability": pick.probability,
                "tier": pick.tier
            })
        
        return outstanding
    
    def fetch_player_stats(
        self,
        player_name: str,
        team: str,
        game_result: Dict
    ) -> Optional[Dict[str, float]]:
        """
        Fetch player box score stats for a completed game.
        
        Routes to sport-specific box score fetchers via BoxScoreRouter.
        
        Args:
            player_name: Player name
            team: Team abbreviation
            game_result: Game result dict with event_id, teams, scores, commence_time
            
        Returns:
            Dict of stat_type -> actual_value or None if not found
        """
        sport = self.sport_map.get(self.sport_key, "NBA")
        event_id = game_result.get("event_id")
        
        # Parse game date from commence_time
        game_date = None
        if game_result.get("commence_time"):
            try:
                game_date = datetime.fromisoformat(
                    game_result["commence_time"].replace("Z", "+00:00")
                )
            except Exception as e:
                logger.warning(f"Could not parse commence_time: {e}")
        
        try:
            stats = self.box_score_router.fetch_stats(
                sport=sport,
                event_id=event_id,
                player_name=player_name,
                team=team,
                game_date=game_date
            )
            
            if stats:
                logger.debug(
                    f"Fetched {len(stats)} stats for {player_name} in {event_id}"
                )
            
            return stats
            
        except Exception as e:
            logger.error(
                f"Error fetching stats for {player_name} ({team}): {e}"
            )
            return None
    
    def update_pick_results(
        self,
        completed_games: List[Dict],
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Update calibration tracker with results from completed games.
        
        Args:
            completed_games: List of completed game results
            dry_run: If True, don't save changes (default: False)
            
        Returns:
            Summary stats dict with counts of updated/skipped picks
        """
        sport = self.sport_map.get(self.sport_key, "NBA")
        stats = {
            "total_games": len(completed_games),
            "picks_updated": 0,
            "picks_skipped": 0,
            "errors": 0
        }
        
        # Get outstanding picks for this sport
        outstanding = self.get_outstanding_picks(sport)
        logger.info(f"Found {len(outstanding)} outstanding picks for {sport}")
        
        if not outstanding:
            logger.info("No outstanding picks to update")
            return stats
        
        # Index picks by player for faster lookup
        picks_by_player: Dict[str, List[Dict]] = {}
        for pick in outstanding:
            player = pick["entity"]
            if player not in picks_by_player:
                picks_by_player[player] = []
            picks_by_player[player].append(pick)
        
        # Process each completed game
        for game in completed_games:
            try:
                logger.info(
                    f"Processing: {game['away_team']} @ {game['home_team']} "
                    f"({game['away_score']}-{game['home_score']})"
                )
                
                # For each player with outstanding picks
                for player_name, player_picks in picks_by_player.items():
                    # Fetch player stats for this game
                    player_stats = self.fetch_player_stats(
                        player_name,
                        game["home_team"],  # Need to determine player's team
                        game
                    )
                    
                    if not player_stats:
                        stats["picks_skipped"] += len(player_picks)
                        continue
                    
                    # Update each pick with actual result
                    for pick in player_picks:
                        stat_type = pick["market"]
                        actual_value = player_stats.get(stat_type)
                        
                        if actual_value is None:
                            logger.warning(
                                f"No {stat_type} stat found for {player_name}"
                            )
                            stats["picks_skipped"] += 1
                            continue
                        
                        # Update tracker
                        if not dry_run:
                            self.tracker.update_result(
                                pick["pick_id"], 
                                actual_value
                            )
                            logger.info(
                                f"✓ Updated {player_name} {stat_type}: "
                                f"{actual_value} (line: {pick['line']}, "
                                f"dir: {pick['direction']})"
                            )
                        else:
                            logger.info(
                                f"[DRY RUN] Would update {player_name} {stat_type}: "
                                f"{actual_value}"
                            )
                        
                        stats["picks_updated"] += 1
                
            except Exception as e:
                logger.error(f"Error processing game {game.get('event_id')}: {e}")
                stats["errors"] += 1
        
        return stats
    
    def run_auto_ingestion(
        self,
        days_from: int = 1,
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Run automated result ingestion pipeline.
        
        Args:
            days_from: Days to look back for completed games (1-3)
            dry_run: If True, don't save changes
            
        Returns:
            Summary stats dict
        """
        logger.info("=" * 60)
        logger.info("AUTOMATED POSTGAME RESULT INGESTION")
        logger.info(f"Sport: {self.sport_key} | Days: {days_from}")
        if dry_run:
            logger.info("MODE: DRY RUN (no changes saved)")
        logger.info("=" * 60)
        
        # Step 1: Fetch completed games
        completed_games = self.fetch_completed_games(days_from)
        
        if not completed_games:
            logger.info("No completed games found")
            return {"total_games": 0, "picks_updated": 0}
        
        # Step 2: Extract structured results
        game_results = []
        for score_obj in completed_games:
            result = self.extract_game_results(score_obj)
            if result:
                game_results.append(result)
        
        logger.info(f"Extracted {len(game_results)} valid game results")
        
        # Step 3: Update pick results
        stats = self.update_pick_results(game_results, dry_run=dry_run)
        
        # Summary
        logger.info("=" * 60)
        logger.info("INGESTION SUMMARY")
        logger.info(f"Games processed: {stats['total_games']}")
        logger.info(f"Picks updated: {stats['picks_updated']}")
        logger.info(f"Picks skipped: {stats['picks_skipped']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("=" * 60)
        
        return stats


def main():
    """CLI entry point for manual execution."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Automated postgame result ingestion via OddsAPI"
    )
    parser.add_argument(
        "--sport",
        default="basketball_nba",
        help="OddsAPI sport key (default: basketball_nba)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Days to look back for completed games (1-3, default: 1)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without saving"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Run ingestion
    ingester = OddsApiResultsIngester(sport_key=args.sport)
    stats = ingester.run_auto_ingestion(
        days_from=args.days,
        dry_run=args.dry_run
    )
    
    # Exit code based on results
    if stats["errors"] > 0:
        sys.exit(1)
    elif stats["picks_updated"] == 0:
        logger.warning("No picks were updated")
        sys.exit(2)
    else:
        logger.info("✓ Ingestion complete")
        sys.exit(0)


if __name__ == "__main__":
    main()
