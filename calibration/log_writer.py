"""
Calibration Log Writer — Logs every pick and result to CSV for CBB calibration.
"""
import csv
from pathlib import Path
from datetime import datetime

LOG_PATH = Path(__file__).parent / "picks.csv"


def log_pick_result(edge_id, player, stat, line, direction, probability, tier, pick_state, result=None, timestamp=None):
    """
    Log a pick and its result (if available) to the calibration CSV.
    """
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    row = {
        "timestamp": timestamp,
        "edge_id": edge_id,
        "player": player,
        "stat": stat,
        "line": line,
        "direction": direction,
        "probability": probability,
        "tier": tier,
        "pick_state": pick_state,
        "result": result
    }
    file_exists = LOG_PATH.exists()
    with open(LOG_PATH, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
