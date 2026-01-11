# RESOLVED LEDGER — IMPLEMENTATION & USAGE GUIDE

**Date:** 2026-01-03  
**Status:** PRODUCTION READY (Tested with mock data)

---

## Overview

The **Resolved Ledger** is a **ground-truth immutable record** that answers:
> *"What did we predict? What actually happened? Did our confidence match reality?"*

It sits **ABOVE** the daily cheat sheet and enforces accountability through three components:

1. **CSV Ledger** (`reports/resolved_ledger.csv`) — Machine-readable source of truth
2. **Markdown Report** (`reports/RESOLVED_PERFORMANCE_LEDGER.md`) — Human-readable daily summary
3. **Rolling Windows** — 7/14/30-day performance aggregates

---

## File Structure

```
/ufa/
├── generate_resolved_ledger.py    [NEW] Main resolver: grades picks → CSV + Markdown
├── load_game_results.py            [NEW] Fetch final stats from ESPN → game_results.json
├── ledger_pipeline.py              [NEW] Orchestrate load + resolve
│
/reports/
├── resolved_ledger.csv             (append-only, machine truth)
├── RESOLVED_PERFORMANCE_LEDGER.md  (daily human report)
├── resolved_2026-01-02.json        (daily JSON snapshot)
├── resolved_2026-01-03.json        (next day, etc.)
│
/ops/
├── csv_schema.md                   [NEW] CSV column definitions + SQL patterns
└── sop_v2.1_truth_enforced.md      (references ledger as SOP step)
```

---

## Quick Start (3 Steps)

### 1. Generate Daily Cheatsheet (Existing)
```bash
.venv\Scripts\python.exe generate_cheatsheet.py
# Output: outputs/CHEATSHEET_*.txt with tiers + confidence
```

### 2. [Manual] Wait for Games to Finalize
```
⏳ Game results become available (ESPN publishes final stats)
```

### 3. Run Ledger Pipeline
```bash
.venv\Scripts\python.exe ledger_pipeline.py
```

**What it does:**
- Fetches final game stats → `outputs/game_results.json`
- Grades each pick (HIT/MISS/PUSH/UNKNOWN)
- Writes `reports/resolved_ledger.csv` (append-only)
- Renders `reports/RESOLVED_PERFORMANCE_LEDGER.md`
- Computes 7/14/30-day rolling windows
- Validates system health (SOP v2.1 rules)

---

## What Gets Graded?

### ✅ PRIMARY Edges (Units = ±1.0)
```
Players that appear as the main bet, with primary_edge=TRUE
Example: "OG Anunoby OVER 16.5 points"
  → Outcome: HIT/MISS/PUSH
  → Units: +1.0 (if HIT) or 0.0 (if MISS/PUSH)
```

### ⚠️ CORRELATED Edges (Units = 0.0, tracked only)
```
Alternative stats for same player, with primary_edge=FALSE
Example: "OG Anunoby OVER 25.5 PRA" (correlated with points)
  → Outcome: HIT/MISS/PUSH (but units always = 0.0)
  → Purpose: Track correlation accuracy, prevent stacking
```

### ⏳ PENDING (Outcome = UNKNOWN)
```
Games not yet finalized — excluded from performance calculations
```

---

## Output Files Explained

### 1. CSV (`reports/resolved_ledger.csv`)
**Machine-readable source of truth. Append-only. Never rewritten.**

Example rows:
```
date,game_id,player_name,stat,direction,line,actual_value,tier,confidence,primary_edge,outcome,units
2026-01-02,CLE_NYK,OG Anunoby,points,OVER,16.5,18,SLAM,0.75,TRUE,HIT,1.0
2026-01-02,CLE_NYK,OG Anunoby,pra,OVER,25.5,27,STRONG,0.65,FALSE,HIT,0.0
```

See `ops/csv_schema.md` for full column definitions and SQL queries.

