#!/usr/bin/env python3
"""
Auto-Calibration Scheduler - Phase 4 Implementation
=====================================================
Runs daily calibration checks and auto-adjusts thresholds based on drift.

Features:
1. Daily drift detection
2. Automatic threshold adjustment when drift exceeds limits
3. Telegram alerts for significant changes
4. Historical tracking of adjustments

Can be run as:
- Standalone script (manual)
- Windows Task Scheduler job
- VS Code task

Version: 1.0.0
Created: 2026-02-04
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent

# Add project root to path
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class CalibrationAction:
    """Record of a calibration action taken."""
    timestamp: datetime
    action_type: str  # "threshold_adjust", "penalty_adjust", "alert_only"
    sport: str
    tier: str
    old_value: float
    new_value: float
    reason: str
    drift_gap: float
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type,
            "sport": self.sport,
            "tier": self.tier,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "drift_gap": self.drift_gap,
        }


class AutoCalibrator:
    """
    Automatic calibration adjustment engine.
    """
    
    # Drift thresholds for action
    ALERT_THRESHOLD = 0.08      # 8% gap triggers alert
    ADJUST_THRESHOLD = 0.12     # 12% gap triggers auto-adjustment
    CRITICAL_THRESHOLD = 0.18   # 18% gap triggers emergency action
    
    # Maximum adjustment per run (safety limit)
    MAX_ADJUSTMENT = 0.05  # 5% max change per run

    # Maximum tier-threshold delta per run (absolute probability points)
    MAX_THRESHOLD_DELTA = 0.03
    
    def __init__(self):
        self.actions_file = PROJECT_ROOT / "calibration" / "calibration_actions.json"
        self.runs_file = PROJECT_ROOT / "calibration" / "auto_calibrator_runs.json"
        self.threshold_overrides_file = PROJECT_ROOT / "config" / "threshold_overrides.json"
        self.actions: List[CalibrationAction] = []
        self.dry_run = True  # Default to dry run for safety

    def _append_jsonlish_history(self, path: Path, records: List[dict], *, keep_last: int = 1000) -> None:
        """Append records to a JSON list file, keeping only the most recent N."""
        path.parent.mkdir(parents=True, exist_ok=True)
        history: list = []
        if path.exists():
            try:
                history = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                history = []
        history.extend(records)
        history = history[-keep_last:]
        path.write_text(json.dumps(history, indent=2), encoding="utf-8")

    def _load_threshold_overrides(self) -> Dict[str, Dict[str, Optional[float]]]:
        """Load threshold overrides from disk (sport -> tier -> value)."""
        if not self.threshold_overrides_file.exists():
            return {}
        try:
            raw = json.loads(self.threshold_overrides_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

        # Accept either {"overrides": {...}} or a direct mapping.
        mapping = raw.get("overrides") if isinstance(raw, dict) and "overrides" in raw else raw
        if not isinstance(mapping, dict):
            return {}

        out: Dict[str, Dict[str, Optional[float]]] = {}
        for sport, tiers in mapping.items():
            if not isinstance(sport, str) or not isinstance(tiers, dict):
                continue
            sport_u = sport.strip().upper()
            out.setdefault(sport_u, {})
            for tier, val in tiers.items():
                if not isinstance(tier, str):
                    continue
                tier_u = tier.strip().upper()
                if val is None:
                    out[sport_u][tier_u] = None
                    continue
                try:
                    f = float(val)
                except Exception:
                    continue
                # Allow percent-like values.
                if f > 1.0:
                    f = f / 100.0
                if 0.0 <= f <= 1.0:
                    out[sport_u][tier_u] = round(f, 4)
        return out

    def _write_threshold_override(self, sport: str, tier: str, value: float) -> None:
        """Write/update a single sport+tier override in threshold_overrides.json."""
        sport_u = sport.strip().upper()
        tier_u = tier.strip().upper()

        payload: dict = {}
        if self.threshold_overrides_file.exists():
            try:
                payload = json.loads(self.threshold_overrides_file.read_text(encoding="utf-8"))
            except Exception:
                payload = {}

        if not isinstance(payload, dict):
            payload = {}
        overrides = payload.get("overrides")
        if not isinstance(overrides, dict):
            overrides = {}
            payload["overrides"] = overrides

        sport_block = overrides.get(sport_u)
        if not isinstance(sport_block, dict):
            sport_block = {}
            overrides[sport_u] = sport_block

        sport_block[tier_u] = round(float(value), 4)
        payload["updated_utc"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.threshold_overrides_file.parent.mkdir(parents=True, exist_ok=True)
        self.threshold_overrides_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        
    def run_daily_check(self, dry_run: bool = True) -> List[CalibrationAction]:
        """Run daily calibration check."""
        self.dry_run = dry_run
        self.actions = []

        run_started = datetime.now()
        sports_checked = 0
        sports_skipped = 0
        
        print("\n" + "=" * 60)
        print("AUTO-CALIBRATION SCHEDULER")
        print(f"   Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Run drift detection
        from calibration.drift_detector import DriftDetector
        detector = DriftDetector()
        
        # Check each sport
        sports = ["NBA", "TENNIS", "CBB", "GOLF", "NHL"]
        
        for sport in sports:
            print(f"\nChecking {sport}...")
            metrics, alert, tier_alerts = detector.print_status(sport=sport, min_picks=10)

            sports_checked += 1
            
            if metrics.total_picks < 10:
                print(f"   Skipping auto-adjustments (only {metrics.total_picks} picks)")
                sports_skipped += 1
                continue
            
            # Evaluate drift
            gap = metrics.calibration_gap
            severity = metrics.drift_severity
            
            if abs(gap) >= self.CRITICAL_THRESHOLD:
                self._handle_critical_drift(sport, gap, metrics)
            elif abs(gap) >= self.ADJUST_THRESHOLD:
                self._handle_adjustment_drift(sport, gap, metrics)
            elif abs(gap) >= self.ALERT_THRESHOLD:
                self._handle_alert_drift(sport, gap, metrics)
            else:
                print(f"   OK: {sport} within tolerance ({gap:+.1%})")
            
            # Check tier-specific drift
            for tier, data in metrics.tier_metrics.items():
                try:
                    from config.thresholds import get_tier_threshold
                    expected = get_tier_threshold(tier, sport)
                except Exception:
                    expected = None

                if expected is None:
                    continue
                actual = data.get("actual", expected)
                tier_gap = actual - expected
                
                if abs(tier_gap) >= 0.15 and data.get("count", 0) >= 10:
                    self._handle_tier_drift(sport, tier, tier_gap, expected, actual)

        # Always persist a "run" record so history reflects that the scheduler executed.
        run_record = {
            "timestamp": run_started.isoformat(),
            "dry_run": bool(self.dry_run),
            "sports_checked": sports_checked,
            "sports_skipped": sports_skipped,
            "actions_count": len(self.actions),
        }
        try:
            self._append_jsonlish_history(self.runs_file, [run_record], keep_last=1000)
        except Exception:
            pass
        
        # Save actions
        if self.actions:
            self._save_actions()
            self._send_telegram_summary()
        
        print("\n" + "=" * 60)
        print(f"Actions taken: {len(self.actions)}")
        print("=" * 60)
        
        return self.actions
    
    def _handle_critical_drift(self, sport: str, gap: float, metrics):
        """Handle critical drift (18%+)."""
        direction = "overconfident" if gap > 0 else "underconfident"
        print(f"   CRITICAL: {sport} is {direction} by {abs(gap):.1%}")
        
        # For critical drift, recommend manual review
        action = CalibrationAction(
            timestamp=datetime.now(),
            action_type="critical_alert",
            sport=sport,
            tier="ALL",
            old_value=0,
            new_value=0,
            reason=f"Critical {direction} drift requires manual review",
            drift_gap=gap,
        )
        self.actions.append(action)
        
        # Calculate suggested adjustment
        suggested = min(abs(gap) * 0.5, self.MAX_ADJUSTMENT)
        if gap > 0:  # Overconfident - reduce probabilities
            print(f"   💡 Suggested: Increase variance penalty by {suggested:.1%}")
        else:  # Underconfident - increase probabilities
            print(f"   💡 Suggested: Decrease variance penalty by {suggested:.1%}")
    
    def _handle_adjustment_drift(self, sport: str, gap: float, metrics):
        """Handle adjustment-level drift (12-18%)."""
        direction = "overconfident" if gap > 0 else "underconfident"
        print(f"   ADJUSTMENT: {sport} is {direction} by {abs(gap):.1%}")
        
        # Translate calibration gap into a small tier-threshold shift.
        # If overconfident (predicted > actual), tighten gates (raise thresholds).
        # If underconfident, loosen gates (lower thresholds).
        delta = min(abs(gap) * 0.25, self.MAX_THRESHOLD_DELTA)
        signed_delta = delta if gap > 0 else -delta

        applied_changes: List[Tuple[str, float, float]] = []
        if not self.dry_run:
            applied_changes = self._adjust_tier_thresholds(sport, signed_delta)
        
        action = CalibrationAction(
            timestamp=datetime.now(),
            action_type="threshold_adjust" if not self.dry_run else "threshold_adjust_proposed",
            sport=sport,
            tier="ALL",
            old_value=0,
            new_value=signed_delta,
            reason=f"Auto-adjustment for {direction} drift",
            drift_gap=gap,
        )
        self.actions.append(action)
        
        print(f"   {'Applied' if not self.dry_run else 'Would apply'}: "
              f"{'Tighten' if gap > 0 else 'Loosen'} tier thresholds by {abs(delta):.1%}")
        if applied_changes:
            for tier, old_v, new_v in applied_changes:
                print(f"      - {tier}: {old_v:.3f} -> {new_v:.3f}")
    
    def _handle_alert_drift(self, sport: str, gap: float, metrics):
        """Handle alert-level drift (8-12%)."""
        direction = "overconfident" if gap > 0 else "underconfident"
        print(f"   ALERT: {sport} is {direction} by {abs(gap):.1%}")
        
        action = CalibrationAction(
            timestamp=datetime.now(),
            action_type="alert_only",
            sport=sport,
            tier="ALL",
            old_value=0,
            new_value=0,
            reason=f"Monitoring {direction} drift",
            drift_gap=gap,
        )
        self.actions.append(action)
    
    def _handle_tier_drift(self, sport: str, tier: str, gap: float, expected: float, actual: float):
        """Handle tier-specific drift."""
        direction = "over" if gap > 0 else "under"
        print(f"   {tier}: {direction}performing ({actual:.1%} vs {expected:.0%})")
        
        action = CalibrationAction(
            timestamp=datetime.now(),
            action_type="tier_alert",
            sport=sport,
            tier=tier,
            old_value=expected,
            new_value=actual,
            reason=f"{tier} tier {direction}performing",
            drift_gap=gap,
        )
        self.actions.append(action)
    
    def _adjust_tier_thresholds(self, sport: str, delta: float) -> List[Tuple[str, float, float]]:
        """Adjust tier thresholds for a sport by delta and persist as overrides.

        Returns a list of (tier, old_value, new_value) for applied changes.
        """
        try:
            from config.thresholds import get_all_thresholds
        except Exception:
            return []

        thresholds = get_all_thresholds(sport)
        # Only adjust actionable tiers; respect disabled tiers (None).
        tiers_to_adjust = ["STRONG", "LEAN", "SLAM"]
        new_vals: Dict[str, float] = {}
        applied: List[Tuple[str, float, float]] = []

        for tier in tiers_to_adjust:
            old = thresholds.get(tier)
            if old is None:
                continue
            try:
                old_f = float(old)
            except Exception:
                continue
            # Clamp to safe range.
            candidate = max(0.50, min(0.90, old_f + float(delta)))
            new_vals[tier] = round(candidate, 4)

        # Enforce ordering: SLAM >= STRONG >= LEAN with small spacing.
        min_gap = 0.02
        slam = new_vals.get("SLAM")
        strong = new_vals.get("STRONG")
        lean = new_vals.get("LEAN")
        if strong is not None and lean is not None and strong < lean + min_gap:
            strong = min(0.90, lean + min_gap)
            new_vals["STRONG"] = round(strong, 4)
        if slam is not None and strong is not None and slam < strong + min_gap:
            slam = min(0.90, strong + min_gap)
            new_vals["SLAM"] = round(slam, 4)

        # Persist overrides.
        for tier, new_v in new_vals.items():
            old_v = thresholds.get(tier)
            if old_v is None:
                continue
            try:
                old_f = float(old_v)
            except Exception:
                continue
            if abs(new_v - old_f) < 1e-9:
                continue
            self._write_threshold_override(sport, tier, new_v)
            applied.append((tier, old_f, new_v))

        if applied:
            print(f"   Updated threshold overrides: {self.threshold_overrides_file}")
        return applied
    
    def _save_actions(self):
        """Save actions to history file."""
        records = [a.to_dict() for a in self.actions]
        self._append_jsonlish_history(self.actions_file, records, keep_last=1000)
        print(f"\nSaved {len(self.actions)} actions to {self.actions_file}")
    
    def _send_telegram_summary(self):
        """Send Telegram summary of actions."""
        try:
            from telegram_notifier import send_drift_alert_sync
            
            # Build summary message
            critical = [a for a in self.actions if a.action_type == "critical_alert"]
            adjustments = [a for a in self.actions if "adjust" in a.action_type]
            alerts = [a for a in self.actions if a.action_type == "alert_only"]
            
            if critical:
                for action in critical:
                    send_drift_alert_sync(
                        drift_type="CRITICAL",
                        severity="CRITICAL",
                        message=action.reason,
                        gap=action.drift_gap
                    )
            elif adjustments:
                for action in adjustments[:3]:  # Max 3 alerts
                    send_drift_alert_sync(
                        drift_type="AUTO_ADJUST",
                        severity="HIGH",
                        message=action.reason,
                        gap=action.drift_gap
                    )
                    
        except ImportError:
            print("   WARN: Telegram not configured")
        except Exception as e:
            print(f"   WARN: Telegram error: {e}")
    
    def get_action_history(self, days: int = 7) -> List[dict]:
        """Get recent action history."""
        if not self.actions_file.exists():
            return []
        
        try:
            history = json.loads(self.actions_file.read_text())
        except:
            return []
        
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        
        for action in history:
            try:
                ts = datetime.fromisoformat(action["timestamp"])
                if ts >= cutoff:
                    recent.append(action)
            except:
                continue
        
        return recent

    def get_run_history(self, days: int = 7) -> List[dict]:
        """Get recent run history (even if no actions were taken)."""
        if not self.runs_file.exists():
            return []
        try:
            history = json.loads(self.runs_file.read_text(encoding="utf-8"))
        except Exception:
            return []

        cutoff = datetime.now() - timedelta(days=days)
        recent: List[dict] = []
        for run in history:
            try:
                ts = datetime.fromisoformat(run.get("timestamp", ""))
                if ts >= cutoff:
                    recent.append(run)
            except Exception:
                continue
        return recent
    
    def print_history(self, days: int = 7):
        """Print action history."""
        history = self.get_action_history(days)
        
        print(f"\nCalibration Actions (Last {days} days)")
        print("─" * 50)
        
        if not history:
            print("   No actions recorded")
            return
        
        for action in history[-20:]:  # Last 20
            ts = action.get("timestamp", "")[:16]
            sport = action.get("sport", "?")
            atype = action.get("action_type", "?")
            gap = action.get("drift_gap", 0)
            
            print(f"   [{ts}] {sport:6s} {atype:20s} gap={gap:+.1%}")

    def print_run_history(self, days: int = 7):
        """Print recent scheduler runs."""
        runs = self.get_run_history(days)
        print(f"\nAuto-Calibrator Runs (Last {days} days)")
        print("─" * 50)
        if not runs:
            print("   No runs recorded")
            return
        for run in runs[-20:]:
            ts = str(run.get("timestamp", ""))[:16]
            dry = "DRY" if run.get("dry_run") else "LIVE"
            checked = run.get("sports_checked", "?")
            skipped = run.get("sports_skipped", "?")
            actions = run.get("actions_count", "?")
            print(f"   [{ts}] mode={dry:4s} sports={checked} skipped={skipped} actions={actions}")

    def reset_threshold_overrides(self) -> None:
        """Remove threshold overrides file to revert to canonical defaults."""
        try:
            if self.threshold_overrides_file.exists():
                self.threshold_overrides_file.unlink()
        except Exception as e:
            raise e


def main():
    """CLI for auto-calibrator."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-Calibration Scheduler")
    parser.add_argument("--live", action="store_true", help="Run in LIVE mode (apply changes)")
    parser.add_argument("--history", type=int, default=0, help="Show action history for N days")
    args = parser.parse_args()
    
    calibrator = AutoCalibrator()
    
    if args.history > 0:
        calibrator.print_history(args.history)
    else:
        calibrator.run_daily_check(dry_run=not args.live)


if __name__ == "__main__":
    main()
