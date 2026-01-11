# SYSTEM ARCHITECTURE — GROUND TRUTH ENFORCEMENT

**Date:** 2026-01-03  
**Overview:** How SOP v2.1, validate_output.py, daily cheatsheets, and the resolved ledger work together

---

## The Truth Stack (Bottom to Top)

### Layer 1: GROUND TRUTH DATA
```
nba_api (official Last10 stats)
    ↓
ground_truth_data_loader.py
    ↓
outputs/ground_truth_official.json
    │
    └→ [OFFICIAL NBA STATS — IMMUTABLE]
       (e.g., "OG Anunoby: avg 14.5 PRA over last 10")
```

**Purpose:** Official stats are the anchor. All confidence calculations start here.

---

### Layer 2: SOP v2.1 CONSTRAINTS
```
ops/sop_v2.1_truth_enforced.md

Key Rules:
  ✓ Rule A2: No duplicate EDGES (same player, stat, direction)
  ✓ Rule A3: No outlier lines (line > official_avg × 2.5)
  ✓ Rule B1: One PRIMARY per (player, game_id)
  ✓ Rule B2: CORRELATED excluded from SLAM/STRONG tiers
  ✓ Rule C2: Tier ↔ confidence alignment (75%+, 65-74%, 55-64%, <55%)
```

**Purpose:** Hard gates that cannot be violated.

---

### Layer 3: INPUT VALIDATION
```
validate_output.py

Enforces all 5 SOP v2.1 rules BEFORE rendering:
  • detect_duplicate_edges() [Rule A2]
  • detect_outlier_lines() [Rule A3]
  • detect_duplicate_players_as_primary() [Rule B1]
  • detect_correlated_in_tiers() [Rule B2]
  • check_tier_confidence_alignment() [Rule C2]

Exit: 0 (pass) or 1 (fail)
```

**Purpose:** Gate keeper—nothing renders unless ALL checks pass.

---

### Layer 4: DAILY CHEATSHEET
```
generate_cheatsheet.py

Inputs:
  • picks.json (manually entered lines)
  • ground_truth_official.json (official stats)
  • SOP v2.1 constraints (hard gates)

Process:
  1. Calculate probability hit (Normal CDF vs official mean)
  2. Apply hard UNDER gate (reject if avg < line)
  3. Assign tier + confidence
  4. Call validate_output.py (must pass)

Output:
  outputs/CHEATSHEET_*.txt
    - SLAM (68-75% confidence)
    - STRONG (60-67% confidence)
    - LEAN (52-59% confidence)
```

**Purpose:** Daily signal publication. Confidence is prospective (what we think will happen).

---

### Layer 5: GAME RESOLUTION
```
load_game_results.py → outputs/game_results.json
    ↓
Final stats for all completed games
    │
    └→ [ACTUAL OUTCOMES]
       (e.g., "OG Anunoby scored 18 points in CLE vs NYK on 2026-01-02")
```

**Purpose:** Reality. Once games finalize, this is immutable.

---

### Layer 6: LEDGER GRADING (🎯 THE NEW TRUTH LAYER)
```
generate_resolved_ledger.py

Inputs:
  • picks.json (picks with confidence)
  • game_results.json (actual outcomes)
  • ground_truth_official.json (context)

Process:
  1. For each PRIMARY pick: Grade HIT/MISS/PUSH
  2. For each CORRELATED pick: Grade but DON'T score units
  3. Compute win rate by tier
  4. Calibration: Compare confidence vs actual win %
  5. Rolling windows: 7/14/30-day aggregates
  6. System health: Validate SOP v2.1 on resolved picks

Output:
  reports/resolved_ledger.csv (machine truth, append-only)
  reports/RESOLVED_PERFORMANCE_LEDGER.md (human report)
  reports/resolved_2026-01-03.json (daily JSON snapshot)
```

**Purpose:** Accountability. Answer: "Did our confidence match reality?"

---

## Data Flow (Complete)

```
📋 picks.json (user input: lines, dates)
    ↓
⚙️  ground_truth_official.json (official NBA stats)
    ↓
🎯 generate_cheatsheet.py
    • Calc P(hit) = Normal CDF
    • Apply hard gates (outliers, duplicates)
    • Assign tier + confidence
    ↓
✅ validate_output.py
    • Rule A2: no duplicate edges
    • Rule A3: no outlier lines
    • Rule B1: one primary per player per game
    • Rule B2: no correlated in SLAM/STRONG
    • Rule C2: tier ↔ confidence alignment
    ↓
📊 outputs/CHEATSHEET_*.txt (daily picks with tiers)
    ↓
⏳ [Games finalize over next 24-48 hours]
    ↓
🎮 load_game_results.py
    • Fetch final stats from ESPN
    ↓
📈 outputs/game_results.json (actual outcomes)
    ↓
🎯 generate_resolved_ledger.py
    • Grade PRIMARY edges: HIT/MISS/PUSH
    • Track CORRELATED edges (no units)
    • Compute win % by tier
    • Calibration check (confidence vs reality)
    • Rolling windows (7/14/30 days)
    • Health check (SOP v2.1 rules)
    ↓
📝 reports/resolved_ledger.csv (machine truth)
📝 reports/RESOLVED_PERFORMANCE_LEDGER.md (human truth)
📝 reports/resolved_2026-01-03.json (archive)
    ↓
🔍 [Operator reviews calibration + health checks]
    ↓
✅ OR ❌ Approve/reject next day's cheatsheet
```

---

## Truth Enforcement Checkpoints

