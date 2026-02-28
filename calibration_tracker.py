#!/usr/bin/env python3
"""
FUOOM CALIBRATION TRACKER — SOP v2.1 Compliant
===============================================
Tracks prediction accuracy, calibration drift, and enables data-driven recalibration.

Features:
- Immutable calibration log (append-only)
- Brier score tracking by sport/stat/tier
- Automatic drift detection
- Calibration curve generation
- Weekly/monthly reporting

Usage:
    from calibration_tracker import CalibrationTracker
    
    tracker = CalibrationTracker()
    tracker.log_pick(pick_data)
    tracker.log_result(pick_id, actual_outcome)
    report = tracker.generate_calibration_report("NBA", "2026-01")
    
CLI Usage:
    python calibration_tracker.py --init
    python calibration_tracker.py --report --sport NBA --period 2026-01
    python calibration_tracker.py --check-drift --sport NBA
    python calibration_tracker.py --export --format csv
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager


# =============================================================================
# SCHEMA DEFINITION
# =============================================================================

SCHEMA_SQL = """
-- =============================================================================
-- FUOOM CALIBRATION TRACKING SCHEMA v1.0
-- SOP v2.1 Compliant — Immutable Audit Trail
-- =============================================================================

-- Core picks table (immutable after insertion)
CREATE TABLE IF NOT EXISTS picks (
    pick_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Game/Event Context
    sport TEXT NOT NULL,
    game_id TEXT NOT NULL,
    game_date DATE NOT NULL,
    
    -- Player/Entity
    player_id TEXT,
    player_name TEXT NOT NULL,
    team TEXT,
    opponent TEXT,
    
    -- Pick Details
    stat_type TEXT NOT NULL,
    line REAL NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('over', 'under', 'higher', 'lower')),
    
    -- Model Output
    projected_value REAL NOT NULL,
    probability REAL NOT NULL CHECK (probability >= 0 AND probability <= 1),
    confidence_tier TEXT NOT NULL,
    model_version TEXT,
    
    -- Risk Classification
    is_primary BOOLEAN DEFAULT TRUE,
    risk_tag TEXT,
    pick_state TEXT,
    
    -- Metadata
    edge_key TEXT,
    features_json TEXT,
    
    -- Indexing
    UNIQUE(sport, game_id, player_name, stat_type, direction)
);

-- Results table (links to picks, immutable)
CREATE TABLE IF NOT EXISTS results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pick_id TEXT NOT NULL REFERENCES picks(pick_id),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Actual Outcome
    actual_value REAL NOT NULL,
    hit BOOLEAN NOT NULL,
    
    -- Verification
    source TEXT,
    verified BOOLEAN DEFAULT FALSE,
    
    UNIQUE(pick_id)
);

-- Calibration log (aggregated metrics, append-only)
CREATE TABLE IF NOT EXISTS calibration_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Grouping
    sport TEXT NOT NULL,
    stat_type TEXT,
    confidence_tier TEXT,
    probability_bucket TEXT,
    direction TEXT,
    
    -- Metrics
    n_picks INTEGER NOT NULL,
    n_hits INTEGER NOT NULL,
    actual_hit_rate REAL NOT NULL,
    expected_hit_rate REAL NOT NULL,
    
    -- Calibration Scores
    brier_score REAL,
    calibration_error REAL,
    log_loss REAL,
    
    -- Action
    action_taken TEXT,
    notes TEXT,
    
    -- Indexing
    UNIQUE(log_date, sport, stat_type, confidence_tier, probability_bucket, direction)
);

-- Drift detection table
CREATE TABLE IF NOT EXISTS drift_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    sport TEXT NOT NULL,
    stat_type TEXT,
    
    -- Drift Details
    metric TEXT NOT NULL,
    baseline_value REAL NOT NULL,
    current_value REAL NOT NULL,
    drift_magnitude REAL NOT NULL,
    drift_direction TEXT CHECK (drift_direction IN ('overconfident', 'underconfident')),
    
    -- Severity
    severity TEXT CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    
    -- Resolution
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolution_notes TEXT
);

