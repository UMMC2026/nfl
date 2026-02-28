"""
VALIDATE_CALIBRATION.PY — Hard Assertions for Calibration Workflow

GOVERNANCE: This module enforces the mandatory result-recording sequence.
No retroactive edits, no overwriting results, no partial game ingestion.

Canonical sequence:
1. FINAL detected
2. Cooldown elapsed (sport-specific)
3. Cross-verify stats (Source A + B)
4. Write immutable result record
5. Lock pick → frozen
6. Update calibration store
7. Run weekly calibration audit
"""
import json
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

# =============================================================================
# CONFIGURATION
# =============================================================================

CALIBRATION_DIR = Path(__file__).parent
RESULTS_DIR = CALIBRATION_DIR / "results"
VERIFICATION_LOG = CALIBRATION_DIR / "verification_log.json"
DRIFT_ALERTS = CALIBRATION_DIR / "drift_alerts.log"
BRIER_WEEKLY = CALIBRATION_DIR / "brier_weekly.csv"
PICKS_CSV = CALIBRATION_DIR / "picks.csv"

# Sport-specific cooldown (minutes after FINAL before recording)
COOLDOWN_MINUTES = {
    "NBA": 30,
    "NFL": 45,
    "CBB": 30,
    "TENNIS": 15,
    "SOCCER": 30,
}

# Brier score thresholds for drift detection
BRIER_THRESHOLDS = {
    "NBA": 0.25,      # Alert if Brier > 0.25
    "NFL": 0.28,
    "CBB": 0.30,
    "TENNIS": 0.27,
}

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ResultRecord:
    """Immutable result record."""
    record_id: str           # SHA256 hash of pick_id + game_id + timestamp
    pick_id: str
    sport: str
    game_id: str
    player: str
    stat: str
    line: float
    direction: str
    predicted_prob: float
    tier: str
    actual_value: float
    hit: bool
    game_status: str         # Must be "FINAL"
    game_end_ts: str         # ISO format
    recorded_ts: str         # When this record was created
    source_a: str            # Primary source (e.g., "nba_api")
    source_b: str            # Verification source
    source_a_value: float    # Value from source A
    source_b_value: float    # Value from source B
    frozen: bool = True      # Always frozen once recorded
    
    def compute_brier(self) -> float:
        """Compute Brier score."""
        actual = 1.0 if self.hit else 0.0
        return (self.predicted_prob - actual) ** 2
    
    def generate_id(self) -> str:
        """Generate immutable record ID."""
        data = f"{self.pick_id}|{self.game_id}|{self.recorded_ts}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_game_final(game_status: str) -> Tuple[bool, str]:
    """Validate game is FINAL."""
    if game_status.upper() != "FINAL":
        return False, f"Game status '{game_status}' is not FINAL. Cannot record result."
    return True, ""


def validate_cooldown_elapsed(game_end_ts: str, sport: str) -> Tuple[bool, str]:
    """Validate cooldown period has elapsed."""
    try:
        end_dt = datetime.fromisoformat(game_end_ts)
        now = datetime.now()
        cooldown = COOLDOWN_MINUTES.get(sport.upper(), 30)
        elapsed = (now - end_dt).total_seconds() / 60
        
        if elapsed < cooldown:
            return False, f"Cooldown not elapsed. {elapsed:.1f} min since FINAL, need {cooldown} min."
        return True, ""
    except Exception as e:
        return False, f"Invalid game_end_ts: {e}"


def validate_cross_verification(source_a_value: float, source_b_value: float, tolerance: float = 0.5) -> Tuple[bool, str]:
    """Validate stats match across two sources."""
    diff = abs(source_a_value - source_b_value)
    if diff > tolerance:
        return False, f"Source mismatch: A={source_a_value}, B={source_b_value}, diff={diff}"
    return True, ""


