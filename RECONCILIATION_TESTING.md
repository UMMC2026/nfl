# Reconciliation Testing Guide

## Quick Test: Manually Update a Pick Result

### **Step 1: Check Current State**
```python
from ufa.analysis.results_tracker import ResultsTracker

tracker = ResultsTracker()
perf = tracker.get_daily_performance("2025-12-31")
print(f"Dec 31: {perf.resolved_count} resolved | {perf.pending} pending")
# Output: Dec 31: 0 resolved | 46 pending
```

### **Step 2: Update One Pick Result**
```python
tracker.update_result(
    date="2025-12-31",
    player="OG Anunoby",
    stat="points",
    result="HIT",
    actual_value=18.5
)
```

### **Step 3: Verify Display Updates**
```python
perf = tracker.get_daily_performance("2025-12-31")
print(f"Dec 31: {perf.resolved_count} resolved | {perf.pending} pending")
print(f"Record: {perf.hits}-{perf.misses} ({perf.win_rate*100:.0f}%)")

# Expected output:
# Dec 31: 1 resolved | 45 pending
# Record: 1-0 (100%)
```

### **Step 4: Check Cheatsheet Display**
```python
from ufa.daily_pipeline import DailyPipeline

pipeline = DailyPipeline()
cheatsheet = pipeline.generate_cheat_sheet()

# Should show:
# 📈 YESTERDAY'S PERFORMANCE (2025-12-31)
# ==================================================
#   Status: 1 resolved | 45 pending
#   Resolved Record: 1-0 (100%)
#   SLAM Plays: 1/1 (100%)
#   ROI (resolved): +1.0 units
```

---

## Full Test Suite (From Root)

```bash
# 1. Run unit tests
pytest sports_quant/tests/ -v

# 2. Manual integration test
python -c "
from ufa.analysis.results_tracker import ResultsTracker

tracker = ResultsTracker()

# Before
perf_before = tracker.get_daily_performance('2025-12-31')
print('BEFORE:')
print(f'  Resolved: {perf_before.resolved_count}')
print(f'  Pending: {perf_before.pending}')
print(f'  Record: {perf_before.hits}-{perf_before.misses}')

# Update a pick
tracker.update_result('2025-12-31', 'OG Anunoby', 'points', 'HIT', 18.5)

# After
perf_after = tracker.get_daily_performance('2025-12-31')
print('\nAFTER:')
print(f'  Resolved: {perf_after.resolved_count}')
print(f'  Pending: {perf_after.pending}')
print(f'  Record: {perf_after.hits}-{perf_after.misses}')

print('\n✅ Reconciliation working!')
"

# 3. Generate fresh cheatsheet
python -c "
from ufa.daily_pipeline import DailyPipeline
pipeline = DailyPipeline()
cheatsheet = pipeline.generate_cheat_sheet()
print(cheatsheet[:1000])  # Print first 1000 chars
"
```

---

## Data File Format (results_YYYY-MM-DD.json)

Each pick can be updated:

```json
{
  "date": "2025-12-31",
  "updated_at": "2026-01-01T21:54:00",
  "picks": [
    {
      "date": "2025-12-31",
      "player": "OG Anunoby",
      "team": "NYK",
      "stat": "points",
      "line": 16.5,
      "direction": "higher",
      "tier": "SLAM",
      "confidence": 0.75,
      "result": "PENDING",           # ← Update to HIT/MISS/PUSH
      "actual_value": null            # ← Fill with actual stat value
    }
  ]
}
```

### **Bulk Update Method**
```python
tracker.bulk_update_results("2025-12-31", [
    {"player": "OG Anunoby", "stat": "points", "result": "HIT", "actual_value": 18.5},
    {"player": "Jamal Shead", "stat": "points", "result": "MISS", "actual_value": 6.2},
    {"player": "Giannis Antetokounmpo", "stat": "points", "result": "PUSH", "actual_value": 27.5},
])
```

---

## Expected Display Changes

### **State 0: All Pending (Current)**
```
📈 YESTERDAY'S PERFORMANCE (2025-12-31)
==================================================
  Status: 0 resolved | 46 pending
  ⏳ Waiting for game results...
```

### **State 1: Some Resolved (After 3 Updates)**
```
📈 YESTERDAY'S PERFORMANCE (2025-12-31)
==================================================
  Status: 3 resolved | 43 pending
  Resolved Record: 2-1 (67%)
  SLAM Plays: 2/2 (100%)
  STRONG Plays: 0/1 (0%)
  ROI (resolved): +1.0 units
```

### **State 2: All Resolved (After 46 Updates)**
```
📈 YESTERDAY'S PERFORMANCE (2025-12-31)
==================================================
  Status: 46 resolved | 0 pending
  Resolved Record: 32-14 (70%)
  SLAM Plays: 12/12 (100%)
  STRONG Plays: 15/22 (68%)
  LEAN Plays: 5/12 (42%)
  ROI (resolved): +18.0 units
```

---

## Next Implementation Steps

### **Phase 1: Reconciliation Input (Choose One)**

**Option A: Manual CSV Upload**
```python
def ingest_csv_results(csv_path: str):
    """Load results from CSV with columns: player,stat,result,actual_value,date"""
    df = pd.read_csv(csv_path)
    for _, row in df.iterrows():
        tracker.update_result(
            date=row['date'],
            player=row['player'],
            stat=row['stat'],
            result=row['result'],
            actual_value=row['actual_value']
        )
```

**Option B: Telegram Feedback (React with ✅/❌)**
```python
def process_telegram_reactions():
    """Poll Telegram channel for reaction counts on pick posts"""
    # Counts ✅ reactions = HIT
    # Counts ❌ reactions = MISS
    # Updates results_tracker accordingly
```

**Option C: ESPN API Auto-Grading (Phase 3)**
```python
def auto_grade_picks_from_espn():
    """Fetch final stats from ESPN, compare to lines, auto-grade"""
    # Requires espn_service.py with live stats fetching
    # Deferred to mid-January after stability check
```

### **Phase 2: Monitoring (2 Weeks)**
- Collect daily results for Dec 31, Jan 1-14
- Monitor hit rates by tier (SLAM should be 70%+, STRONG 60%+)
- Verify ROI calculations
- Check correlation accuracy

### **Phase 3: Auto-Grading (Mid-January)**
- Implement ESPN live stats fetching
- Auto-update results when games complete
- Eliminate manual reconciliation
- Archive historical performance by date