### Before Publishing Daily Cheatsheet
```
validate_output.py (enforces SOP v2.1)
    └→ MUST pass all 5 checks
    └→ Exit code: 0 (proceed) or 1 (block)
```

### After Games Finalize
```
generate_resolved_ledger.py (enforces SOP v2.1 on resolved picks)
    ├→ Grading logic (HIT/MISS/PUSH)
    ├→ System health checks (edge collapse, duplicate players, etc.)
    ├→ Calibration check (confidence vs actual win %)
    └→ If ANY fail → Report shows [FAIL] and operator reviews
```

---

## Key Invariants (Non-Negotiable)

1. **Official stats are immutable**
   - Once ground_truth_official.json is generated, don't change it
   - It's the anchor for all confidence calculations

2. **Cheatsheet lines are immutable**
   - Once published, picks.json doesn't change for that day
   - Resolution grading is based on published confidence, not retroactive adjustments

3. **Ledger is append-only**
   - resolved_ledger.csv NEVER rewrites old rows
   - Each game date appears once per run
   - Historical performance is preserved forever

4. **SOP v2.1 rules are always enforced**
   - No exceptions for "just this one edge"
   - If validate_output.py fails, cheatsheet is blocked

5. **Confidence is prospective, grading is retrospective**
   - Confidence = our pre-game estimate (70%)
   - Grading = actual outcome (HIT or MISS)
   - Calibration = comparison (did 70% picks actually hit ~70%?)

---

## Troubleshooting: When Truth Breaks

### Symptom: Cheatsheet blocked by validate_output.py
```
Check: Did I accidentally enter duplicate edges?
  e.g., OG Anunoby OVER 16.5 pts twice?

Fix:
  1. .venv\Scripts\python.exe validate_output.py
  2. Read error message (which rule failed)
  3. Edit picks.json to remove violation
  4. Re-run validate_output.py
  5. Rerun generate_cheatsheet.py
```

### Symptom: Ledger calibration warning (actual win % vs expected deviates >10%)
```
Check: Are my confidence estimates off?
  e.g., "SLAM tier hit only 50% instead of expected 75%"

Root causes:
  • Overconfident (lines are harder to hit than modeled)
  • Underconfident (lines are easier to hit than modeled)
  • Correlation errors (stacked correlated bets together)

Fix:
  1. Review ground_truth_official.json (are official stats correct?)
  2. Review picks.json lines (are they stale/inaccurate?)
  3. Review picks.json correlation flags (are they correct?)
  4. Recalibrate confidence for next day
```

### Symptom: Health check fails on resolved ledger [FAIL]
```
Check: Did SOP v2.1 rules get violated on resolved picks?

Examples:
  • EDGE_COLLAPSE: Same (player, stat, direction) appears 2+ times as PRIMARY
  • DUPLICATE_PLAYERS: Same player has 2+ PRIMARY bets in same game
  • CONFIDENCE_CAPS: SLAM pick has <68% confidence

Fix:
  1. .venv\Scripts\python.exe generate_resolved_ledger.py
  2. Read which check failed
  3. Review picks.json for the violation
  4. Fix and rerun
  5. Document the issue (shouldn't happen if validate_output.py passed)
```

---

## Decision Tree: Should I Publish This Cheatsheet?

```
┌─ Run: .venv\Scripts\python.exe validate_output.py
│
├─ Exit 0 (PASS)
│  └→ ✅ YES, publish cheatsheet
│     All SOP v2.1 rules enforced
│
└─ Exit 1 (FAIL)
   └→ ❌ NO, do NOT publish
      Review error message
      Fix picks.json
      Re-run validate_output.py
      Once PASS, then publish
```

---

## Decision Tree: Reviewing Resolved Ledger

```
┌─ Run: .venv\Scripts\python.exe ledger_pipeline.py
│
├─ System Health: All [PASS]
│  ├─ Calibration: <10% deviation → ✅ Confidence is well-calibrated
│  ├─ Calibration: >10% deviation → ⚠️  Recalibrate for next day
│  └─ Rolling 7-day: Win % on track → ✅ Approach looks solid
│
├─ System Health: Any [FAIL]
│  └→ ❌ Critical issue (shouldn't happen if validate_output.py passed)
│     Review error message
│     Investigate picks.json for SOP violation
│     Document the incident
│
└─ End result: Are we improving?
   Compare against previous weeks/months
   Adjust approach if win % drifts
```

---

## Files by Purpose

| File | Purpose | When Created | When Updated |
|------|---------|--------------|--------------|
| `ops/sop_v2.1_truth_enforced.md` | Constraints | Once | Never (frozen) |
| `validate_output.py` | Input gate | Once | Only bug fixes |
| `generate_cheatsheet.py` | Daily picker | Once | Only bug fixes |
| `picks.json` | Input lines | Daily | Daily (new games) |
| `ground_truth_official.json` | Official stats | Daily | Daily (new stats) |
| `outputs/CHEATSHEET_*.txt` | Daily report | Daily | N/A (immutable) |
| `load_game_results.py` | Result fetcher | Once | Only ESPN changes |
| `outputs/game_results.json` | Final stats | When games done | When games done |
| `generate_resolved_ledger.py` | Grader | Once | Only bug fixes |
| `reports/resolved_ledger.csv` | Machine truth | First run, then append | Append-only |
| `reports/RESOLVED_PERFORMANCE_LEDGER.md` | Human report | Daily | Daily (new rows) |

---

**System Status:** ✅ PRODUCTION READY  
**Last Tested:** 2026-01-03 (mock data)  
**Next Step:** Connect load_game_results.py to live ESPN API
