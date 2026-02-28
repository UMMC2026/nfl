#!/usr/bin/env python3
"""
Calibration Drift Detector - Phase 2 Implementation
=====================================================
Monitors calibration metrics over time and alerts when drift is detected.

Key metrics:
1. Expected Calibration Error (ECE) - Should be < 0.10
2. Brier Score - Should be < 0.25
3. Actual vs Predicted gap - Should be < 10%
4. Tier hit rates - Each tier should be within 5% of expected

Drift types:
- GRADUAL: Slow degradation over 30+ days
- SUDDEN: Sharp change in last 7 days
- TIER_SPECIFIC: One tier drifting while others stable

Version: 1.0.0
Created: 2026-02-04
"""

import csv
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import math

from config.thresholds import get_tier_threshold

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class DriftMetrics:
    """Drift detection metrics for a time window."""
    window_start: datetime
    window_end: datetime
    total_picks: int
    
    # Core calibration metrics
    avg_predicted: float
    avg_actual: float
    calibration_gap: float  # predicted - actual
    
    # By tier
    tier_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Brier score
    brier_score: float = 0.0
    
    # Drift signals
    drift_type: Optional[str] = None
    drift_severity: str = "NONE"  # NONE, LOW, MEDIUM, HIGH, CRITICAL
    
    def to_dict(self) -> dict:
        return {
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "total_picks": self.total_picks,
            "avg_predicted": self.avg_predicted,
            "avg_actual": self.avg_actual,
            "calibration_gap": self.calibration_gap,
            "tier_metrics": self.tier_metrics,
            "brier_score": self.brier_score,
            "drift_type": self.drift_type,
            "drift_severity": self.drift_severity,
        }


@dataclass
class DriftAlert:
    """Alert generated when drift is detected."""
    alert_id: str
    timestamp: datetime
    drift_type: str
    severity: str
    message: str
    metrics: DriftMetrics
    recommended_action: str
    
    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat(),
            "drift_type": self.drift_type,
            "severity": self.severity,
            "message": self.message,
            "metrics": self.metrics.to_dict(),
            "recommended_action": self.recommended_action,
        }


