"""
Regret Metrics Integration for FUOOM Dashboard
- Loads pick history from cache/pick_history.db
- Computes regret metrics using core/regret.py
- Exposes regret summary for dashboard/app.py
"""

import sys
from pathlib import Path
import sqlite3
from core.regret import compute_regret

PICK_DB = Path("cache/pick_history.db")

def get_regret_metrics():
    if not PICK_DB.exists():
        return {"total": 0, "regret_sum": 0.0, "opportunity_cost": 0.0, "avg_regret": 0.0}
    conn = sqlite3.connect(str(PICK_DB))
    conn.row_factory = sqlite3.Row
    picks = conn.execute('SELECT * FROM picks WHERE hit IS NOT NULL').fetchall()
    conn.close()
    regrets = []
    for row in picks:
        # Build edge-like object for regret computation
        edge = type('Edge', (), {})()
        edge.edge_id = row['pick_id'] if 'pick_id' in row.keys() else row['id']
        edge.raw_probability = row['confidence'] if 'confidence' in row.keys() else 0.5
        edge.execution_probability = row['confidence'] if 'confidence' in row.keys() else 0.5
        edge.executed = True  # All resolved picks are executed
        edge.outcome = bool(row['hit'])
        regret = compute_regret(edge)
        if regret:
            regrets.append(regret)
    if not regrets:
        return {"total": 0, "regret_sum": 0.0, "opportunity_cost": 0.0, "avg_regret": 0.0}
    regret_sum = sum(r.regret_score for r in regrets)
    opportunity_cost = sum(r.opportunity_cost for r in regrets)
    avg_regret = regret_sum / len(regrets)
    return {
        "total": len(regrets),
        "regret_sum": regret_sum,
        "opportunity_cost": opportunity_cost,
        "avg_regret": avg_regret
    }
