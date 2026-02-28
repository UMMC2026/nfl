# 🛡️ FUOOM Protection Demo — CBB Slate 2026-02-15

**Scenario**: Real CBB slate with 85% UNDER bias  
**Current Behavior**: Pipeline generates 40 picks, Monte Carlo suggests 4-leg parlays  
**Expected Behavior**: Direction gate ABORTS at step [3/5]  

---

## 📊 Actual Pipeline Output (BROKEN)

### What Happened
```
[2/5] GENERATE EDGES
  Generated 116 edges (from 207 raw, deduplicated)

[3/5] APPLY GATES
  [ESPN] Loaded 1 games for spread lookup
  Passed: 116, Failed: 0

[4/5] SCORE EDGES
  [SDG v2.1] Applying Stat Deviation Gate...
  [CALIBRATION] Capped 8 STRONG → LEAN (13d remaining)

[5/5] VALIDATE — HARD GATE
  [OK] All checks passed  ✅ (FALSE POSITIVE)

[6/5] RENDER REPORT
  Saved to: cbb_report_20260215_160244.txt
```

### Directional Analysis
| Direction | Count | Percentage |
|-----------|-------|------------|
| **UNDER (lower)** | **34 picks** | **85.0%** |
| OVER (higher) | 6 picks | 15.0% |
| **Total actionable** | **40 picks** | **100%** |

**Threshold**: 65% maximum allowed  
**Violation**: +20 percentage points over limit  
**Status**: ⛔ **SHOULD HAVE ABORTED**

---

## 🚨 What SHOULD Have Happened (FUOOM)

### Step [3/5] — Direction Gate Triggers

```
[3/5] APPLY GATES
----------------------------------------
  [DEBUG] Edges before direction gate: 116
  [DEBUG] Sample edge keys: ['player', 'stat', 'direction', 'probability', 'tier']
  [DEBUG] Sample direction: lower
  [DEBUG] Calling apply_direction_gate()...

============================================================
  ⛔ DIRECTION GATE — PIPELINE ABORTED
============================================================
  Bias: 85.0% UNDER (34 of 40 actionable picks)
  Threshold: 65% (FUOOM SOP v2.1)
  Direction counts: {'UNDER': 34, 'OVER': 6}

  This indicates STRUCTURAL MODEL BIAS, not a real edge.
  
  Possible causes:
    - Lines are NOT systematically mispriced 40 times
    - Model projections are systematically too low
    - Game script / context layer missing
    - Opponent data incomplete (all showing "UNK")
  
  Action required:
    1. Check model calibration against historical outcomes
    2. Add game script context (win probability → minutes)
    3. Verify line sources are current
    4. Fix opponent lookup (KenPom API broken)
    5. Fix spread lookup (only 1 game found)
    6. Fix recent averages (all showing 0.0)
============================================================

  [DEBUG] Gate returned 0 edges
  ⛔ Pipeline ABORTED by direction gate
  See above for diagnostic information

PIPELINE STOPPED — NO REPORT GENERATED
```

**Result**: User sees diagnostic message, NO picks generated, NO Monte Carlo parlays suggested.

---

## 🔍 Root Cause Analysis

### Issue #1: Direction Gate Not Executing

**Evidence**:
- ✅ Gate code exists and works (manual test confirmed)
- ✅ Gate is wired at line 1684 of cbb_main.py
- ❌ Gate never runs during pipeline execution
- ❌ No console output: no "[DEBUG]" lines, no "Direction Gate PASSED/ABORTED"

**Hypothesis**: One of three possibilities:

1. **Import is failing silently** — Exception being caught upstream
   ```python
   try:
       from sports.cbb.direction_gate import apply_direction_gate
   except ImportError:
       pass  # Silent failure
   ```

2. **Function is called but doesn't reach print statements** — Logic error between lines 1684-1700

3. **Different code path being executed** — Pipeline has alternate route that bypasses apply_cbb_gates()

**Next Diagnostic**:
- Add `print("CHECKPOINT 1: Before import")` at line 1683
- Add `print("CHECKPOINT 2: After import")` at line 1685  
- Add `print("CHECKPOINT 3: Before call")` at line 1690
- Add `print("CHECKPOINT 4: After call")` at line 1693

