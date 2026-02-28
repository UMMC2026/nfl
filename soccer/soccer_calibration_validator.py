"""
Soccer Calibration Validation Framework
========================================

Validates model calibration to prevent overconfidence:
- Brier Score (accuracy)
- Expected Calibration Error (ECE)
- Reliability diagrams
- Walk-forward validation
- Confidence tier performance

Author: Production Sports Betting System
Date: 2026-02-01
"""

import logging
import json
import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Prediction:
    """Single prediction record."""
    player_name: str
    opponent: str
    stat_type: str
    line: float
    direction: str
    predicted_prob: float
    tier: str
    timestamp: datetime
    
    # Outcome (filled after match)
    actual_outcome: Optional[int] = None  # 1 = hit, 0 = miss
    actual_stat_value: Optional[float] = None
    
    # Metadata
    match_id: Optional[str] = None
    book: Optional[str] = None
    competition: Optional[str] = None


class CalibrationValidator:
    """
    Validate model calibration and track performance.
    
    Key Metrics:
    
    1. Brier Score
       - Measures accuracy of probabilistic predictions
       - Formula: BS = (1/n) sum(predicted_prob - actual)^2
       - Range: 0 (perfect) to 1 (worst)
       - Target: < 0.25 (better than random)
    
    2. Expected Calibration Error (ECE)
       - Measures calibration (predicted vs actual hit rate)
       - Bins predictions by confidence level
       - Target: < 0.10 (within 10%)
    
    3. Log Loss
       - Penalizes confident wrong predictions more heavily
       - Formula: -sum[y*log(p) + (1-y)*log(1-p)]
       - Target: < 0.65
    
    4. ROI
       - Return on investment at standard odds (-110)
       - Target: > +3%
    """
    
    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize calibration validator.
        
        Args:
            output_dir: Directory to save calibration results
        """
        if output_dir is None:
            # Use project directory
            output_dir = Path(__file__).parent / "calibration_results"
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.predictions: List[Prediction] = []
        self.history_file = self.output_dir / "calibration_history.json"
        
        # Load existing history
        self._load_history()
        
        logger.info(f"CalibrationValidator initialized: {len(self.predictions)} historical predictions")
    
    def _load_history(self):
        """Load prediction history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        # Convert timestamp string back to datetime
                        item['timestamp'] = datetime.fromisoformat(item['timestamp'])
                        self.predictions.append(Prediction(**item))
                logger.info(f"Loaded {len(self.predictions)} historical predictions")
            except Exception as e:
                logger.error(f"Failed to load history: {e}")
                self.predictions = []
        else:
            self.predictions = []
    
    def _save_history(self):
        """Save prediction history to file."""
        try:
            data = []
            for pred in self.predictions:
                pred_dict = asdict(pred)
                # Convert datetime to string for JSON serialization
                pred_dict['timestamp'] = pred.timestamp.isoformat()
                data.append(pred_dict)
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(self.predictions)} predictions to history")
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
    
    def add_prediction(
        self,
        player_name: str,
        opponent: str,
        stat_type: str,
        line: float,
        direction: str,
        predicted_prob: float,
        tier: str,
        **kwargs
    ):
        """
        Add a new prediction (before outcome is known).
        
        Args:
            player_name: Player name
            opponent: Opponent team
            stat_type: Stat being predicted
            line: Betting line
            direction: "OVER" or "UNDER"
            predicted_prob: Model's predicted probability (0-1)
            tier: Confidence tier (e.g., "ELITE", "STRONG")
            **kwargs: Additional metadata
        """
        pred = Prediction(
            player_name=player_name,
            opponent=opponent,
            stat_type=stat_type,
            line=line,
            direction=direction,
            predicted_prob=predicted_prob,
            tier=tier,
            timestamp=datetime.now(),
            **kwargs
        )
        
        self.predictions.append(pred)
        self._save_history()
        
        logger.info(
            f"[PREDICTION] {player_name} {stat_type} {direction} {line} "
            f"({predicted_prob:.1%} - {tier})"
        )
    
    def update_outcome(
        self,
        player_name: str,
        timestamp: datetime,
        actual_outcome: int,
        actual_stat_value: float
    ):
        """
        Update prediction with actual outcome.
        
        Args:
            player_name: Player name
            timestamp: When prediction was made
            actual_outcome: 1 if hit, 0 if miss
            actual_stat_value: Actual stat value from match
        """
        # Find matching prediction
        for pred in self.predictions:
            if (pred.player_name == player_name and 
                pred.timestamp == timestamp and
                pred.actual_outcome is None):
                
                pred.actual_outcome = actual_outcome
                pred.actual_stat_value = actual_stat_value
                
                self._save_history()
                
                result_str = "HIT" if actual_outcome == 1 else "MISS"
                logger.info(
                    f"[OUTCOME] {player_name} {pred.stat_type}: "
                    f"predicted {pred.predicted_prob:.1%}, {result_str}"
                )
                return
        
        logger.warning(f"No matching prediction found for {player_name}")
    
    def calculate_brier_score(
        self,
        predictions: Optional[List[Prediction]] = None
    ) -> float:
        """
        Calculate Brier Score.
        
        Formula: BS = (1/n) sum(predicted_prob - actual)^2
        
        Args:
            predictions: List of predictions (defaults to all with outcomes)
        
        Returns:
            Brier score (0-1, lower is better)
        
        Interpretation:
            < 0.20: Excellent
            0.20-0.25: Good (better than random)
            0.25-0.30: Acceptable
            > 0.30: Poor (needs recalibration)
        """
        if predictions is None:
            predictions = [p for p in self.predictions if p.actual_outcome is not None]
        
        if not predictions:
            logger.warning("No predictions with outcomes for Brier score")
            return 0.25
        
        squared_errors = [
            (pred.predicted_prob - pred.actual_outcome) ** 2
            for pred in predictions
        ]
        
        brier_score = sum(squared_errors) / len(squared_errors)
        
        logger.info(f"Brier Score: {brier_score:.4f} (n={len(predictions)})")
        return brier_score
    
    def calculate_ece(
        self,
        predictions: Optional[List[Prediction]] = None,
        n_bins: int = 10
    ) -> Tuple[float, List[Dict]]:
        """
        Calculate Expected Calibration Error.
        
        Bins predictions by confidence, compares predicted vs actual hit rate.
        
        Args:
            predictions: List of predictions (defaults to all with outcomes)
            n_bins: Number of calibration bins
        
        Returns:
            Tuple of (ECE value, list of bin details)
        
        Interpretation:
            < 0.05: Excellent calibration
            0.05-0.10: Good calibration
            0.10-0.15: Needs improvement
            > 0.15: Poor calibration (systematic bias)
        """
        if predictions is None:
            predictions = [p for p in self.predictions if p.actual_outcome is not None]
        
        if not predictions:
            logger.warning("No predictions with outcomes for ECE")
            return 0.0, []
        
        # Create bins
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bins = []
        
        for i in range(n_bins):
            bin_lower = bin_edges[i]
            bin_upper = bin_edges[i + 1]
            
            # Get predictions in this bin
            bin_preds = [
                p for p in predictions
                if bin_lower <= p.predicted_prob < bin_upper
            ]
            
            if not bin_preds:
                continue
            
            # Calculate bin statistics
            avg_predicted = sum(p.predicted_prob for p in bin_preds) / len(bin_preds)
            avg_actual = sum(p.actual_outcome for p in bin_preds) / len(bin_preds)
            bin_error = abs(avg_predicted - avg_actual)
            
            bins.append({
                "bin_range": f"{bin_lower:.1f}-{bin_upper:.1f}",
                "n_predictions": len(bin_preds),
                "avg_predicted": avg_predicted,
                "avg_actual": avg_actual,
                "error": bin_error
            })
        
        # Calculate weighted ECE
        total_preds = len(predictions)
        ece = sum(
            (bin_data["n_predictions"] / total_preds) * bin_data["error"]
            for bin_data in bins
        )
        
        logger.info(f"ECE: {ece:.4f} across {len(bins)} bins")
        return ece, bins
    
    def calculate_log_loss(
        self,
        predictions: Optional[List[Prediction]] = None
    ) -> float:
        """
        Calculate Log Loss (cross-entropy).
        
        Formula: -sum[y*log(p) + (1-y)*log(1-p)]
        
        Heavily penalizes confident wrong predictions.
        """
        if predictions is None:
            predictions = [p for p in self.predictions if p.actual_outcome is not None]
        
        if not predictions:
            logger.warning("No predictions with outcomes for log loss")
            return 0.69  # Random guessing
        
        log_losses = []
        for pred in predictions:
            y = pred.actual_outcome
            p = max(1e-15, min(1 - 1e-15, pred.predicted_prob))  # Avoid log(0)
            
            loss = -(y * np.log(p) + (1 - y) * np.log(1 - p))
            log_losses.append(loss)
        
        avg_log_loss = sum(log_losses) / len(log_losses)
        
        logger.info(f"Log Loss: {avg_log_loss:.4f}")
        return avg_log_loss
    
    def calculate_roi(
        self,
        predictions: Optional[List[Prediction]] = None,
        odds: float = -110
    ) -> float:
        """
        Calculate Return on Investment.
        
        Assumes flat betting at given odds.
        
        Args:
            predictions: List of predictions
            odds: American odds (default -110)
        
        Returns:
            ROI as percentage
        """
        if predictions is None:
            predictions = [p for p in self.predictions if p.actual_outcome is not None]
        
        if not predictions:
            return 0.0
        
        # Convert American odds to decimal multiplier
        if odds < 0:
            decimal_odds = 1 + (100 / abs(odds))
        else:
            decimal_odds = 1 + (odds / 100)
        
        total_bet = len(predictions)  # $1 per bet
        wins = sum(p.actual_outcome for p in predictions)
        losses = total_bet - wins
        
        # Calculate profit
        profit = (wins * (decimal_odds - 1)) - losses
        roi_pct = (profit / total_bet) * 100
        
        logger.info(
            f"ROI: {roi_pct:+.2f}% ({wins}W-{losses}L, n={total_bet})"
        )
        return roi_pct
    
    def analyze_by_tier(self) -> Dict[str, Dict]:
        """
        Analyze performance by confidence tier.
        
        Returns:
            Dict of tier -> metrics
        """
        predictions_with_outcomes = [
            p for p in self.predictions if p.actual_outcome is not None
        ]
        
        tiers = defaultdict(list)
        for pred in predictions_with_outcomes:
            tiers[pred.tier].append(pred)
        
        results = {}
        for tier, preds in tiers.items():
            if not preds:
                continue
            
            results[tier] = {
                "n_predictions": len(preds),
                "hit_rate": sum(p.actual_outcome for p in preds) / len(preds),
                "brier_score": self.calculate_brier_score(preds),
                "roi": self.calculate_roi(preds),
                "avg_confidence": sum(p.predicted_prob for p in preds) / len(preds)
            }
        
        return results
    
    def generate_calibration_report(self) -> Dict:
        """
        Generate comprehensive calibration report.
        
        Returns:
            Dict with all calibration metrics
        """
        predictions_with_outcomes = [
            p for p in self.predictions if p.actual_outcome is not None
        ]
        
        if not predictions_with_outcomes:
            logger.warning("No predictions with outcomes for report")
            return {
                "error": "No predictions with outcomes",
                "total_predictions": len(self.predictions)
            }
        
        # Calculate all metrics
        brier = self.calculate_brier_score(predictions_with_outcomes)
        ece, bins = self.calculate_ece(predictions_with_outcomes)
        log_loss = self.calculate_log_loss(predictions_with_outcomes)
        roi = self.calculate_roi(predictions_with_outcomes)
        tier_analysis = self.analyze_by_tier()
        
        # Overall hit rate
        hit_rate = sum(p.actual_outcome for p in predictions_with_outcomes) / len(predictions_with_outcomes)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_predictions": len(predictions_with_outcomes),
            "overall_metrics": {
                "brier_score": round(brier, 4),
                "ece": round(ece, 4),
                "log_loss": round(log_loss, 4),
                "roi_pct": round(roi, 2),
                "hit_rate": round(hit_rate, 3)
            },
            "calibration_bins": bins,
            "tier_performance": tier_analysis,
            "status": self._assess_status(brier, ece, roi)
        }
        
        # Save report
        report_file = self.output_dir / f"calibration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Calibration report saved: {report_file}")
        return report
    
    def _assess_status(self, brier: float, ece: float, roi: float) -> str:
        """Assess overall calibration status."""
        if brier < 0.23 and ece < 0.08 and roi > 3:
            return "EXCELLENT - Production ready"
        elif brier < 0.25 and ece < 0.10 and roi > 0:
            return "GOOD - Minor tuning recommended"
        elif brier < 0.27 and ece < 0.12:
            return "ACCEPTABLE - Needs recalibration"
        else:
            return "POOR - Major recalibration required"
    
    def export_to_csv(self, filename: Optional[str] = None):
        """
        Export predictions to CSV for external analysis.
        
        Args:
            filename: Output filename (defaults to timestamped file)
        """
        if filename is None:
            filename = self.output_dir / f"predictions_{datetime.now().strftime('%Y%m%d')}.csv"
        
        predictions_with_outcomes = [
            p for p in self.predictions if p.actual_outcome is not None
        ]
        
        if not predictions_with_outcomes:
            logger.warning("No predictions to export")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'player_name', 'opponent', 'stat_type', 'line', 'direction',
                'predicted_prob', 'tier', 'timestamp',
                'actual_outcome', 'actual_stat_value',
                'book', 'competition'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            for pred in predictions_with_outcomes:
                writer.writerow({
                    'player_name': pred.player_name,
                    'opponent': pred.opponent,
                    'stat_type': pred.stat_type,
                    'line': pred.line,
                    'direction': pred.direction,
                    'predicted_prob': pred.predicted_prob,
                    'tier': pred.tier,
                    'timestamp': pred.timestamp.isoformat(),
                    'actual_outcome': pred.actual_outcome,
                    'actual_stat_value': pred.actual_stat_value,
                    'book': pred.book or '',
                    'competition': pred.competition or ''
                })
        
        logger.info(f"Exported {len(predictions_with_outcomes)} predictions to {filename}")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize validator
    validator = CalibrationValidator()
    
    # Simulate adding predictions and outcomes
    print(f"\n{'='*70}")
    print(f"CALIBRATION VALIDATION EXAMPLE")
    print(f"{'='*70}\n")
    
    # Add some test predictions
    test_predictions = [
        # (player, stat, line, dir, pred_prob, tier, actual_outcome)
        ("Salah", "SHOTS", 3.5, "OVER", 0.75, "ELITE", 1),
        ("Haaland", "SHOTS", 4.5, "OVER", 0.68, "STRONG", 1),
        ("Grealish", "PASSES", 55.5, "OVER", 0.72, "ELITE", 0),
        ("Rodri", "TACKLES", 2.5, "OVER", 0.58, "LEAN", 1),
        ("De Bruyne", "SHOTS", 2.5, "OVER", 0.62, "STRONG", 0),
    ]
    
    for player, stat, line, direction, prob, tier, outcome in test_predictions:
        ts = datetime.now()
        validator.add_prediction(
            player_name=player,
            opponent="Opponent FC",
            stat_type=stat,
            line=line,
            direction=direction,
            predicted_prob=prob,
            tier=tier,
            book="PrizePicks",
            competition="Premier League"
        )
        # Immediately update with outcome (in reality, this happens later)
        validator.update_outcome(player, ts, outcome, line + (1 if outcome else -1))
    
    # Generate calibration report
    print("\nGenerating calibration report...\n")
    report = validator.generate_calibration_report()
    
    print(f"{'='*70}")
    print(f"CALIBRATION REPORT")
    print(f"{'='*70}")
    print(f"Total Predictions: {report['total_predictions']}")
    print(f"\nOverall Metrics:")
    print(f"  Brier Score: {report['overall_metrics']['brier_score']:.4f}")
    print(f"  ECE:         {report['overall_metrics']['ece']:.4f}")
    print(f"  Log Loss:    {report['overall_metrics']['log_loss']:.4f}")
    print(f"  ROI:         {report['overall_metrics']['roi_pct']:+.2f}%")
    print(f"  Hit Rate:    {report['overall_metrics']['hit_rate']:.1%}")
    print(f"\nStatus: {report['status']}")
    print(f"{'='*70}\n")
    
    # Export to CSV
    validator.export_to_csv()