-- Model version tracking
CREATE TABLE IF NOT EXISTS model_versions (
    version_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    sport TEXT NOT NULL,
    model_type TEXT,
    
    -- Performance at deployment
    backtest_accuracy REAL,
    backtest_brier REAL,
    backtest_sample_size INTEGER,
    
    -- Configuration snapshot
    config_json TEXT,
    
    -- Status
    status TEXT CHECK (status IN ('active', 'deprecated', 'testing')),
    deprecated_at TIMESTAMP,
    deprecation_reason TEXT
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_picks_sport_date ON picks(sport, game_date);
CREATE INDEX IF NOT EXISTS idx_picks_player ON picks(player_name, sport);
CREATE INDEX IF NOT EXISTS idx_picks_stat ON picks(stat_type, sport);
CREATE INDEX IF NOT EXISTS idx_picks_tier ON picks(confidence_tier, sport);
CREATE INDEX IF NOT EXISTS idx_picks_probability ON picks(probability);

CREATE INDEX IF NOT EXISTS idx_results_pick ON results(pick_id);
CREATE INDEX IF NOT EXISTS idx_results_hit ON results(hit);

CREATE INDEX IF NOT EXISTS idx_calibration_sport_date ON calibration_log(sport, log_date);
CREATE INDEX IF NOT EXISTS idx_calibration_bucket ON calibration_log(probability_bucket);

CREATE INDEX IF NOT EXISTS idx_drift_sport ON drift_alerts(sport, created_at);
CREATE INDEX IF NOT EXISTS idx_drift_unresolved ON drift_alerts(resolved, severity);

-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

-- Current calibration status by sport
CREATE VIEW IF NOT EXISTS v_calibration_current AS
SELECT 
    sport,
    COUNT(*) as total_picks,
    SUM(CASE WHEN r.hit THEN 1 ELSE 0 END) as total_hits,
    ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END), 4) as actual_hit_rate,
    ROUND(AVG(p.probability), 4) as avg_predicted_probability,
    ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) - AVG(p.probability), 4) as calibration_error,
    ROUND(AVG((p.probability - CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) * 
              (p.probability - CASE WHEN r.hit THEN 1.0 ELSE 0.0 END)), 6) as brier_score
FROM picks p
JOIN results r ON p.pick_id = r.pick_id
WHERE p.game_date >= DATE('now', '-30 days')
GROUP BY sport;

-- Calibration by probability bucket
CREATE VIEW IF NOT EXISTS v_calibration_by_bucket AS
SELECT 
    sport,
    CASE 
        WHEN probability >= 0.75 THEN '75-100%'
        WHEN probability >= 0.65 THEN '65-74%'
        WHEN probability >= 0.55 THEN '55-64%'
        ELSE '< 55%'
    END as probability_bucket,
    COUNT(*) as n_picks,
    ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END), 4) as actual_hit_rate,
    ROUND(AVG(p.probability), 4) as expected_hit_rate,
    ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) - AVG(p.probability), 4) as calibration_error
FROM picks p
JOIN results r ON p.pick_id = r.pick_id
WHERE p.game_date >= DATE('now', '-30 days')
GROUP BY sport, probability_bucket
ORDER BY sport, probability_bucket DESC;

-- Performance by tier
CREATE VIEW IF NOT EXISTS v_performance_by_tier AS
SELECT 
    sport,
    confidence_tier,
    COUNT(*) as n_picks,
    SUM(CASE WHEN r.hit THEN 1 ELSE 0 END) as hits,
    ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) * 100, 1) as hit_rate_pct,
    ROUND(AVG(p.probability) * 100, 1) as expected_pct,
    ROUND((AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) - AVG(p.probability)) * 100, 1) as edge_pct
FROM picks p
JOIN results r ON p.pick_id = r.pick_id
WHERE p.game_date >= DATE('now', '-30 days')
GROUP BY sport, confidence_tier
ORDER BY sport, 
    CASE confidence_tier 
        WHEN 'SLAM' THEN 1 
        WHEN 'STRONG' THEN 2 
        WHEN 'LEAN' THEN 3 
        ELSE 4 
    END;

