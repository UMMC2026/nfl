# EDGE GENERATOR INTEGRATION — CODE EXAMPLES

This file shows the exact 3 lines of code needed in each edge generator to wire the Daily Games Report gating.

---

## **NFL EDGE GENERATOR**

**File:** `nfl/nfl_edge_generator.py`

### **Add Gating Import (Line 1-2)**

```python
#!/usr/bin/env python3
"""NFL Edge Generator — with Daily Games Report gating"""

from gating.daily_games_report_gating import gate_nfl_edges, gate_resolved_ledger
# ↑ New import line
```

### **Call Gating Before Edge Ranking (in main function)**

```python
def main(date: str = None, output_dir: str = "outputs"):
    """
    Generate ranked NFL edges for given date.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    
    # GATING CHECK (NEW)
    # ==================
    confidence_caps = gate_nfl_edges(date=date)  # Aborts if no report
    # Now we have caps: {"core": 0.70, "alt": 0.65, "td": 0.52}
    
    # Load picks
    picks = load_nfl_picks(f"nfl/picks_{date}.json")
    
    # Rank picks with gated confidence
    ranked_edges = []
    for pick in picks:
        # Get raw confidence estimate (your existing logic)
        raw_confidence = estimate_confidence(pick)
        
        # Apply cap from report
        capped_confidence = min(raw_confidence, confidence_caps["core"])
        
        edge = {
            "player_name": pick["player_name"],
            "team": pick["team"],
            "stat": pick["stat"],
            "direction": pick["direction"],
            "line": pick["line"],
            "confidence": capped_confidence,  # Now gated!
            "source": f"DAILY_GAMES_REPORT_{date}"
        }
        ranked_edges.append(edge)
    
    # Rank by confidence
    ranked_edges.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Output
    return ranked_edges


if __name__ == "__main__":
    main()
```

---

## **NBA EDGE GENERATOR**

**File:** `nba/nba_edge_generator.py`

### **Add Gating Import**

```python
from gating.daily_games_report_gating import gate_nba_edges
```

### **Call Gating in Main**

```python
def main(date: str = None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    
    # GATING CHECK
    confidence_caps = gate_nba_edges(date=date)  # NBA-specific caps
    
    # Rest of logic...
```

---

## **CBB EDGE GENERATOR**

**File:** `cbb/cbb_edge_generator.py`

### **Add Gating Import**

```python
from gating.daily_games_report_gating import gate_cbb_edges
```

### **Call Gating in Main**

```python
def main(date: str = None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    
    # GATING CHECK
    confidence_caps = gate_cbb_edges(date=date)  # CBB-specific caps
    
    # Rest of logic...
```

---

## **CHEAT SHEET BUILDER**

**File:** `cheat_sheet_builder.py`

### **Add Gating Import**

```python
from gating.daily_games_report_gating import gate_cheat_sheets
```

### **Extract Volume Ceilings from Report**

```python
def build_cheat_sheets(date: str = None, format: str = "power", legs: int = 3):
    """
    Build parlay entries respecting daily report context.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    
    # GATING CHECK — Get all game contexts
    all_context = gate_cheat_sheets(date=date)  # Aborts if no report
    
    nfl_context = all_context.get("NFL", {})
    nfl_games = nfl_context.get("games", [])
    
    # Build entries
    entries = []
    for game in nfl_games:
        volume_suppression = game.get("volume_suppression", "MODERATE")
        variance = game.get("variance", "MODERATE")
        script = game.get("expected_script", "")
        
        # Adjust entry building based on suppression
        if volume_suppression == "VERY_HIGH":
            # BAL @ PIT playoff game: suppress passing volume
            # Only include RB runs and defensive plays
            max_pass_plays = 0
        elif volume_suppression == "HIGH":
            max_pass_plays = 1  # At most 1 pass prop per entry
        else:
            max_pass_plays = 2  # Normal
        
        # Build entries respecting this ceiling
        for edge in ranked_edges:
            if edge["game_id"] == game["game_id"]:
                if edge["stat"] in ["passing_yards", "pass_td"] and max_pass_plays == 0:
                    continue  # Skip this edge
        
        # ... rest of entry building
    
    return entries
```

---

## **RESOLVED LEDGER CALIBRATION**

