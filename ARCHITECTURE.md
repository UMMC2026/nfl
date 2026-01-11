# ✅ THREE-LAYER BETTING ANALYSIS SYSTEM
## SOP v2.1 GOVERNANCE-SAFE ARCHITECTURE

---

## 🎯 FINAL DECISION: **OPTION C (GOVERNANCE-SAFE MODE)**

✅ **Ollama is a read-only interpretation layer ONLY**
✅ **Monte Carlo is the immutable truth layer**
✅ **Cheatsheet Pro is the executable summary**

---

## 📐 ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: MONTE CARLO (TRUTH ENGINE)                            │
├─────────────────────────────────────────────────────────────────┤
│ File: run_all_games_monte_carlo.py                              │
│ Input: Game data, player props, correlations                    │
│ Output 1: MC_ALL_GAMES_YYYY-MM-DD.txt (readable report)         │
│ Output 2: MC_LOCK_YYYY-MM-DD.json (locked, immutable)           │
│                                                                  │
│ Properties:                                                      │
│ - Deterministic algorithm (Bernoulli trials, 10k each game)     │
│ - No opinion, no language, pure math                            │
│ - Reproducible (same input → same output always)                │
│ - Auditable (every number traceable to simulation)              │
│ - Locked: Cannot be modified by downstream layers               │
└─────────────────────────────────────────────────────────────────┘
              ⬇️ (LOCKED JSON PASSED DOWN)
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2: OLLAMA COMMENTARY (INTERPRETATION ENGINE)              │
├─────────────────────────────────────────────────────────────────┤
│ File: ollama_slate_commentary_final.py                          │
│ Input: MC_LOCK_YYYY-MM-DD.json (READ-ONLY)                      │
│ Output: OLLAMA_SLATE_COMMENTARY_YYYY-MM-DD.md                   │
│                                                                  │
│ Properties:                                                      │
│ - Reads locked MC data (never modifies)                         │
│ - Generates narrative explanation of data                       │
│ - Conditional language only ("data suggests", "may indicate")   │
│ - NO imperatives, NO new recommendations                        │
│ - Editable (narrative, not executable)                          │
│ - Disagreement rule: MC wins automatically                      │
└─────────────────────────────────────────────────────────────────┘
              ⬇️ (COMMENTARY INTEGRATED)
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 3: CHEAT SHEET PRO (FINAL PRESENTATION)                   │
├─────────────────────────────────────────────────────────────────┤
│ File: cheatsheet_pro_generator.py                               │
│ Input 1: MC_LOCK_YYYY-MM-DD.json (decisions)                    │
│ Input 2: OLLAMA_SLATE_COMMENTARY_YYYY-MM-DD.md (context)        │
│ Output: CHEAT_SHEET_PRO_YYYY-MM-DD.md (ready-to-bet summary)    │
│                                                                  │
│ Properties:                                                      │
│ - Combines MC tier assignments with Ollama context              │
│ - Professional presentation (SLAM / STRONG / LEAN tiers)        │
│ - Exposure management rules auto-calculated                     │
│ - Risk warnings included                                         │
│ - Regulatory-defensible format                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔒 GOVERNANCE CONSTRAINTS (INVIOLABLE)

### Rule 1: MC Data is Immutable
```
✅ ALLOWED: Read MC_LOCK_YYYY-MM-DD.json
❌ FORBIDDEN: Modify any MC numbers
❌ FORBIDDEN: Adjust probabilities downstream
❌ FORBIDDEN: Change tier assignments based on opinion
```

### Rule 2: Ollama Never Touches Decisions
```
✅ ALLOWED: Explain variance, concentration, fragility
✅ ALLOWED: Compare risk profiles, highlight safest bets
❌ FORBIDDEN: Recommend exposure sizes
❌ FORBIDDEN: Change any MC output
❌ FORBIDDEN: Invent new correlations or assumptions
```

### Rule 3: Disagreement Resolution
```
IF Ollama interpretation ≠ MC data:
  → Log as comment
  → MC data stands (MC wins automatically)
  → Ollama narrative adjusted to align
  → Never override MC for LLM opinion
```

### Rule 4: Language Standards
```
✅ ALLOWED LANGUAGE:
  - "The data suggests..."
  - "MC indicates..."
  - "Variance analysis shows..."
  - "Primary candidate if exposure allows..."

❌ FORBIDDEN LANGUAGE:
  - "LOCK IN", "PLACE NOW", "BET THIS"
  - "You must", "You should"
  - Any imperatives or commands
```

---

## 📊 EXECUTION SEQUENCE

### Step 1: Run Monte Carlo Suite
```bash
python run_all_games_monte_carlo.py
```
**Outputs:**
- `MC_ALL_GAMES_2026-01-03_TIMESTAMP.txt` — Readable report
- `MC_LOCK_2026-01-03.json` — Locked data for downstream

**Validation:**
- Check exit code = 0
- Verify lock file exists
- Confirm all 9 games in JSON

---

