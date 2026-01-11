"""
Automatic results tracking and credibility metrics.

Fetches actual stat lines and grades signals after games complete.
"""
import os
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from ufa.db import SessionLocal
from ufa.models.user import Signal, SignalResult, DailyMetrics

logger = logging.getLogger(__name__)


class ResultsTracker:
    """
    Track and grade signal results using live stats.
    """
    
    def __init__(self):
        self.db: Session = SessionLocal()
    
    def close(self):
        self.db.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def fetch_actual_stat(
        self, 
        league: str, 
        player: str, 
        stat: str, 
        game_date: date
    ) -> Optional[float]:
        """
        Fetch actual stat value from API.
        Returns None if game not complete or data unavailable.
        """
        try:
            if league == "NBA":
                return self._fetch_nba_stat(player, stat, game_date)
            elif league == "NFL":
                return self._fetch_nfl_stat(player, stat, game_date)
            elif league == "CFB":
                return self._fetch_cfb_stat(player, stat, game_date)
            else:
                logger.warning(f"Unknown league: {league}")
                return None
        except Exception as e:
            logger.error(f"Error fetching stat for {player}: {e}")
            return None
    
    def _fetch_nba_stat(self, player: str, stat: str, game_date: date) -> Optional[float]:
        """Fetch NBA stat from nba_api."""
        try:
            from nba_api.stats.endpoints import playergamelog
            from nba_api.stats.static import players
            
            # Find player ID
            player_info = players.find_players_by_full_name(player)
            if not player_info:
                logger.warning(f"NBA player not found: {player}")
                return None
            
            player_id = player_info[0]["id"]
            
            # Get game log
            gamelog = playergamelog.PlayerGameLog(
                player_id=player_id,
                season="2024-25",
                season_type_all_star="Regular Season",
            )
            df = gamelog.get_data_frames()[0]
            
            if df.empty:
                return None
            
            # Filter to specific date
            df["GAME_DATE"] = df["GAME_DATE"].apply(
                lambda x: datetime.strptime(x, "%b %d, %Y").date()
            )
            game_row = df[df["GAME_DATE"] == game_date]
            
            if game_row.empty:
                return None
            
            # Map stat to column
            stat_map = {
                "points": "PTS",
                "rebounds": "REB",
                "assists": "AST",
                "3pm": "FG3M",
                "steals": "STL",
                "blocks": "BLK",
                "turnovers": "TOV",
                "pts+reb+ast": lambda r: r["PTS"] + r["REB"] + r["AST"],
                "pts+reb": lambda r: r["PTS"] + r["REB"],
                "pts+ast": lambda r: r["PTS"] + r["AST"],
                "reb+ast": lambda r: r["REB"] + r["AST"],
                "stl+blk": lambda r: r["STL"] + r["BLK"],
            }
            
            row = game_row.iloc[0]
            
            if stat in stat_map:
                mapping = stat_map[stat]
                if callable(mapping):
                    return float(mapping(row))
                return float(row[mapping])
            
            logger.warning(f"Unknown NBA stat: {stat}")
            return None
            
        except ImportError:
            logger.warning("nba_api not installed")
            return None
        except Exception as e:
            logger.error(f"NBA stat fetch error: {e}")
            return None
    
    def _fetch_nfl_stat(self, player: str, stat: str, game_date: date) -> Optional[float]:
        """Fetch NFL stat from nfl_data_py or ESPN."""
        try:
            import nfl_data_py as nfl
            
            # Get weekly stats
            year = game_date.year if game_date.month > 6 else game_date.year - 1
            weekly = nfl.import_weekly_data([year])
            
            # Filter to player
            player_data = weekly[
                weekly["player_display_name"].str.lower() == player.lower()
            ]
            
            if player_data.empty:
                return None
            
            # Map stat to column
            stat_map = {
                "pass_yds": "passing_yards",
                "rush_yds": "rushing_yards",
                "rec_yds": "receiving_yards",
                "receptions": "receptions",
                "pass_tds": "passing_tds",
                "rush_tds": "rushing_tds",
                "rec_tds": "receiving_tds",
            }
            
            if stat not in stat_map:
                logger.warning(f"Unknown NFL stat: {stat}")
                return None
            
            col = stat_map[stat]
            
            # Get most recent game (simplified - real implementation would match date)
            latest = player_data.sort_values("week", ascending=False).iloc[0]
            return float(latest[col])
            
        except ImportError:
            logger.warning("nfl_data_py not installed")
            return None
        except Exception as e:
            logger.error(f"NFL stat fetch error: {e}")
            return None
    
    def _fetch_cfb_stat(self, player: str, stat: str, game_date: date) -> Optional[float]:
        """Fetch CFB stat from CFBD API."""
        # Simplified - would need CFBD API implementation
        logger.warning("CFB stat fetching not yet implemented")
        return None
    
    def grade_signal(self, signal: Signal) -> SignalResult:
        """
        Grade a single signal based on actual results.
        """
        if signal.result != SignalResult.PENDING:
            return signal.result
        
        actual = self.fetch_actual_stat(
            signal.league,
            signal.player,
            signal.stat,
            signal.game_date.date() if isinstance(signal.game_date, datetime) else signal.game_date,
        )
        
        if actual is None:
            return SignalResult.PENDING
        
        signal.actual_value = actual
        signal.graded_at = datetime.utcnow()
        
        # Determine result
        if signal.direction == "higher":
            if actual > signal.line:
                signal.result = SignalResult.WIN
            elif actual == signal.line:
                signal.result = SignalResult.PUSH
            else:
                signal.result = SignalResult.LOSS
        else:  # lower
            if actual < signal.line:
                signal.result = SignalResult.WIN
            elif actual == signal.line:
                signal.result = SignalResult.PUSH
            else:
                signal.result = SignalResult.LOSS
        
        self.db.commit()
        return signal.result
    
    def grade_pending_signals(self, game_date: date = None) -> dict:
        """
        Grade all pending signals for a date.
        Returns summary of results.
        """
        if game_date is None:
            game_date = date.today() - timedelta(days=1)  # Grade yesterday's games
        
        # Get pending signals for date
        pending = self.db.execute(
            select(Signal).where(
                and_(
                    Signal.result == SignalResult.PENDING,
                    Signal.game_date >= datetime.combine(game_date, datetime.min.time()),
                    Signal.game_date < datetime.combine(game_date + timedelta(days=1), datetime.min.time()),
                )
            )
        ).scalars().all()
        
        results = {"wins": 0, "losses": 0, "pushes": 0, "pending": 0}
        
        for signal in pending:
            result = self.grade_signal(signal)
            
            if result == SignalResult.WIN:
                results["wins"] += 1
            elif result == SignalResult.LOSS:
                results["losses"] += 1
            elif result == SignalResult.PUSH:
                results["pushes"] += 1
            else:
                results["pending"] += 1
        
        logger.info(f"Graded {len(pending)} signals: {results}")
        return results
    
    def update_daily_metrics(self, target_date: date = None) -> DailyMetrics:
        """
        Calculate and update daily metrics.
        """
        if target_date is None:
            target_date = date.today() - timedelta(days=1)
        
        target_datetime = datetime.combine(target_date, datetime.min.time())
        
        # Get or create metrics record
        metrics = self.db.execute(
            select(DailyMetrics).where(DailyMetrics.date == target_datetime)
        ).scalar_one_or_none()
        
        if not metrics:
            metrics = DailyMetrics(date=target_datetime)
            self.db.add(metrics)
        
        # Get all graded signals for date
        signals = self.db.execute(
            select(Signal).where(
                and_(
                    Signal.game_date >= target_datetime,
                    Signal.game_date < target_datetime + timedelta(days=1),
                    Signal.result != SignalResult.PENDING,
                )
            )
        ).scalars().all()
        
        # Reset counters
        metrics.slam_count = 0
        metrics.slam_wins = 0
        metrics.strong_count = 0
        metrics.strong_wins = 0
        metrics.lean_count = 0
        metrics.lean_wins = 0
        metrics.total_signals = 0
        metrics.total_wins = 0
        metrics.total_losses = 0
        metrics.total_pushes = 0
        
        for signal in signals:
            metrics.total_signals += 1
            
            if signal.result == SignalResult.WIN:
                metrics.total_wins += 1
            elif signal.result == SignalResult.LOSS:
                metrics.total_losses += 1
            elif signal.result == SignalResult.PUSH:
                metrics.total_pushes += 1
            
            # By tier
            if signal.tier == "SLAM":
                metrics.slam_count += 1
                if signal.result == SignalResult.WIN:
                    metrics.slam_wins += 1
            elif signal.tier == "STRONG":
                metrics.strong_count += 1
                if signal.result == SignalResult.WIN:
                    metrics.strong_wins += 1
            elif signal.tier == "LEAN":
                metrics.lean_count += 1
                if signal.result == SignalResult.WIN:
                    metrics.lean_wins += 1
        
        # Calculate ROI (simplified: assuming -110 odds, $100 per play)
        units_wagered = metrics.total_wins + metrics.total_losses  # pushes don't count
        units_won = (metrics.total_wins * 0.91) - metrics.total_losses  # -110 odds
        metrics.units_wagered = float(units_wagered)
        metrics.units_won = float(units_won)
        metrics.roi_percent = (units_won / units_wagered * 100) if units_wagered > 0 else 0.0
        
        self.db.commit()
        logger.info(f"Updated metrics for {target_date}: {metrics.total_wins}-{metrics.total_losses}")
        
        return metrics
    
    def get_credibility_stats(self, days: int = 30) -> dict:
        """
        Get comprehensive credibility statistics.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get graded signals
        signals = self.db.execute(
            select(Signal).where(
                and_(
                    Signal.graded_at >= cutoff,
                    Signal.result != SignalResult.PENDING,
                )
            )
        ).scalars().all()
        
        if not signals:
            return {
                "period_days": days,
                "total_picks": 0,
                "win_rate": 0,
                "roi_percent": 0,
                "by_tier": {},
            }
        
        total = len(signals)
        wins = sum(1 for s in signals if s.result == SignalResult.WIN)
        losses = sum(1 for s in signals if s.result == SignalResult.LOSS)
        
        # By tier
        tier_stats = {}
        for tier in ["SLAM", "STRONG", "LEAN"]:
            tier_signals = [s for s in signals if s.tier == tier]
            tier_wins = sum(1 for s in tier_signals if s.result == SignalResult.WIN)
            tier_losses = sum(1 for s in tier_signals if s.result == SignalResult.LOSS)
            tier_total = tier_wins + tier_losses
            
            tier_stats[tier] = {
                "total": len(tier_signals),
                "wins": tier_wins,
                "losses": tier_losses,
                "win_rate": (tier_wins / tier_total * 100) if tier_total > 0 else 0,
            }
        
        # Overall ROI
        total_wl = wins + losses
        roi = ((wins * 0.91) - losses) / total_wl * 100 if total_wl > 0 else 0
        
        return {
            "period_days": days,
            "total_picks": total,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total_wl * 100) if total_wl > 0 else 0,
            "roi_percent": roi,
            "by_tier": tier_stats,
        }


def run_grading_job():
    """
    Run as scheduled job to grade yesterday's signals.
    """
    with ResultsTracker() as tracker:
        yesterday = date.today() - timedelta(days=1)
        
        # Grade signals
        results = tracker.grade_pending_signals(yesterday)
        
        # Update metrics
        tracker.update_daily_metrics(yesterday)
        
        print(f"Grading complete for {yesterday}: {results}")


if __name__ == "__main__":
    run_grading_job()