class DriftDetector:
    """
    Detects calibration drift by analyzing historical pick data.
    """
    
    # Thresholds
    CALIBRATION_GAP_THRESHOLDS = {
        "CRITICAL": 0.20,  # 20% gap
        "HIGH": 0.15,      # 15% gap
        "MEDIUM": 0.10,    # 10% gap
        "LOW": 0.05,       # 5% gap
    }
    
    BRIER_THRESHOLDS = {
        "CRITICAL": 0.30,
        "HIGH": 0.27,
        "MEDIUM": 0.24,
        "LOW": 0.22,
    }
    
    def _console_safe(self, text) -> str:
        """Return a string that is safe to print on Windows consoles (cp1252)."""
        if text is None:
            return ""
        s = str(text)
        # Replace common symbols seen in outputs.
        s = (
            s.replace("✅", "OK")
            .replace("⚠️", "WARN")
            .replace("⚠", "WARN")
            .replace("🚨", "CRITICAL")
            .replace("📊", "INFO")
            .replace("🔶", "HIGH")
            .replace("❌", "FAIL")
            .replace("❓", "?")
            .replace("→", "->")
            .replace("≈", "~=")
            .replace("≥", ">=")
            .replace("≤", "<=")
            .replace("—", "-")
            .replace("–", "-")
        )

        enc = getattr(sys.stdout, "encoding", None) or "cp1252"
        try:
            s.encode(enc)
            return s
        except Exception:
            return s.encode(enc, errors="replace").decode(enc, errors="replace")

    def _expected_tier_rate(self, *, sport: Optional[str], tier: str) -> Optional[float]:
        """Use canonical tier thresholds as the expected hit-rate baseline.

        We intentionally do NOT hardcode tier rates here; they must be sourced from config/thresholds.py.
        """
        try:
            return get_tier_threshold(tier, sport)
        except Exception:
            return None
    
    def __init__(self, calibration_file: Optional[Path] = None):
        self.calibration_file = calibration_file or PROJECT_ROOT / "calibration_history.csv"
        self.alerts_file = PROJECT_ROOT / "calibration" / "drift_alerts.json"
        self.metrics_file = PROJECT_ROOT / "calibration" / "drift_metrics.json"
        self.history: List[dict] = []
        self.alerts: List[DriftAlert] = []
        
    def load_history(self) -> List[dict]:
        """Load calibration history from CSV."""
        if not self.calibration_file.exists():
            print(f"WARN: Calibration file not found: {self._console_safe(self.calibration_file)}")
            return []
        
        history = []
        try:
            with open(self.calibration_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Parse date - support multiple column names
                    date_str = row.get("game_date") or row.get("date") or row.get("Date") or ""
                    if not date_str.strip():
                        continue
                    try:
                        date = datetime.strptime(date_str, "%Y-%m-%d")
                    except ValueError:
                        try:
                            date = datetime.strptime(date_str, "%m/%d/%Y")
                        except ValueError:
                            continue
                    
                    # Parse result/outcome
                    result_str = (row.get("outcome") or row.get("result") or row.get("Result") or "").strip().upper()
                    hit = result_str in ("HIT", "WIN", "W", "1", "TRUE")
                    
                    # Parse probability
                    prob_str = row.get("probability") or row.get("Probability") or "0"
                    try:
                        prob = float(prob_str.replace("%", "")) / 100 if "%" in str(prob_str) else float(prob_str)
                        # Handle probabilities stored as raw floats > 1 (e.g., 65.5 meaning 65.5%)
                        if prob > 1:
                            prob = prob / 100
                    except ValueError:
                        prob = 0.5
                    
                    # Parse tier
                    tier = (row.get("tier") or row.get("Tier") or "LEAN").upper()
                    
                    # Parse sport/league
                    sport = (row.get("league") or row.get("sport") or row.get("Sport") or "NBA").upper()
                    
                    history.append({
                        "date": date,
                        "hit": hit,
                        "probability": prob,
                        "tier": tier,
                        "player": row.get("player") or row.get("Player") or "",
                        "stat": row.get("stat") or row.get("Stat") or "",
                        "sport": sport,
                    })
                    
            self.history = sorted(history, key=lambda x: x["date"])
            print(f"INFO: Loaded {len(self.history)} calibration records")
            
        except Exception as e:
            print(f"ERROR: Error loading calibration: {self._console_safe(e)}")
            
        return self.history
    
    def calculate_metrics(
        self, 
        window_days: int = 30,
        sport: Optional[str] = None
    ) -> DriftMetrics:
        """Calculate calibration metrics for a time window."""
        if not self.history:
            self.load_history()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=window_days)
        
        # Filter history
        window_data = [
            h for h in self.history 
            if start_date <= h["date"] <= end_date
            and (sport is None or h.get("sport", "").upper() == sport.upper())
        ]
        
        if not window_data:
            return DriftMetrics(
                window_start=start_date,
                window_end=end_date,
                total_picks=0,
                avg_predicted=0,
                avg_actual=0,
                calibration_gap=0,
            )
        
        # Overall metrics
        probs = [h["probability"] for h in window_data]
        hits = [1 if h["hit"] else 0 for h in window_data]
        
        avg_predicted = sum(probs) / len(probs)
        avg_actual = sum(hits) / len(hits)
        calibration_gap = avg_predicted - avg_actual
        
        # Brier score
        brier = sum((p - h) ** 2 for p, h in zip(probs, hits)) / len(probs)
        
        # By tier
        tier_metrics = {}
        for tier in ["SLAM", "STRONG", "LEAN"]:
            tier_data = [h for h in window_data if h["tier"] == tier]
            if tier_data:
                tier_probs = [h["probability"] for h in tier_data]
                tier_hits = [1 if h["hit"] else 0 for h in tier_data]
                tier_avg_pred = sum(tier_probs) / len(tier_probs)
                tier_avg_act = sum(tier_hits) / len(tier_hits)
                expected = self._expected_tier_rate(sport=sport, tier=tier)
                tier_metrics[tier] = {
                    "count": len(tier_data),
                    "predicted": tier_avg_pred,
                    "actual": tier_avg_act,
                    "gap": tier_avg_pred - tier_avg_act,
                    "expected": expected,
                }
        
        return DriftMetrics(
            window_start=start_date,
            window_end=end_date,
            total_picks=len(window_data),
            avg_predicted=round(avg_predicted, 4),
            avg_actual=round(avg_actual, 4),
            calibration_gap=round(calibration_gap, 4),
            tier_metrics=tier_metrics,
            brier_score=round(brier, 4),
        )
    
    def detect_drift(
        self,
        short_window: int = 7,
        long_window: int = 30,
        sport: Optional[str] = None
    ) -> Tuple[DriftMetrics, Optional[DriftAlert]]:
        """
        Detect calibration drift by comparing short and long windows.
        
        Returns: (current_metrics, alert_if_drift_detected)
        """
        short_metrics = self.calculate_metrics(short_window, sport)
        long_metrics = self.calculate_metrics(long_window, sport)
        
        # Determine drift severity
        gap = abs(short_metrics.calibration_gap)
        severity = "NONE"
        
        for level, threshold in sorted(self.CALIBRATION_GAP_THRESHOLDS.items(), 
                                        key=lambda x: x[1], reverse=True):
            if gap >= threshold:
                severity = level
                break
        
        short_metrics.drift_severity = severity
        
        # Detect drift type
        drift_type = None
        
        if severity != "NONE":
            # Compare short vs long window gaps
            short_gap = abs(short_metrics.calibration_gap)
            long_gap = abs(long_metrics.calibration_gap)
            
            if short_gap > long_gap * 1.5:
                drift_type = "SUDDEN"
            elif short_gap <= long_gap * 1.2:
                drift_type = "GRADUAL"
            else:
                drift_type = "STABLE_HIGH"
            
            short_metrics.drift_type = drift_type
        
        # Generate alert if needed
        alert = None
        if severity in ["MEDIUM", "HIGH", "CRITICAL"]:
            direction = "over" if short_metrics.calibration_gap > 0 else "under"
            
            alert = DriftAlert(
                alert_id=f"DRIFT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now(),
                drift_type=drift_type or "UNKNOWN",
                severity=severity,
                message=f"Calibration drift detected: {direction}confidence by {gap:.1%}",
                metrics=short_metrics,
                recommended_action=self._get_recommendation(severity, drift_type, short_metrics.calibration_gap),
            )
            self.alerts.append(alert)
            
            # Send Telegram alert for HIGH and CRITICAL
            if severity in ["HIGH", "CRITICAL"]:
                try:
                    from telegram_notifier import send_drift_alert_sync
                    send_drift_alert_sync(
                        drift_type=drift_type or "UNKNOWN",
                        severity=severity,
                        message=alert.recommended_action,
                        gap=short_metrics.calibration_gap
                    )
                except ImportError:
                    pass  # Telegram not configured
                except Exception as e:
                    print(f"WARN: Telegram alert failed: {self._console_safe(e)}")
        
        return short_metrics, alert
    
    def _get_recommendation(self, severity: str, drift_type: str, gap: float) -> str:
        """Get recommended action based on drift severity and type."""
        direction = "overconfidence" if gap > 0 else "underconfidence"
        
        recommendations = {
            "CRITICAL": f"URGENT: {direction} requires immediate calibration review. "
                       f"Consider pausing picks until recalibration complete.",
            "HIGH": f"Significant {direction} detected. Run variance penalty audit "
                    f"and check distribution parameters.",
            "MEDIUM": f"Moderate {direction}. Monitor closely over next 7 days. "
                      f"Review recent tier distribution.",
        }
        
        if drift_type == "SUDDEN":
            return recommendations.get(severity, "") + " Sudden change suggests recent code/data issue."
        elif drift_type == "GRADUAL":
            return recommendations.get(severity, "") + " Gradual drift suggests model decay."
        
        return recommendations.get(severity, "Monitor calibration metrics.")
    
    def check_tier_drift(self, window_days: int = 30, sport: Optional[str] = None) -> List[DriftAlert]:
        """Check for drift in specific tiers."""
        metrics = self.calculate_metrics(window_days, sport)
        tier_alerts = []

        for tier in ("SLAM", "STRONG", "LEAN"):
            expected = self._expected_tier_rate(sport=sport, tier=tier)
            if expected is None:
                continue
            if tier not in metrics.tier_metrics:
                continue

            tier_data = metrics.tier_metrics[tier]
            actual = tier_data["actual"]
            gap = actual - expected
            
            # Tier-specific threshold: 10% deviation
            if abs(gap) > 0.10 and tier_data["count"] >= 10:
                severity = "HIGH" if abs(gap) > 0.15 else "MEDIUM"
                direction = "under" if gap < 0 else "over"
                
                alert = DriftAlert(
                    alert_id=f"TIER-{tier}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    timestamp=datetime.now(),
                    drift_type="TIER_SPECIFIC",
                    severity=severity,
                    message=f"{tier} tier {direction}performing: {actual:.1%} vs expected {expected:.1%}",
                    metrics=metrics,
                    recommended_action=f"Review {tier} tier selection criteria and line thresholds.",
                )
                tier_alerts.append(alert)
                self.alerts.append(alert)
        
        return tier_alerts
    
    def save_metrics(self, metrics: DriftMetrics):
        """Save metrics to JSON for historical tracking."""
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        
        history = []
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, "r") as f:
                    history = json.load(f)
            except:
                history = []
        
        history.append(metrics.to_dict())
        
        # Keep last 365 days
        history = history[-365:]
        
        with open(self.metrics_file, "w") as f:
            json.dump(history, f, indent=2)
        
        print(f"📊 Saved metrics to {self.metrics_file}")
    
    def save_alerts(self):
        """Save alerts to JSON."""
        self.alerts_file.parent.mkdir(parents=True, exist_ok=True)
        
        existing = []
        if self.alerts_file.exists():
            try:
                with open(self.alerts_file, "r") as f:
                    existing = json.load(f)
            except:
                existing = []
        
        # Add new alerts
        for alert in self.alerts:
            existing.append(alert.to_dict())
        
        # Keep last 100 alerts
        existing = existing[-100:]
        
        with open(self.alerts_file, "w") as f:
            json.dump(existing, f, indent=2)
        
        print(f"🚨 Saved {len(self.alerts)} alerts to {self.alerts_file}")
    
    def print_status(self, sport: Optional[str] = None, *, min_picks: int = 10):
        """Print current drift status.

        If total picks in the window is below min_picks, we report INSUFFICIENT_DATA
        and suppress CRITICAL/urgent alerts.
        """
        metrics, alert = self.detect_drift(sport=sport)
        tier_alerts = self.check_tier_drift(sport=sport)
        
        sport_label = f" ({sport})" if sport else ""
        
        print("\n" + "=" * 60)
        print(f"CALIBRATION DRIFT STATUS{sport_label}")
        print("=" * 60)
        print(f"Window: {metrics.window_start.date()} to {metrics.window_end.date()}")
        print(f"Total picks: {metrics.total_picks}")
        print()
        print(f"Predicted avg: {metrics.avg_predicted:.1%}")
        print(f"Actual avg:    {metrics.avg_actual:.1%}")
        print(f"Gap:           {metrics.calibration_gap:+.1%}")
        print(f"Brier Score:   {metrics.brier_score:.4f}")
        print()

        low_n = metrics.total_picks < int(min_picks)
        
        # Tier breakdown
        print("─" * 40)
        print("TIER BREAKDOWN:")
        for tier, data in metrics.tier_metrics.items():
            expected = data.get("expected")
            actual = data["actual"]
            if expected is None:
                print(f"  {tier:8s} n={data['count']:3d}  actual={actual:.1%} vs expected=DISABLED")
                continue
            status = "OK" if abs(actual - expected) < 0.05 else "WARN" if abs(actual - expected) < 0.10 else "FAIL"
            print(f"  {tier:8s} n={data['count']:3d}  actual={actual:.1%} vs expected={expected:.1%}  {status}")
        
        # Drift status
        print()
        print("─" * 40)
        if low_n:
            print(f"DRIFT STATUS: INSUFFICIENT_DATA (min_picks={min_picks})")
        else:
            print(f"DRIFT STATUS: {metrics.drift_severity}")
            if metrics.drift_type:
                print(f"DRIFT TYPE:   {metrics.drift_type}")
        
        # Alerts
        if alert and not low_n:
            print()
            print("─" * 40)
            print(f"ALERT: {self._console_safe(alert.message)}")
            print(f"   Action: {self._console_safe(alert.recommended_action)}")
        
        if not low_n:
            for t_alert in tier_alerts:
                print(f"TIER ALERT: {self._console_safe(t_alert.message)}")
        
        print("=" * 60)
        
        return metrics, alert, tier_alerts


def main():
    """CLI for drift detection."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Calibration Drift Detector")
    parser.add_argument("--sport", help="Filter by sport (NBA, Tennis, etc.)")
    parser.add_argument("--short-window", type=int, default=7, help="Short window days")
    parser.add_argument("--long-window", type=int, default=30, help="Long window days")
    parser.add_argument("--save", action="store_true", help="Save metrics and alerts")
    args = parser.parse_args()
    
    detector = DriftDetector()
    metrics, alert, tier_alerts = detector.print_status(sport=args.sport)
    
    if args.save:
        detector.save_metrics(metrics)
        if detector.alerts:
            detector.save_alerts()


if __name__ == "__main__":
    main()