### Step 2: Generate Ollama Commentary (Optional)
```bash
python ollama_slate_commentary_final.py
```
**Outputs:**
- `OLLAMA_SLATE_COMMENTARY_2026-01-03.md` — Narrative interpretation

**Validation:**
- Check exit code = 0
- Verify no MC numbers were changed
- Confirm conditional language throughout

**Note:** This script uses fallback mode if Ollama unavailable

---

### Step 3: Generate Cheatsheet Pro (Final)
```bash
python cheatsheet_pro_generator.py
```
**Outputs:**
- `CHEAT_SHEET_PRO_2026-01-03.md` — Ready-to-bet summary

**Validation:**
- Check exit code = 0
- Verify tier assignments match MC confidence
- Confirm exposure percentages auto-calculated

---

## 📁 FILE ORGANIZATION

```
outputs/
├── MC_ALL_GAMES_2026-01-03_TIMESTAMP.txt
│   └─ Human-readable MC report with all 9 games
│
├── MC_LOCK_2026-01-03.json
│   └─ Locked JSON (immutable, passed to Ollama/Cheatsheet)
│
├── OLLAMA_SLATE_COMMENTARY_2026-01-03.md
│   └─ Narrative interpretation layer (read-only to MC)
│
└── CHEAT_SHEET_PRO_2026-01-03.md
    └─ Final betting summary with tiers and exposure rules
```

**Golden Rule:** Only MC_LOCK file is allowed to change tier assignments.

---

## 🛡️ WHY THIS ARCHITECTURE IS SOP v2.1 COMPLIANT

### Separation of Concerns
- **MC:** Math only (reproducible, auditable, locked)
- **Ollama:** Narrative only (interpretive, non-binding, read-only)
- **Cheatsheet:** Presentation (combines both, governance-safe)

### Non-Contamination
- Ollama CANNOT modify MC probabilities
- MC CANNOT influence Ollama narrative (one-way flow)
- Cheatsheet uses MC tier assignments, not Ollama opinions

### Auditability
- Every number traces to locked MC JSON
- Every explanation in Ollama is linked to underlying data
- Disagreements logged (never executed)

### Regulatory Defensibility
- "We ran 10,000 MC trials per game" (verifiable)
- "LLM provided commentary only" (not decision-making)
- "Final tiers from MC data, not LLM opinion" (traceable)

---

## 🔄 MULTI-SPORT EXPANSION (READY)

This architecture supports adding more sports:

```python
# Current: NFL, NBA, CFB, CBB, Tennis, Boxing, Soccer
# Just add game data to GAMES_SLATE and re-run

GAMES_SLATE = {
    "NFL": [...],      # Already 5 games
    "NBA": [...],      # Already 4 games
    "CFB": [...],      # Ready (just add data)
    "CBB": [...],      # Ready (just add data)
    "Tennis": [...],   # Ready (just add data)
    "Boxing": [...],   # Ready (just add data)
    "Soccer": [...],   # Ready (just add data)
}
```

Ollama commentary and Cheatsheet Pro will automatically scale.

---

## ⚠️ CRITICAL REMINDERS

1. **DO NOT edit MC_LOCK_YYYY-MM-DD.json manually**
   - Auto-generated by MC suite
   - Locked = immutable
   - If changes needed, re-run MC suite

2. **DO NOT call Ollama directly from MC script**
   - Risk of contamination
   - Unpredictable behavior
   - SOP violation

3. **DO NOT skip Ollama commentary**
   - Even with fallback, narrative matters
   - Helps identify edge cases
   - Improves exposure management

4. **DO NOT modify exposure percentages in Cheatsheet**
   - Auto-calculated from concentration detection
   - Based on number of same-direction bets
   - Override only with documented reason

---

## ✅ SUCCESS CRITERIA (PHASE COMPLETE)

- ✅ MC suite runs end-to-end (Exit code 0)
- ✅ Lock file generated (immutable JSON)
- ✅ Ollama commentary optional (fallback works)
- ✅ Cheatsheet Pro tiers match MC confidence (within 0.1%)
- ✅ All three files complement each other
- ✅ No cross-layer contamination
- ✅ Governance rules enforced

---

## 📋 NEXT STEPS

### Option 1: Deploy Now
- Use three-layer system as-is
- Cheatsheet Pro is ready for betting
- Ollama commentary provides context

### Option 2: Connect to Ollama Service
- If Ollama becomes unreliable, use fallback template
- Consider running Ollama as separate service
- Add retry logic for subprocess calls

### Option 3: Multi-Sport Scale
- Add more sports to GAMES_SLATE
- Re-run all three scripts
- Same architecture, just more data

---

## 🔐 SOP v2.1 SIGN-OFF

**This system is governance-safe, auditable, and regulatory-defensible.**

All three layers work together without contamination:
- **MC:** Truth (locked)
- **Ollama:** Interpretation (read-only)
- **Cheatsheet:** Execution (auto-calculated)

**Ready for institution-grade betting operations.**
