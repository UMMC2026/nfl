# 🚀 QUICK START REFERENCE

## Three Commands to Run (In Order):

```bash
# 1. Generate MC lock file
python run_all_games_monte_carlo.py

# 2. Generate Ollama commentary
python ollama_slate_commentary_final.py

# 3. Generate final cheatsheet
python cheatsheet_pro_generator.py
```

**All exit codes should be 0**

---

## Three Output Files (In Order of Use):

### 1. MC_LOCK_2026-01-03.json
- **What:** Locked Monte Carlo data
- **Status:** IMMUTABLE (no modifications allowed)
- **Use:** Reference for accuracy verification

### 2. OLLAMA_SLATE_COMMENTARY_2026-01-03.md  
- **What:** Narrative interpretation of MC data
- **Status:** Context and explanation only
- **Use:** Understand the "why" behind the numbers

### 3. CHEAT_SHEET_PRO_2026-01-03.md
- **What:** Final betting summary with tiers
- **Status:** READY FOR BETTING
- **Use:** Make actual betting decisions

---

## Tier System (From MC Data):

| Tier | Range | Count | Use Case |
|------|-------|-------|----------|
| SLAM | 67%+ | 4 | Primary allocation |
| STRONG | 62-66% | 10 | Secondary allocation |
| LEAN | 55-61% | 13 | Hedging/diversification |

---

## Exposure Rules (Auto-Calculated):

| Configuration | Reduction | Games |
|---|---|---|
| 3/3 overs | -35% | 3 |
| 2/3 overs | -25% | 6 |

---

## Critical Rules (INVIOLABLE):

1. ❌ Do NOT edit MC_LOCK file manually
2. ❌ Do NOT call Ollama from within MC script
3. ✅ Do use CHEAT_SHEET_PRO for betting
4. ✅ Do use conditional language ("if exposure allows")
5. ✅ Do hedge concentration (1:1 ratio)

---

## Troubleshooting:

**Issue:** Unicode/emoji encoding errors
- **Fix:** Scripts auto-apply UTF-8 on startup

**Issue:** Ollama not found
- **Fix:** Falls back to template-based commentary automatically

**Issue:** MC_LOCK file doesn't exist
- **Fix:** Run `run_all_games_monte_carlo.py` first

---

## File Locations:

```
outputs/
├── MC_ALL_GAMES_2026-01-03_*.txt          ← Readable report
├── MC_LOCK_2026-01-03.json                ← Locked (immutable)
├── OLLAMA_SLATE_COMMENTARY_2026-01-03.md  ← Narrative
└── CHEAT_SHEET_PRO_2026-01-03.md          ← Ready-to-bet
```

---

## Success Indicators:

✅ All three scripts run (exit code 0)
✅ Lock file generated and immutable
✅ Ollama output shows "data suggests..." language
✅ Cheatsheet shows tier assignments
✅ Exposure percentages auto-calculated
✅ No errors or warnings in output

---

## Next Steps:

1. Run the pipeline (3 commands)
2. Verify all outputs generated
3. Review CHEAT_SHEET_PRO for tier assignments
4. Use tier system to size bets
5. Apply exposure reduction rules
6. Execute bets

---

**System Status: PRODUCTION READY ✅**

All governance constraints enforced.
All three layers operational.
Ready for institution-grade betting.