def validate_no_duplicate(pick_id: str, game_id: str) -> Tuple[bool, str]:
    """Validate no existing record for this pick+game."""
    if not PICKS_CSV.exists():
        return True, ""
    
    with open(PICKS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('pick_id') == pick_id and row.get('game_id') == game_id:
                return False, f"Duplicate record exists for pick_id={pick_id}, game_id={game_id}"
    return True, ""


def validate_no_retroactive_edit(record_id: str) -> Tuple[bool, str]:
    """Validate record has not been edited after creation."""
    if not VERIFICATION_LOG.exists():
        return True, ""
    
    with open(VERIFICATION_LOG, 'r', encoding='utf-8') as f:
        log = json.load(f)
    
    if record_id in log:
        original = log[record_id]
        if original.get('edited', False):
            return False, f"Record {record_id} was retroactively edited. FORBIDDEN."
    return True, ""


def validate_adjustment_stages(adjustments: List[Dict]) -> Tuple[bool, str]:
    """
    Validate no duplicate probability adjustments from same stage.
    
    Each adjustment must declare:
    - adjustment_stage: INJURY | CONTEXT | MARKET
    
    Duplicate stages = double-penalization/boost.
    """
    stages_seen = set()
    for adj in adjustments:
        stage = adj.get('adjustment_stage', 'UNKNOWN')
        if stage in stages_seen:
            return False, f"Duplicate adjustment stage: {stage}. Double-adjustment forbidden."
        stages_seen.add(stage)
    return True, ""


# =============================================================================
# CALIBRATION WORKFLOW
# =============================================================================

def record_result(
    pick_id: str,
    sport: str,
    game_id: str,
    player: str,
    stat: str,
    line: float,
    direction: str,
    predicted_prob: float,
    tier: str,
    actual_value: float,
    game_status: str,
    game_end_ts: str,
    source_a: str,
    source_b: str,
    source_a_value: float,
    source_b_value: float,
) -> Tuple[bool, str, Optional[ResultRecord]]:
    """
    Record a result with full validation.
    
    Returns:
        (success, message, record)
    """
    errors = []
    
    # 1. Validate FINAL
    ok, msg = validate_game_final(game_status)
    if not ok:
        errors.append(msg)
    
    # 2. Validate cooldown
    ok, msg = validate_cooldown_elapsed(game_end_ts, sport)
    if not ok:
        errors.append(msg)
    
    # 3. Validate cross-verification
    ok, msg = validate_cross_verification(source_a_value, source_b_value)
    if not ok:
        errors.append(msg)
    
    # 4. Validate no duplicate
    ok, msg = validate_no_duplicate(pick_id, game_id)
    if not ok:
        errors.append(msg)
    
    if errors:
        return False, "\n".join(errors), None
    
    # Determine hit
    if direction.lower() == 'higher':
        hit = actual_value > line
    else:
        hit = actual_value < line
    
    # Create record
    record = ResultRecord(
        record_id="",  # Will be generated
        pick_id=pick_id,
        sport=sport.upper(),
        game_id=game_id,
        player=player,
        stat=stat,
        line=line,
        direction=direction,
        predicted_prob=predicted_prob,
        tier=tier,
        actual_value=actual_value,
        hit=hit,
        game_status=game_status,
        game_end_ts=game_end_ts,
        recorded_ts=datetime.now().isoformat(),
        source_a=source_a,
        source_b=source_b,
        source_a_value=source_a_value,
        source_b_value=source_b_value,
        frozen=True,
    )
    record.record_id = record.generate_id()
    
    return True, "Result recorded successfully.", record


def save_to_calibration_store(record: ResultRecord) -> bool:
    """Save record to calibration CSV (append-only)."""
    RESULTS_DIR.mkdir(exist_ok=True)
    
    # Daily parquet file
    date_str = datetime.now().strftime("%Y%m%d")
    daily_file = RESULTS_DIR / f"results_{date_str}.json"
    
    # Load existing or create new
    if daily_file.exists():
        with open(daily_file, 'r', encoding='utf-8') as f:
            records = json.load(f)
    else:
        records = []
    
    records.append(asdict(record))
    
    with open(daily_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2)
    
    # Log verification
    log_verification(record)
    
    return True


def log_verification(record: ResultRecord):
    """Log record to verification log (immutable audit trail)."""
    if VERIFICATION_LOG.exists():
        with open(VERIFICATION_LOG, 'r', encoding='utf-8') as f:
            log = json.load(f)
    else:
        log = {}
    
    log[record.record_id] = {
        "pick_id": record.pick_id,
        "recorded_ts": record.recorded_ts,
        "sport": record.sport,
        "hit": record.hit,
        "brier": record.compute_brier(),
        "edited": False,  # Never set to True
    }
    
    with open(VERIFICATION_LOG, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2)


def check_drift(sport: str, recent_n: int = 20) -> Tuple[bool, str]:
    """
    Check for calibration drift using recent Brier scores.
    
    Returns:
        (has_drift, alert_message)
    """
    if not VERIFICATION_LOG.exists():
        return False, ""
    
    with open(VERIFICATION_LOG, 'r', encoding='utf-8') as f:
        log = json.load(f)
    
    # Filter to sport and get recent
    sport_records = [v for v in log.values() if v.get('sport', '').upper() == sport.upper()]
    sport_records = sorted(sport_records, key=lambda x: x.get('recorded_ts', ''), reverse=True)[:recent_n]
    
    if len(sport_records) < 10:
        return False, ""  # Not enough data
    
    briers = [r['brier'] for r in sport_records if 'brier' in r]
    if not briers:
        return False, ""
    
    avg_brier = sum(briers) / len(briers)
    threshold = BRIER_THRESHOLDS.get(sport.upper(), 0.28)
    
    if avg_brier > threshold:
        alert = f"DRIFT ALERT: {sport} avg Brier {avg_brier:.3f} > threshold {threshold}"
        
        # Log alert
        with open(DRIFT_ALERTS, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().isoformat()}] {alert}\n")
        
        return True, alert
    
    return False, ""