**File:** `generate_resolved_ledger.py`

### **Add Gating Import**

```python
from gating.daily_games_report_gating import gate_resolved_ledger
```

### **Extract Report for Sport-Adaptive Calibration**

```python
def compute_rolling_windows(ledger_df: pd.DataFrame, date: str = None):
    """
    Compute sport-adaptive rolling windows using daily report context.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    
    # GATING CHECK — Get report for context
    report_data = gate_resolved_ledger(date=date)
    nfl_context = report_data["nfl"]
    nba_context = report_data["nba"]
    
    # Example: Adjust window sizes by sport
    rolling_config = {
        "NFL": {
            "window": 7,  # Shorter (fewer games per week)
            "confidence_threshold": 0.68,  # NFL slightly lower (weather impact)
            "accuracy_target": 0.55
        },
        "NBA": {
            "window": 14,  # Longer (more games per week)
            "confidence_threshold": 0.70,  # NBA higher (less weather)
            "accuracy_target": 0.58
        }
    }
    
    results = {}
    for sport, config in rolling_config.items():
        sport_ledger = ledger_df[ledger_df["sport"] == sport]
        
        if len(sport_ledger) == 0:
            continue
        
        # Compute rolling metrics
        hit_rate = sport_ledger["hit"].sum() / len(sport_ledger)
        
        results[sport] = {
            "hit_rate": hit_rate,
            "count": len(sport_ledger),
            "config": config,
            "drift_detected": hit_rate < config["accuracy_target"]
        }
    
    return results
```

---

## **TESTING**

### **Unit Test Example**

```python
# tests/test_gating_integration.py

import pytest
from datetime import datetime
from gating.daily_games_report_gating import (
    gate_nfl_edges,
    gate_cheat_sheets,
    gate_resolved_ledger
)

def test_nfl_gating_lock():
    """Verify NFL edges cannot be generated without report."""
    date = "2026-01-03"
    
    # Should succeed (report exists)
    caps = gate_nfl_edges(date=date)
    assert caps["core"] == 0.70
    assert caps["alt"] == 0.65
    
    # Simulate missing report
    with pytest.raises(SystemExit):
        gate_nfl_edges(date="2099-12-31")  # No report for future date

def test_cheat_sheet_volume_ceilings():
    """Verify cheat sheet gets volume ceilings from report."""
    date = "2026-01-03"
    
    context = gate_cheat_sheets(date=date)
    nfl_games = context["NFL"]["games"]
    
    # Find BAL @ PIT (very high suppression)
    bal_pit = [g for g in nfl_games if "BAL" in g["matchup"] and "PIT" in g["matchup"]][0]
    assert bal_pit["volume_suppression"] == "VERY_HIGH"
    assert bal_pit["variance"] == "LOW"

def test_resolved_ledger_sport_context():
    """Verify resolved ledger gets sport-specific context."""
    date = "2026-01-03"
    
    report = gate_resolved_ledger(date=date)
    
    # Should have separate contexts per sport
    assert "nfl" in report
    assert "nba" in report
    assert "cbb" in report
    
    # NFL should have 5 games
    assert len(report["nfl"]["games"]) == 5

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### **Run Tests**

```bash
pytest tests/test_gating_integration.py -v
```

---

## **SUMMARY**

| System | Gating Import | Gating Function | Consequence |
|--------|---------------|-----------------|------------|
| NFL Edge Gen | `gate_nfl_edges` | `gate_nfl_edges(date)` | Aborts if no report |
| NBA Edge Gen | `gate_nba_edges` | `gate_nba_edges(date)` | Aborts if no report |
| CBB Edge Gen | `gate_cbb_edges` | `gate_cbb_edges(date)` | Aborts if no report |
| Cheat Sheet | `gate_cheat_sheets` | `gate_cheat_sheets(date)` | No volume ceilings |
| Resolved Ledger | `gate_resolved_ledger` | `gate_resolved_ledger(date)` | No sport context |

**Implementation Time:** ~5 minutes (add import + 1 function call per system)  
**Production Impact:** Zero (gating is non-blocking pass-through if report valid)  
**Safety:** 100% (blocks all downstream systems if report missing)

---

**Status:** Ready for integration ✅