-- Performance by stat type
CREATE VIEW IF NOT EXISTS v_performance_by_stat AS
SELECT 
    sport,
    stat_type,
    COUNT(*) as n_picks,
    ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) * 100, 1) as hit_rate_pct,
    ROUND(AVG(p.probability) * 100, 1) as expected_pct,
    direction,
    ROUND(AVG(p.projected_value - p.line), 2) as avg_edge_vs_line
FROM picks p
JOIN results r ON p.pick_id = r.pick_id
WHERE p.game_date >= DATE('now', '-30 days')
GROUP BY sport, stat_type, direction
HAVING n_picks >= 10
ORDER BY sport, hit_rate_pct DESC;

-- Unresolved drift alerts
CREATE VIEW IF NOT EXISTS v_active_drift_alerts AS
SELECT *
FROM drift_alerts
WHERE resolved = FALSE
ORDER BY 
    CASE severity 
        WHEN 'CRITICAL' THEN 1 
        WHEN 'WARNING' THEN 2 
        ELSE 3 
    END,
    created_at DESC;
"""

# =============================================================================
# SAMPLE QUERIES
# =============================================================================

SAMPLE_QUERIES = {
    "daily_performance": """
        -- Daily performance summary
        SELECT 
            p.game_date,
            p.sport,
            COUNT(*) as picks,
            SUM(CASE WHEN r.hit THEN 1 ELSE 0 END) as hits,
            ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) * 100, 1) as hit_rate
        FROM picks p
        JOIN results r ON p.pick_id = r.pick_id
        WHERE p.game_date >= DATE('now', '-7 days')
        GROUP BY p.game_date, p.sport
        ORDER BY p.game_date DESC, p.sport;
    """,
    
    "calibration_by_bucket": """
        -- Calibration check by probability bucket
        SELECT 
            CASE 
                WHEN probability >= 0.75 THEN '75-100%%'
                WHEN probability >= 0.70 THEN '70-74%%'
                WHEN probability >= 0.65 THEN '65-69%%'
                WHEN probability >= 0.60 THEN '60-64%%'
                WHEN probability >= 0.55 THEN '55-59%%'
                ELSE '< 55%%'
            END as bucket,
            COUNT(*) as n,
            ROUND(AVG(probability) * 100, 1) as predicted_pct,
            ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) * 100, 1) as actual_pct,
            ROUND((AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) - AVG(probability)) * 100, 1) as error_pct
        FROM picks p
        JOIN results r ON p.pick_id = r.pick_id
        WHERE sport = ?
        GROUP BY bucket
        ORDER BY bucket DESC;
    """,
    
    "overconfidence_detection": """
        -- Detect overconfident predictions
        SELECT 
            sport,
            stat_type,
            confidence_tier,
            COUNT(*) as n_picks,
            ROUND(AVG(probability) * 100, 1) as avg_predicted,
            ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) * 100, 1) as actual,
            ROUND((AVG(probability) - AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END)) * 100, 1) as overconfidence
        FROM picks p
        JOIN results r ON p.pick_id = r.pick_id
        WHERE game_date >= DATE('now', '-30 days')
        GROUP BY sport, stat_type, confidence_tier
        HAVING n_picks >= 20 AND overconfidence > 5
        ORDER BY overconfidence DESC;
    """,
    
    "direction_bias": """
        -- Check for over/under bias
        SELECT 
            sport,
            direction,
            COUNT(*) as n_picks,
            ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) * 100, 1) as hit_rate,
            ROUND(AVG(probability) * 100, 1) as expected
        FROM picks p
        JOIN results r ON p.pick_id = r.pick_id
        WHERE game_date >= DATE('now', '-30 days')
        GROUP BY sport, direction
        ORDER BY sport, direction;
    """,
    
    "player_performance": """
        -- Player-level performance
        SELECT 
            player_name,
            sport,
            COUNT(*) as n_picks,
            ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) * 100, 1) as hit_rate,
            ROUND(AVG(probability) * 100, 1) as expected
        FROM picks p
        JOIN results r ON p.pick_id = r.pick_id
        WHERE game_date >= DATE('now', '-60 days')
        GROUP BY player_name, sport
        HAVING n_picks >= 10
        ORDER BY (hit_rate - expected) DESC
        LIMIT 20;
    """,
    
    "brier_score_trend": """
        -- Weekly Brier score trend
        SELECT 
            strftime('%%Y-%%W', game_date) as week,
            sport,
            COUNT(*) as n,
            ROUND(AVG((probability - CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) * 
                      (probability - CASE WHEN r.hit THEN 1.0 ELSE 0.0 END)), 6) as brier
        FROM picks p
        JOIN results r ON p.pick_id = r.pick_id
        WHERE game_date >= DATE('now', '-90 days')
        GROUP BY week, sport
        ORDER BY week DESC, sport;
    """,
    
    "stat_multipliers": """
        -- Calculate empirical stat multipliers for data_driven_penalties.py
        SELECT 
            stat_type,
            COUNT(*) as n,
            ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END), 4) as actual_rate,
            ROUND(AVG(probability), 4) as expected_rate,
            ROUND(AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) / NULLIF(AVG(probability), 0), 2) as multiplier
        FROM picks p
        JOIN results r ON p.pick_id = r.pick_id
        WHERE sport = ? AND game_date >= DATE('now', '-90 days')
        GROUP BY stat_type
        HAVING n >= 20
        ORDER BY multiplier DESC;
    """
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Pick:
    """Pick data structure"""
    pick_id: str
    sport: str
    game_id: str
    game_date: str
    player_name: str
    stat_type: str
    line: float
    direction: str
    projected_value: float
    probability: float
    confidence_tier: str
    player_id: Optional[str] = None
    team: Optional[str] = None
    opponent: Optional[str] = None
    model_version: Optional[str] = None
    is_primary: bool = True
    risk_tag: Optional[str] = None
    pick_state: Optional[str] = None
    edge_key: Optional[str] = None
    features_json: Optional[str] = None


@dataclass
class Result:
    """Result data structure"""
    pick_id: str
    actual_value: float
    hit: bool
    source: Optional[str] = None
    verified: bool = False


@dataclass
class CalibrationReport:
    """Calibration report structure"""
    sport: str
    period: str
    generated_at: str
    total_picks: int
    total_hits: int
    hit_rate: float
    expected_rate: float
    calibration_error: float
    brier_score: float
    by_tier: Dict[str, Dict]
    by_bucket: Dict[str, Dict]
    by_stat: Dict[str, Dict]
    by_direction: Dict[str, Dict]
    drift_alerts: List[Dict]
    
    def to_dict(self) -> Dict:
        return asdict(self)


# =============================================================================
# CALIBRATION TRACKER CLASS
# =============================================================================

class CalibrationTracker:
    """
    FUOOM Calibration Tracking System
    SOP v2.1 Compliant — Immutable Audit Trail
    """
    
    DEFAULT_DB_PATH = "data/calibration.db"
    
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path or self.DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
    
    @contextmanager
    def _get_connection(self):
        """Thread-safe database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _ensure_schema(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
    
    def log_pick(self, pick: Pick) -> bool:
        """Log a new pick (immutable insert)"""
        with self._get_connection() as conn:
            try:
                # Normalize direction
                direction = pick.direction.lower()
                if direction in ['higher', 'more']:
                    direction = 'over'
                elif direction in ['lower', 'less']:
                    direction = 'under'
                
                conn.execute("""
                    INSERT INTO picks (
                        pick_id, sport, game_id, game_date, player_id, player_name,
                        team, opponent, stat_type, line, direction, projected_value,
                        probability, confidence_tier, model_version, is_primary,
                        risk_tag, pick_state, edge_key, features_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pick.pick_id, pick.sport.upper(), pick.game_id, pick.game_date,
                    pick.player_id, pick.player_name, pick.team, pick.opponent,
                    pick.stat_type, pick.line, direction, pick.projected_value,
                    pick.probability, pick.confidence_tier, pick.model_version,
                    pick.is_primary, pick.risk_tag, pick.pick_state, 
                    pick.edge_key, pick.features_json
                ))
                return True
            except sqlite3.IntegrityError:
                return False
    
    def log_result(self, result: Result) -> bool:
        """Log a pick result (immutable insert)"""
        with self._get_connection() as conn:
            try:
                conn.execute("""
                    INSERT INTO results (pick_id, actual_value, hit, source, verified)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    result.pick_id, result.actual_value, result.hit,
                    result.source, result.verified
                ))
                return True
            except sqlite3.IntegrityError:
                return False
    
    def log_picks_batch(self, picks: List[Pick]) -> Tuple[int, int]:
        """Batch insert picks. Returns (success_count, failure_count)"""
        success, failures = 0, 0
        for pick in picks:
            if self.log_pick(pick):
                success += 1
            else:
                failures += 1
        return success, failures
    
    def log_results_batch(self, results: List[Result]) -> Tuple[int, int]:
        """Batch insert results. Returns (success_count, failure_count)"""
        success, failures = 0, 0
        for result in results:
            if self.log_result(result):
                success += 1
            else:
                failures += 1
        return success, failures
    
    def calculate_brier_score(self, predictions: List[float], outcomes: List[bool]) -> float:
        """Calculate Brier score (lower is better, 0 is perfect)"""
        if not predictions or len(predictions) != len(outcomes):
            return 1.0
        n = len(predictions)
        return sum((p - (1.0 if o else 0.0)) ** 2 for p, o in zip(predictions, outcomes)) / n
    
    def calculate_calibration_error(self, predictions: List[float], outcomes: List[bool]) -> float:
        """Calculate mean calibration error"""
        if not predictions:
            return 0.0
        avg_predicted = sum(predictions) / len(predictions)
        avg_actual = sum(1.0 if o else 0.0 for o in outcomes) / len(outcomes)
        return avg_predicted - avg_actual
    
    def generate_calibration_report(self, sport: str, period: str = None) -> CalibrationReport:
        """Generate comprehensive calibration report."""
        with self._get_connection() as conn:
            if period and len(period) == 7:
                date_filter = f"strftime('%Y-%m', p.game_date) = '{period}'"
            else:
                date_filter = "p.game_date >= DATE('now', '-30 days')"
            
            base_query = f"""
                SELECT p.*, r.actual_value, r.hit
                FROM picks p
                JOIN results r ON p.pick_id = r.pick_id
                WHERE p.sport = ? AND {date_filter}
            """
            
            rows = conn.execute(base_query, (sport.upper(),)).fetchall()
            
            if not rows:
                return CalibrationReport(
                    sport=sport, period=period or "last_30_days",
                    generated_at=datetime.utcnow().isoformat(),
                    total_picks=0, total_hits=0, hit_rate=0.0, expected_rate=0.0,
                    calibration_error=0.0, brier_score=1.0,
                    by_tier={}, by_bucket={}, by_stat={}, by_direction={}, drift_alerts=[]
                )
            
            predictions = [row['probability'] for row in rows]
            outcomes = [bool(row['hit']) for row in rows]
            
            total_picks = len(rows)
            total_hits = sum(outcomes)
            hit_rate = total_hits / total_picks
            expected_rate = sum(predictions) / total_picks
            brier = self.calculate_brier_score(predictions, outcomes)
            cal_error = self.calculate_calibration_error(predictions, outcomes)
            
            # By tier
            by_tier = {}
            for tier in ['SLAM', 'STRONG', 'LEAN', 'NO_PLAY']:
                tier_rows = [r for r in rows if r['confidence_tier'] == tier]
                if tier_rows:
                    tier_preds = [r['probability'] for r in tier_rows]
                    tier_outs = [bool(r['hit']) for r in tier_rows]
                    by_tier[tier] = {
                        'n': len(tier_rows),
                        'hits': sum(tier_outs),
                        'hit_rate': round(sum(tier_outs) / len(tier_outs), 4),
                        'expected': round(sum(tier_preds) / len(tier_preds), 4),
                        'brier': round(self.calculate_brier_score(tier_preds, tier_outs), 6)
                    }
            
            # By bucket
            by_bucket = {}
            buckets = [('75-100%', 0.75, 1.01), ('65-74%', 0.65, 0.75),
                       ('55-64%', 0.55, 0.65), ('< 55%', 0.0, 0.55)]
            for name, low, high in buckets:
                bucket_rows = [r for r in rows if low <= r['probability'] < high]
                if bucket_rows:
                    b_preds = [r['probability'] for r in bucket_rows]
                    b_outs = [bool(r['hit']) for r in bucket_rows]
                    by_bucket[name] = {
                        'n': len(bucket_rows), 'hits': sum(b_outs),
                        'actual_rate': round(sum(b_outs) / len(b_outs), 4),
                        'expected_rate': round(sum(b_preds) / len(b_preds), 4),
                        'calibration_error': round(self.calculate_calibration_error(b_preds, b_outs), 4)
                    }
            
            # By stat
            by_stat = {}
            for stat in set(r['stat_type'] for r in rows):
                s_rows = [r for r in rows if r['stat_type'] == stat]
                if len(s_rows) >= 10:
                    s_preds = [r['probability'] for r in s_rows]
                    s_outs = [bool(r['hit']) for r in s_rows]
                    by_stat[stat] = {
                        'n': len(s_rows),
                        'hit_rate': round(sum(s_outs) / len(s_outs), 4),
                        'expected': round(sum(s_preds) / len(s_preds), 4)
                    }
            
            # By direction
            by_direction = {}
            for direction in ['over', 'under']:
                d_rows = [r for r in rows if r['direction'] == direction]
                if d_rows:
                    d_preds = [r['probability'] for r in d_rows]
                    d_outs = [bool(r['hit']) for r in d_rows]
                    by_direction[direction] = {
                        'n': len(d_rows),
                        'hit_rate': round(sum(d_outs) / len(d_outs), 4),
                        'expected': round(sum(d_preds) / len(d_preds), 4)
                    }
            
            # Drift alerts
            drift_rows = conn.execute("""
                SELECT * FROM drift_alerts WHERE sport = ? AND resolved = FALSE
            """, (sport.upper(),)).fetchall()
            drift_alerts = [dict(r) for r in drift_rows]
            
            return CalibrationReport(
                sport=sport, period=period or "last_30_days",
                generated_at=datetime.utcnow().isoformat(),
                total_picks=total_picks, total_hits=total_hits,
                hit_rate=round(hit_rate, 4), expected_rate=round(expected_rate, 4),
                calibration_error=round(cal_error, 4), brier_score=round(brier, 6),
                by_tier=by_tier, by_bucket=by_bucket, by_stat=by_stat,
                by_direction=by_direction, drift_alerts=drift_alerts
            )
    
    def check_drift(self, sport: str, threshold: float = 0.05) -> List[Dict]:
        """Check for calibration drift."""
        alerts = []
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    CASE 
                        WHEN probability >= 0.75 THEN '75-100%'
                        WHEN probability >= 0.65 THEN '65-74%'
                        WHEN probability >= 0.55 THEN '55-64%'
                        ELSE '< 55%'
                    END as bucket,
                    AVG(probability) as expected,
                    AVG(CASE WHEN r.hit THEN 1.0 ELSE 0.0 END) as actual,
                    COUNT(*) as n
                FROM picks p
                JOIN results r ON p.pick_id = r.pick_id
                WHERE p.sport = ? AND p.game_date >= DATE('now', '-30 days')
                GROUP BY bucket HAVING n >= 20
            """, (sport.upper(),)).fetchall()
            
            for row in rows:
                drift = row['expected'] - row['actual']
                if abs(drift) > threshold:
                    severity = 'CRITICAL' if abs(drift) > 0.15 else ('WARNING' if abs(drift) > 0.08 else 'INFO')
                    alert = {
                        'sport': sport.upper(), 
                        'stat_type': None,
                        'metric': f'calibration_error_{row["bucket"]}',
                        'baseline_value': round(row['expected'], 4),
                        'current_value': round(row['actual'], 4),
                        'drift_magnitude': round(abs(drift), 4),
                        'drift_direction': 'overconfident' if drift > 0 else 'underconfident',
                        'severity': severity
                    }
                    alerts.append(alert)
                    conn.execute("""
                        INSERT INTO drift_alerts (sport, stat_type, metric, baseline_value, 
                            current_value, drift_magnitude, drift_direction, severity)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (alert['sport'], alert['stat_type'], alert['metric'],
                          alert['baseline_value'], alert['current_value'],
                          alert['drift_magnitude'], alert['drift_direction'], alert['severity']))
        return alerts
    
    def run_query(self, query_name: str, params: tuple = ()) -> List[Dict]:
        """Run a named query from SAMPLE_QUERIES"""
        if query_name not in SAMPLE_QUERIES:
            raise ValueError(f"Unknown query: {query_name}")
        with self._get_connection() as conn:
            rows = conn.execute(SAMPLE_QUERIES[query_name], params).fetchall()
            return [dict(row) for row in rows]
    
    def export_to_csv(self, output_path: str, sport: str = None,
                      start_date: str = None, end_date: str = None) -> int:
        """Export picks and results to CSV"""
        import csv
        with self._get_connection() as conn:
            query = """
                SELECT p.*, r.actual_value, r.hit, r.recorded_at as result_recorded_at
                FROM picks p LEFT JOIN results r ON p.pick_id = r.pick_id WHERE 1=1
            """
            params = []
            if sport:
                query += " AND p.sport = ?"
                params.append(sport.upper())
            if start_date:
                query += " AND p.game_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND p.game_date <= ?"
                params.append(end_date)
            
            rows = conn.execute(query, params).fetchall()
            if not rows:
                return 0
            
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))
            return len(rows)
    
    def get_pending_picks(self, sport: str = None) -> List[Dict]:
        """Get picks without results"""
        with self._get_connection() as conn:
            query = """
                SELECT p.* FROM picks p
                LEFT JOIN results r ON p.pick_id = r.pick_id
                WHERE r.pick_id IS NULL
            """
            params = []
            if sport:
                query += " AND p.sport = ?"
                params.append(sport.upper())
            
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]