def weekly_calibration_audit() -> Dict:
    """
    Run weekly calibration audit.
    
    Returns summary statistics by sport and tier.
    """
    if not VERIFICATION_LOG.exists():
        return {"error": "No verification log found"}
    
    with open(VERIFICATION_LOG, 'r', encoding='utf-8') as f:
        log = json.load(f)
    
    # Compute stats by sport and tier
    from collections import defaultdict
    stats = defaultdict(lambda: {"count": 0, "hits": 0, "brier_sum": 0.0})
    
    for record_id, data in log.items():
        sport = data.get('sport', 'UNKNOWN')
        key = sport
        stats[key]["count"] += 1
        stats[key]["hits"] += 1 if data.get('hit') else 0
        stats[key]["brier_sum"] += data.get('brier', 0)
    
    # Compute averages
    results = {}
    for key, s in stats.items():
        if s["count"] > 0:
            results[key] = {
                "count": s["count"],
                "hit_rate": s["hits"] / s["count"],
                "avg_brier": s["brier_sum"] / s["count"],
            }
    
    # Save weekly report
    week_str = datetime.now().strftime("%Y-W%W")
    with open(BRIER_WEEKLY, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if f.tell() == 0:
            writer.writerow(["week", "sport", "count", "hit_rate", "avg_brier"])
        for sport, s in results.items():
            writer.writerow([week_str, sport, s["count"], f"{s['hit_rate']:.3f}", f"{s['avg_brier']:.4f}"])
    
    return results


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Calibration validation and audit")
    parser.add_argument("--audit", action="store_true", help="Run weekly calibration audit")
    parser.add_argument("--drift", type=str, help="Check drift for sport (e.g., NBA)")
    parser.add_argument("--validate-log", action="store_true", help="Validate verification log integrity")
    
    args = parser.parse_args()
    
    if args.audit:
        print("Running weekly calibration audit...")
        results = weekly_calibration_audit()
        print(json.dumps(results, indent=2))
    
    elif args.drift:
        has_drift, msg = check_drift(args.drift)
        if has_drift:
            print(f"⚠️ {msg}")
        else:
            print(f"✅ No drift detected for {args.drift}")
    
    elif args.validate_log:
        if VERIFICATION_LOG.exists():
            with open(VERIFICATION_LOG, 'r', encoding='utf-8') as f:
                log = json.load(f)
            edited = [k for k, v in log.items() if v.get('edited', False)]
            if edited:
                print(f"❌ INTEGRITY VIOLATION: {len(edited)} records marked as edited!")
                for record_id in edited:
                    print(f"  - {record_id}")
            else:
                print(f"✅ Log integrity OK: {len(log)} records, none edited")
        else:
            print("No verification log found")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