If we see CHECKPOINT 1 but not 2 → import failing  
If we see CHECKPOINT 2 but not 3 → conditional logic preventing call  
If we see CHECKPOINT 3 but not 4 → function hanging or exception inside  

---

### Issue #2: Calibration Cap Force-Demotion

**Evidence**:
```
[CALIBRATION] Capped 8 STRONG → LEAN (13d remaining)
```

**What This Means**:
- System has ZERO CBB historical picks in calibration database
- Blanket hold applied: ALL STRONG picks demoted to LEAN for 13 more days
- This is a safety mechanism, but it's masking the real problem

**Example**:
```
Keaton Wagler PTS UNDER 20.5
  Probability: 75.0%
  Tier: [STRONG] | Engine decision: [STRONG]
  
  But rendered as: [LEAN] due to calibration hold
```

**The Problem**: This is correct IF you have no CBB data. But it's also hiding the 85% UNDER bias. If direction gate aborted, you'd never see these picks. Since gate didn't run, the calibration cap is the ONLY protection active.

**Recommended Fix**:
- Keep calibration hold for tier display (correct behavior)
- BUT: Direction gate should run BEFORE tier assignment
- Sequence should be: Raw probability → Check direction bias → Assign tier → Apply calibration cap

---

### Issue #3: Missing Opponent Data ("UNK")

**Evidence**:
```
Team: CIN vs UNKNOWN OPPONENT (NO_KENPOM_OPP)
Team: ILL vs UNKNOWN OPPONENT (NO_KENPOM_OPP)
```

**DeepSeek AI repeated warnings**:
> "Without matchup context or stability metrics, there's no clear edge—this is essentially a coin flip despite the high probability projection."

**Why This Causes UNDER Bias**:

1. **No defensive adjustments** — Can't adjust projections based on opponent defense
2. **No pace adjustments** — Can't factor game speed (fast = more possessions = higher totals)
3. **No game script modeling** — Can't predict blowout → bench players get extra minutes
4. **No situational context** — Can't identify revenge games, rivalry games, tournament pressure

**Result**: Model defaults to season averages, which systematically underestimate players in favorable matchups and overestimate players in tough matchups. If this slate happens to be full of tough matchups → systematic UNDER bias.

**Fix Required**:
- Debug KenPom API calls in `cbb_data_provider.py`
- Check if API key is valid/active
- Add fallback: ESPN defensive ratings if KenPom unavailable
- Add logging: "KenPom lookup failed for CIN vs [opponent]"

---

### Issue #4: Missing Spread Data

**Evidence**:
```
[ESPN] Loaded 1 games for spread lookup
```

**Every edge shows**: `spread=MISSING`

**Why This Matters**:

Spreads are the MOST IMPORTANT context for CBB prop betting:
- **Blowouts** → Starters sit early → UNDERS hit
- **Close games** → Starters play full minutes → Projections accurate
- **Heavy favorites** → Garbage time → Bench players get usage → Model confused