def print_calibration_report(report: CalibrationReport):
    """Pretty print calibration report"""
    print("\n" + "=" * 70)
    print(f"  FUOOM CALIBRATION REPORT — {report.sport}")
    print(f"  Period: {report.period}")
    print("=" * 70)
    
    print(f"\n  OVERALL METRICS")
    print("-" * 70)
    print(f"  Total Picks:        {report.total_picks}")
    print(f"  Total Hits:         {report.total_hits}")
    print(f"  Hit Rate:           {report.hit_rate * 100:.1f}%")
    print(f"  Expected Rate:      {report.expected_rate * 100:.1f}%")
    print(f"  Calibration Error:  {report.calibration_error * 100:+.1f}%")
    print(f"  Brier Score:        {report.brier_score:.4f}")
    
    if report.calibration_error > 0.05:
        print(f"  ⚠️  OVERCONFIDENT by {report.calibration_error * 100:.1f}%")
    elif report.calibration_error < -0.05:
        print(f"  ⚠️  UNDERCONFIDENT by {abs(report.calibration_error) * 100:.1f}%")
    else:
        print(f"  ✓  WELL CALIBRATED")
    
    if report.by_tier:
        print(f"\n  BY TIER")
        print("-" * 70)
        print(f"  {'Tier':<10} {'N':>6} {'Hits':>6} {'Actual':>8} {'Expected':>8}")
        for tier, data in report.by_tier.items():
            print(f"  {tier:<10} {data['n']:>6} {data['hits']:>6} "
                  f"{data['hit_rate']*100:>7.1f}% {data['expected']*100:>7.1f}%")
    
    if report.by_bucket:
        print(f"\n  BY PROBABILITY BUCKET")
        print("-" * 70)
        print(f"  {'Bucket':<10} {'N':>6} {'Actual':>8} {'Expected':>8} {'Error':>8}")
        for bucket, data in report.by_bucket.items():
            print(f"  {bucket:<10} {data['n']:>6} "
                  f"{data['actual_rate']*100:>7.1f}% {data['expected_rate']*100:>7.1f}% "
                  f"{data['calibration_error']*100:>+7.1f}%")
    
    if report.by_direction:
        print(f"\n  BY DIRECTION")
        print("-" * 70)
        for direction, data in report.by_direction.items():
            edge = (data['hit_rate'] - data['expected']) * 100
            print(f"  {direction.upper():<10} n={data['n']:<4} "
                  f"Hit: {data['hit_rate']*100:.1f}% Exp: {data['expected']*100:.1f}% Edge: {edge:+.1f}%")
    
    if report.drift_alerts:
        print(f"\n  ⚠️  ACTIVE DRIFT ALERTS: {len(report.drift_alerts)}")
        for alert in report.drift_alerts:
            print(f"  [{alert['severity']}] {alert['metric']}: "
                  f"{alert['drift_direction']} by {alert['drift_magnitude']*100:.1f}%")
    
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="FUOOM Calibration Tracker")
    parser.add_argument('--db', default='data/calibration.db', help='Database path')
    parser.add_argument('--init', action='store_true', help='Initialize database')
    parser.add_argument('--report', action='store_true', help='Generate report')
    parser.add_argument('--check-drift', action='store_true', help='Check for drift')
    parser.add_argument('--query', help='Run named query')
    parser.add_argument('--list-queries', action='store_true', help='List queries')
    parser.add_argument('--export', action='store_true', help='Export to CSV')
    parser.add_argument('--pending', action='store_true', help='List picks without results')
    parser.add_argument('--sport', help='Sport filter')
    parser.add_argument('--period', help='Period (YYYY-MM)')
    parser.add_argument('--output', '-o', help='Output file')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--threshold', type=float, default=0.05, help='Drift threshold')
    
    args = parser.parse_args()
    tracker = CalibrationTracker(args.db)
    
    if args.init:
        print(f"[INIT] Database initialized at {args.db}")
        return
    
    if args.list_queries:
        print("\nAvailable Queries:")
        for name in SAMPLE_QUERIES:
            print(f"  {name}")
        return
    
    if args.report:
        if not args.sport:
            print("[ERROR] --sport required")
            sys.exit(1)
        report = tracker.generate_calibration_report(args.sport, args.period)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2, default=str))
        else:
            print_calibration_report(report)
        return
    
    if args.check_drift:
        if not args.sport:
            print("[ERROR] --sport required")
            sys.exit(1)
        alerts = tracker.check_drift(args.sport, args.threshold)
        if alerts:
            print(f"\n⚠️  DRIFT DETECTED: {len(alerts)} alerts")
            for alert in alerts:
                print(f"  [{alert['severity']}] {alert['metric']}: {alert['drift_direction']}")
        else:
            print(f"\n✓ No drift detected for {args.sport}")
        return
    
    if args.query:
        params = (args.sport.upper(),) if args.sport and '?' in SAMPLE_QUERIES.get(args.query, '') else ()
        results = tracker.run_query(args.query, params)
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            for row in results[:50]:
                print(row)
        return
    
    if args.export:
        output = args.output or f"export_{datetime.now().strftime('%Y%m%d')}.csv"
        count = tracker.export_to_csv(output, sport=args.sport)
        print(f"[EXPORT] {count} records to {output}")
        return
    
    if args.pending:
        pending = tracker.get_pending_picks(args.sport)
        print(f"\nPending picks (no results): {len(pending)}")
        for p in pending[:20]:
            print(f"  {p['pick_id']}: {p['player_name']} {p['stat_type']} {p['direction']} {p['line']}")
        return
    
    parser.print_help()


if __name__ == "__main__":
    main()