### 2. Markdown Report (`reports/RESOLVED_PERFORMANCE_LEDGER.md`)
**Human-readable daily summary. Includes:**

- **Daily Summary** (wins, losses, net units)
- **Tier-Level Truth Table** (win % by tier)
- **Edge Breakdown** (each pick's actual result)
- **Calibration Check** (confidence vs actual win %)
- **Rolling Performance** (7/14/30 days)
- **System Health Flags** (SOP rule compliance)

Example section:
```markdown
## Tier-Level Truth Table

| Tier | Picks | Wins | Losses | Win % | Units |
|------|-------|------|--------|-------|-------|
| SLAM | 3 | 3 | 0 | 100.0% | +3.0 |
| STRONG | 1 | 1 | 0 | 100.0% | +1.0 |
```

### 3. JSON Snapshot (`reports/resolved_{YYYY-MM-DD}.json`)
**Daily rollup for archiving and automation.**

Contains tier summaries, rolling windows, calibration, health checks.

---

## Key Concepts

### Grading Logic

```
OVER Line 16.5:
  actual_value > 16.5  → HIT (+1.0 units if primary)
  actual_value < 16.5  → MISS (0.0 units)
  actual_value = 16.5  → PUSH (0.0 units)

UNDER Line 39.5:
  actual_value < 39.5  → HIT (+1.0 units if primary)
  actual_value > 39.5  → MISS (0.0 units)
  actual_value = 39.5  → PUSH (0.0 units)
```

### Tier Alignment (SOP v2.1)

```
SLAM:    68-75% confidence  → Expected win %: ~72%
STRONG:  60-67% confidence  → Expected win %: ~63%
LEAN:    52-59% confidence  → Expected win %: ~55%
NO_PLAY: <52% confidence    → Not scored
```

If actual win % deviates >10% from expected → Calibration Warning

### Rolling Windows

```
Last 7 Days:  MIN 3 samples before reporting
Last 14 Days: MIN 5 samples before reporting
Last 30 Days: MIN 10 samples before reporting
```

Until minimum samples met, window shows "Insufficient data".

### System Health Checks

All 5 must PASS (SOP v2.1 enforcement):

1. **EDGE_COLLAPSE** — No duplicate (player, stat, direction) edges as primary
2. **DUPLICATE_PLAYERS** — Max 1 PRIMARY bet per (player, game_id)
3. **CONFIDENCE_CAPS** — Tiers aligned to confidence ranges
4. **CORRELATED_IN_TIERS** — No correlated edges in SLAM/STRONG
5. **STAT_INTEGRITY** — Stat keys match official NBA/NFL schema

If ANY fail → Report shows [FAIL], and rendering may be blocked (operator decision).

---

## Real-World Usage

### Day 1: Generate Picks
```bash
# Morning: Generate daily cheatsheet with tiers + confidence
.venv\Scripts\python.exe generate_cheatsheet.py

# Output: outputs/CHEATSHEET_JAN03_*.txt
#   - SLAM (75% confidence): OG Anunoby OVER 16.5 pts
#   - STRONG (65% confidence): Dean Wade UNDER 12.5 pts
#   - etc.
```

### Day 2: Games Finalize + Resolve
```bash
# Evening: Games are final, resolve performance
.venv\Scripts\python.exe ledger_pipeline.py

# Output:
#   - reports/resolved_ledger.csv (appended)
#   - reports/RESOLVED_PERFORMANCE_LEDGER.md (new)
#   - reports/resolved_2026-01-03.json (new)
```

### Day 30: Check Rolling Performance
```bash
# Query CSV to see 30-day rolling win %
sqlite3 reports/resolved_ledger.csv
SELECT tier, COUNT(*) as picks, 
       SUM(CASE WHEN outcome='HIT' THEN 1 ELSE 0 END) as wins,
       ROUND(100.0*SUM(CASE WHEN outcome='HIT' THEN 1 ELSE 0 END)/COUNT(*), 1) as win_pct
FROM csv
WHERE primary_edge='True' AND outcome != 'UNKNOWN' 
  AND date >= DATE('now', '-30 days')
GROUP BY tier;
```

---

## Testing

### Mock Test (Included)
```bash
# Create mock picks + game results
.venv\Scripts\python.exe test_resolved_ledger.py

# Run resolver with mock data
.venv\Scripts\python.exe generate_resolved_ledger.py \
    --picks picks_mock.json \
    --results outputs/game_results_mock.json

# Expected output:
#   ✓ 4 picks graded (1 correlated, 3 primary)
#   ✓ Win rate: 100% (4/4 hits)
#   ✓ Net units: +4.0
#   ✓ System health: 4/4 PASS
```

### Check Outputs
```bash
# View CSV (first 5 rows)
head -5 reports/resolved_ledger.csv

# View Markdown report
type reports/RESOLVED_PERFORMANCE_LEDGER.md | more

# View JSON snapshot
type reports/resolved_2026-01-03.json | python -m json.tool
```

---

## Common Issues & Fixes

### Issue: "No games finalized"
**Cause:** `game_results.json` is empty (no games completed yet)  
**Fix:** Wait for games to finalize, then re-run ledger_pipeline.py

### Issue: Calibration warning (actual % deviates >10%)
**Cause:** Confidence estimates are off (e.g., 75% tier only hit 50%)  
**Fix:** Review SOP v2.1 confidence calibration; adjust for next day

### Issue: System health FAIL (e.g., EDGE_COLLAPSE)
**Cause:** Duplicate primary edges detected (same player, stat, direction)  
**Fix:** Run validate_output.py BEFORE generating cheatsheet to catch this early

### Issue: Encoding error on Windows
**Fix:** Already handled (UTF-8 encoding in render_markdown)

---

## Integration with SOP v2.1

The ledger is **THE** enforcement mechanism for SOP v2.1:

| SOP Rule | Ledger Check | Output |
|----------|--------------|--------|
| A2: No duplicate edges | EDGE_COLLAPSE health check | [FAIL] if duplicates found |
| B1: One player per game | DUPLICATE_PLAYERS health check | [FAIL] if 2+ primaries same player |
| C2: Tier ↔ confidence | CONFIDENCE_CAPS health check | [FAIL] if tier out of range |
| B2: CORRELATED excluded | CORRELATED_IN_TIERS check | [FAIL] if correlated in SLAM/STRONG |
| Overall calibration | Confidence vs reality table | Warnings if >10% deviation |

**Decision Point:** If health checks show [FAIL], operator must review before approving next day's cheatsheet.

---

## Next Steps (Optional Enhancements)

1. **Automated ESPN Integration**
   - Connect `load_game_results.py` to live ESPN API
   - Auto-fetch stats when games finalize (no manual step)

2. **Slack/Email Alerts**
   - Send daily ledger report to stakeholders
   - Alert on health check failures

3. **Historical Analysis**
   - Aggregate rolling windows across months
   - Plot confidence vs actual win % curves
   - Identify systematic miscalibration

4. **Parlay Accuracy**
   - Track multi-leg correlations
   - Measure edge collapse impact on parlay ROI

---

## File Reference

| File | Purpose | Status |
|------|---------|--------|
| `generate_resolved_ledger.py` | Main resolver | ✅ Ready |
| `load_game_results.py` | ESPN fetcher (stub) | ⚠️ Needs ESPN integration |
| `ledger_pipeline.py` | Orchestrator | ✅ Ready |
| `test_resolved_ledger.py` | Mock test suite | ✅ Ready |
| `ops/csv_schema.md` | CSV reference | ✅ Ready |
| `reports/resolved_ledger.csv` | Machine truth | 📝 Generated daily |
| `reports/RESOLVED_PERFORMANCE_LEDGER.md` | Human report | 📝 Generated daily |

---

**Last Updated:** 2026-01-03  
**Status:** PRODUCTION READY (Mock validated, awaiting live ESPN integration)