**Example from this slate**:
- Illinois (ranked #8) vs IU (unranked) — Likely 15+ point spread  
- If Illinois is heavy favorite → Jake Davis (bench player) might see garbage time  
- His projection: 5.9 pts, Line: 8.5 → Model says 74% UNDER  
- BUT if Illinois blows out IU → Davis gets 10+ minutes in garbage time → OVER more likely

**Without spreads**: Can't run blowout gate, can't adjust projections, can't validate directional thesis.

**Fix Required**:
- Check ESPN API response structure in logs
- Verify game IDs match between props and spread lookup
- Add fallback: Use team rankings as proxy (ranked team vs unranked = estimated -12 spread)

---

### Issue #5: Recent Averages All Zero

**Evidence**:
```
[Quick Analysis] Recent avg (0.0) well below line.
```

Appears on EVERY edge in the report.

**What This Field Should Show**:
- L5 or L10 average for that player in that stat category
- Used to detect hot/cold streaks, injury recovery, role changes

**Why All Zeros**:
- Field exists but isn't populated (query returning NULL)
- Variable named wrong (`recent_avg` vs `recent_average`)
- ESPN API format changed

**Impact on UNDER Bias**:
- If recent averages were populated, AI commentary could say:  
  "Wagler averaging 24.5 pts over L5, line 20.5 is LOW → OVER value"
- Instead AI sees 0.0 and says:  
  "Recent avg well below line" (incorrect analysis)

**Fix Required**:
- Debug `recent_avg` calculation in `generate_edges()`
- Check if L10 cache is empty for CBB (might only have NBA data)
- Add logging: "Recent avg for Wagler: SQL returned [value]"

---

## 🎰 Monte Carlo Risk Analysis

### Your Suggested Entry #1
```
4-leg parlay — Joint Probability: 28.0%
  • Keaton Wagler    PTS      UNDER 20.5 (75%)
  • Jake Davis       PTS      UNDER 8.5  (74%)
  • Jizzle James     PTS      UNDER 14.5 (72%)
  • Tomislav Ivisic  REB+AST  UNDER 9.5  (70%)
```

### Risk Assessment (FUOOM Perspective)

#### ⛔ **Correlation Risk (CRITICAL)**

**All 4 legs are UNDER** = 100% directionally correlated

**SOP v2.1 Rule B2**: Correlated picks multiply risk, not probability.

If UNDER bias is structural error (not real edge), all 4 legs fail together:
- Model systematically over-projects → All 4 lines too high → All 4 UNDERS look good
- OR: Model missing game script → All 4 players affected same way → All fail together

**True probability ≠ 28.0%** if correlation is structural:
- Independent assumption: 0.75 × 0.74 × 0.72 × 0.70 = 28.0%
- Correlated scenario: If model is wrong, correlation = 0.9 → effective prob ~15%

#### ⛔ **Data Quality Risk (CRITICAL)**

All 4 legs suffer from same data gaps:
- **Keaton Wagler**: Opponent UNK, spread MISSING, recent avg 0.0
- **Jake Davis**: Opponent UNK, spread MISSING, recent avg 0.0
- **Jizzle James**: Opponent UNK, spread MISSING, recent avg 0.0
- **Tomislav Ivisic**: Opponent UNK, spread MISSING, recent avg 0.0

If opponent data suddenly populates (e.g., KenPom API comes back online), all 4 probabilities could shift downward simultaneously.

#### ⛔ **Calibration Risk (HIGH)**

**CBB has ZERO historical picks** — Can't validate if 75% probability actually hits 75% of the time.

For comparison:
- NBA: 619 picks tracked, Brier score calculated
- CBB: 0 picks tracked, Brier score UNKNOWN

You're betting on a model that's never been backtested on this sport.

#### ⚠️ **Tier Mislabeling Risk (MEDIUM)**

All 4 legs show `LEAN` but trace shows `STRONG`:
- Wagler: 75% → should be STRONG (≥75%) but displayed as LEAN
- Others: 70-74% → correctly LEAN

Calibration hold is forcing conservative tier display, but Monte Carlo is using the raw 75% probability. If you bet based on report tiers (LEAN = 0.5 units), but Monte Carlo calculates joint prob using engine tiers (STRONG = 1.0 units), there's a mismatch.

---

## ✅ What SHOULD Happen (Step-by-Step)

### Scenario 1: Direction Gate Active (PROPER DEFENSE)

```
User runs: menu.py → [B] CBB → [2] Analyze Slate

Pipeline executes:
  [1/5] Load slate: 229 props
  [2/5] Generate edges: 116 raw edges
  
  [3/5] Apply gates:
    → Direction gate checks: 34 UNDER, 6 OVER = 85%
    → Gate ABORTS: Returns []
    → Pipeline stops immediately
  
  [4/5] NOT REACHED
  [5/5] NOT REACHED
  [6/5] NOT REACHED

Output shown to user:
  ⛔ DIRECTION GATE — PIPELINE ABORTED
  No report generated
  No Monte Carlo suggestions
  
User action:
  → Investigate WHY 85% UNDER (check data quality, model calibration)
  → Fix root causes (opponent lookup, spread data, recent avgs)
  → Re-run pipeline with fixes
  → If still 85% UNDER → Model is fundamentally broken, don't bet
```

### Scenario 2: Data Fixed, Bias Remains (RED FLAG)

```
User fixes:
  - KenPom opponent lookup working
  - Spread data populating
  - Recent averages showing real values
  
Pipeline re-runs:
  [2/5] Generate edges: 116 raw edges (now with full context)
  [3/5] Direction gate: Still 80% UNDER
  
Gate ABORTS again.

Conclusion: The UNDER bias is REAL (not data error)

Possible explanations:
  1. Lines are systematically mispriced (unlikely for 40 props)
  2. Model has systematic bias (projections too low)
  3. Sample is cherry-picked (e.g., all low-usage players)
  
User action:
  → Audit model: Check calibration on historical data
  → If no historical data → Don't bet until you have 50+ resolved picks
  → If calibration shows <50% hit rate on UNDERS → Model is broken
```

### Scenario 3: Data Fixed, Bias Resolves (GREEN LIGHT)

```
User fixes same issues.

Pipeline re-runs:
  [2/5] Generate edges: 116 raw edges
  [3/5] Direction gate: 22 UNDER, 18 OVER = 55% UNDER
  
Gate PASSES (≤65% threshold)

Pipeline continues:
  [4/5] Score edges: SDG applies, calibration hold applies
  [5/5] Validate: Checks pass
  [6/5] Render: Report generated with 40 LEAN picks
  
Monte Carlo:
  → Suggests 4-leg parlays
  → Now includes mix of UNDER and OVER legs
  → Correlation risk reduced
  
User action:
  → Safe to bet (with CBB experimental caps)
  → Track outcomes for calibration
  → Exit experimental mode after 50+ picks if Brier < 0.20
```

---

## 🎓 Key Takeaways

### 1. **Direction Gate is MANDATORY, Not Optional**

The 85% UNDER bias proves the FUOOM audit was correct. Without the gate:
- Users see 40 "high-confidence" picks (70-75% probability)
- Users build 4-leg parlays at 28% joint probability
- Users lose bankroll on **structural model errors**, not bad luck

With the gate:
- Pipeline aborts immediately
- User is forced to investigate root causes
- No bets placed until data quality confirmed

### 2. **85% UNDER = False Edge, Not Market Inefficiency**

**It's statistically impossible** for 40 CBB props to be systematically mispriced in the same direction on the same day. If this were real edge:
- Sharp books would arbitrage instantly
- Lines would move within minutes
- You'd see 55-60% UNDER, never 85%

The fact that you're seeing 85% means:
- Your model has incomplete data (opponent = UNK, spread = MISSING)
- Your model has systematic bias (projects too low)
- Your model lacks context (game script, pace, defense)

### 3. **Correlated Parlays Multiply Risk, Not Probability**

Your #1 entry (all 4 UNDERS) assumes legs are independent:
```
P(all hit) = 0.75 × 0.74 × 0.72 × 0.70 = 28.0%
```

But if UNDER bias is structural:
```
P(all hit) = P(model is correct)^4
If model is 60% correct: 0.60^4 = 13% (not 28%)
```

**Proper Monte Carlo** should:
- Flag 100% directionally correlated parlays
- Adjust joint probability for correlation
- Prefer mixed-direction entries (2 UNDER + 2 OVER)

### 4. **Calibration Cap is Safety, Not Bug**

The `[CALIBRATION] Capped 8 STRONG → LEAN (13d remaining)` is CORRECT behavior:
- You have 0 CBB historical picks
- System refuses to output high-confidence bets on unproven model
- Forces 0.5 unit sizing until calibration proven

This is the ONLY protection currently active (since direction gate isn't running).

### 5. **Missing Data = Missing Edge**

Every edge in this report has:
- Opponent = UNK
- Spread = MISSING  
- Recent avg = 0.0
- Stability = UNKNOWN
- Tier = Overridden by calibration

**You can't have edge without context.** If you bet these picks:
- You're betting on season averages (not matchup-adjusted)
- You're ignoring blowout risk (no spread data)
- You're ignoring hot/cold streaks (no recent form)
- You're ignoring defensive matchups (no opponent rating)

---

## 🔧 Recommended Fixes (Priority Order)

### Priority 1: GET DIRECTION GATE RUNNING (CRITICAL)

**Status**: Code is correct, wiring is correct, but gate isn't executing.

**Next steps**:
1. Add checkpoint logging (CHECKPOINT 1-4 as described above)
2. Run CBB analysis
3. Post console output showing which checkpoints appear
4. Diagnose whether it's import failure, logic error, or alternate code path

**ETA**: 10 minutes once you run the debug version

---

### Priority 2: FIX OPPONENT LOOKUP (HIGH)

**Current**: All opponents show "UNK"  
**Impact**: No defensive adjustments, no pace adjustments, no game script

**Files to check**:
```
sports/cbb/ingest/cbb_data_provider.py
  → get_opponent_for_game()
  → kenpom_lookup()
```

**Diagnostic**:
```python
# Add logging before KenPom API call:
logger.debug(f"Looking up opponent for {team} in game {game_id}")
logger.debug(f"KenPom API key present: {bool(KENPOM_API_KEY)}")
result = kenpom_api.get_game(game_id)
logger.debug(f"KenPom returned: {result}")
```

---

### Priority 3: FIX SPREAD LOOKUP (HIGH)

**Current**: Only 1 game found for entire slate  
**Impact**: No blowout gate, no game script adjustments

**Files to check**:
```
sports/cbb/ingest/cbb_data_provider.py
  → get_todays_games()
  → ESPN spread scraper
```

**Diagnostic**:
```python
logger.debug(f"ESPN returned {len(games)} games")
for game in games:
    logger.debug(f"  {game['home']} vs {game['away']}, spread={game.get('spread', 'MISSING')}")
```

---

### Priority 4: FIX RECENT AVERAGES (MEDIUM)

**Current**: All showing 0.0  
**Impact**: AI commentary incorrect, can't detect streaks

**Files to check**:
```
sports/cbb/cbb_main.py
  → generate_edges()
  → recent_avg calculation
```

**Diagnostic**:
```python
recent_avg = get_recent_avg(player, stat, last_n=10)
logger.debug(f"{player} {stat} L10 avg: {recent_avg}")
```

---

### Priority 5: ADD CORRELATION DETECTION TO MONTE CARLO (MEDIUM)

**Current**: Suggests 100% UNDER parlays  
**Impact**: Multiplies correlation risk

**Enhancement**:
```python
def check_correlation(legs):
    directions = [leg['direction'] for leg in legs]
    under_pct = directions.count('lower') / len(directions)
    
    if under_pct >= 0.75:  # 3+ of 4 legs same direction
        return {
            'correlation_warning': True,
            'correlation_pct': under_pct,
            'adjusted_prob': calculate_correlated_prob(legs),
            'recommendation': 'Consider mixed-direction entry for risk reduction'
        }
```

---

## 📞 Next Action

**Please run CBB analysis ONE MORE TIME with debug logging active:**

```bash
.venv\Scripts\python.exe menu.py → [B] CBB → [2] Analyze Slate
```

**Copy/paste the console output** — specifically looking for:
- `[DEBUG] Edges before direction gate: <number>`
- `[DEBUG] Sample edge keys: [...]`
- `[DEBUG] Sample direction: lower/higher`
- `[DEBUG] Calling apply_direction_gate()...`
- `[DEBUG] Gate returned <number> edges`

If you see NONE of these lines → Import is failing or function isn't being called.  
If you see ALL of these lines → Gate is executing but not aborting (threshold bug).  
If you see SOME of these lines → Exception occurring mid-function.

---

**Bottom Line**: This 85% UNDER slate is the PERFECT test case for FUOOM protection. Once direction gate is running, it will save you from betting on systematically bad data. Until then, **DO NOT BET THIS SLATE** — it's full of data quality issues and model bias.

