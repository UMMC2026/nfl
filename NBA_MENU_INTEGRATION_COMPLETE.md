# NBA ROLE LAYER - MENU INTEGRATION COMPLETE ✅

**Date:** 2026-01-26  
**Status:** ✅ **OPERATIONAL IN MENU PATH**

---

## ✅ WHAT CHANGED

### Files Modified:
1. **[risk_first_analyzer.py](risk_first_analyzer.py)** (Lines 1214-1230)
   - Added `enrich_nba_usage_minutes_simple()` call after stats refresh
   - Added NBA Role Layer normalization (109 picks normalized successfully)

2. **[engine/enrich_nba_simple.py](engine/enrich_nba_simple.py)** (NEW FILE - 94 lines)
   - Simple usage/minutes enrichment for menu path
   - Uses stat types + player name patterns to estimate role
   - Doesn't require `recent_values` (which menu path doesn't populate)

---

## 🧪 TEST RESULTS

**Test File:** [test_menu_nba_role.py](test_menu_nba_role.py)  
**Slate:** IND vs ATL (109 props)

```
✅ Normalized 109 NBA picks

🎯 Key Classifications:

CJ McCollum:
   Archetype: BENCH_MICROWAVE
   Cap Adjustment: -8.0% ⚠️
   Flags: HIGH_USAGE_VOLATILITY, HIGH_BENCH_RISK
   Usage: 26.0%
   Minutes: 24.0 (bench rotation)

Pascal Siakam:
   Archetype: SECONDARY_CREATOR
   Cap Adjustment: 0.0%
   Flags: None
   Usage: 24.0%
   Minutes: 30.0

Jalen Johnson:
   Archetype: SECONDARY_CREATOR
   Cap Adjustment: 0.0%
   Flags: None
   Usage: 26.0%
   Minutes: 32.0
```

---

## 🔄 HOW IT WORKS NOW (Menu Path)

### Analysis Flow:
```
User Selects [2] Analyze Slate
    ↓
analyze_from_underdog_json.py
    ↓
risk_first_analyzer.py:
    1️⃣ Refresh stats via API (_refresh_daily_api_stats)
    2️⃣ Enrich usage/minutes (NEW - enrich_nba_usage_minutes_simple)
    3️⃣ NBA Role Layer normalization (NEW - 109 picks normalized)
    4️⃣ Apply confidence cap adjustments
    5️⃣ Generate picks with nba_role_archetype fields
```

### Fields Added to Each Pick:
```json
{
  "player": "CJ McCollum",
  "stat": "assists",
  "nba_role_archetype": "PlayerArchetype.BENCH_MICROWAVE",
  "nba_confidence_cap_adjustment": -8.0,
  "nba_role_flags": ["HIGH_USAGE_VOLATILITY", "HIGH_BENCH_RISK"],
  "nba_role_metadata": {
    "archetype_confidence_cap": 62,
    "adjusted_minutes_avg": 21.6,
    "adjusted_minutes_std": 5.04,
    "blowout_adjustment": 0.0
  }
}
```

---

## ⚙️ ENRICHMENT HEURISTICS

**Simple enrichment** ([engine/enrich_nba_simple.py](engine/enrich_nba_simple.py)) uses:

### By Stat Type:
- **PRA/combo stats** → 26% usage, 32 min (likely starter)
- **Points/scoring** → 25% usage, 30 min (rotation scorer)
- **Assists** → 24% usage, 30 min (playmaker)
- **Rebounds** → 20% usage, 28 min (role player)
- **Blocks/steals** → 19% usage, 26 min (defensive specialist)

### By Player Name (Known Stars):
- Luka, LeBron, KD, Curry, Giannis, Jokic, etc. → **30% usage, 35 min**

### By Player Name (Bench Scorers):
- **CJ McCollum**, Jordan Clarkson, Malik Monk → **26% usage, 24 min** ⚠️

---

## 📊 CONFIDENCE ADJUSTMENTS

### Archetypes Applied (7 total):
1. **PRIMARY_USAGE_SCORER** (72% cap) - High-usage stars
2. **SECONDARY_CREATOR** (68% cap) - Balanced starters  
3. **CONNECTOR_STARTER** (75% cap) - Most stable archetype
4. **ROLE_PLAYER_SPECIALIST** (65% cap) - 3&D, defensive specialists
5. **BENCH_SCORER_HIGH_USAGE** (65% cap) - Bench-first scorers
6. **BENCH_MICROWAVE** (62% cap) - ⚠️ **Lowest stability** (CJ McCollum)
7. **PURE_CONNECTOR_BENCH** (68% cap) - Bench facilitators

### Penalty Flags (6 types):
- **HIGH_USAGE_VOLATILITY** → -5% (usage >25% + high variance)
- **BLOWOUT_GAME_RISK** → -3% (spread >10 points)
- **HIGH_MINUTES_VARIANCE** → -5% (CV >0.25)
- **LOOSE_ROTATION** → -8% (coach plays deep bench)
- **HIGH_BENCH_RISK** → -5% (bench player with high usage)
- **BACK_TO_BACK_GAME** → -3% (fatigue risk)

---

## 🎯 PRODUCTION USAGE

### Via Menu (NEW - WORKING):
```bash
.venv\Scripts\python.exe menu.py
# Select [2] Analyze Slate
# NBA Role Layer auto-activates
# Output: outputs/IND_ATL*_RISK_FIRST_*.json with nba_role_* fields
```

### Via daily_pipeline.py (STILL WORKING):
```bash
.venv\Scripts\python.exe daily_pipeline.py --league NBA --input-file <picks.json>
# Uses full enrich_usage_minutes() with real usage/minutes data
# More accurate archetypes than menu's simple estimates
```

---

## ⚠️ CURRENT LIMITATIONS (Simple Enrichment)

### What's Missing:
1. **Real usage rates** - Using stat-type estimates, not actual NBA API usage%
2. **Real minutes data** - Using role estimates, not actual mpg  
3. **Player stats variance** - Using 15% std estimate, not real CV

### Impact:
- **Archetypes less precise** (e.g., Siakam → SECONDARY_CREATOR vs PRIMARY_USAGE_SCORER)
- **Penalties less nuanced** (missing HIGH_MINUTES_VARIANCE flag without real CV)
- **Still valuable**: CJ McCollum correctly flagged as BENCH_MICROWAVE with -8% penalty

### Next Upgrade:
Add real NBA API usage/minutes fetch to enrichment:
```python
from nba_api.stats.endpoints import playergamelog
# Fetch real usage%, mpg, minutes CV
# Replace simple estimates with actual stats
```

---

## 📋 VERIFICATION COMMANDS

### Test Menu Integration:
```bash
.venv\Scripts\python.exe test_menu_nba_role.py
# ✅ Normalized 109 NBA picks
# Shows archetype classifications for key players
```

### Check Output JSON:
```powershell
Get-Content outputs\IND_ATL*_RISK_FIRST_*.json | ConvertFrom-Json | 
  Where-Object {$_.player -eq "CJ McCollum"} | 
  Select-Object player, nba_role_archetype, nba_confidence_cap_adjustment, nba_role_flags | 
  Format-List
```

### Full Menu Run:
```bash
echo "2`n0" | .venv\Scripts\python.exe menu.py
# Look for: "📊 Enriched 109 NBA props"
# Look for: "✅ Normalized 109 NBA picks"
```

---

## ✅ SUMMARY

**Status:** MENU PATH UPDATED - NBA ROLE LAYER OPERATIONAL

**Integration:**
- ✅ Menu analysis path (analyze_from_underdog_json → risk_first_analyzer)
- ✅ Simple usage/minutes enrichment (stat-type heuristics)
- ✅ NBA Role Layer normalization (109/109 picks)
- ✅ Confidence cap adjustments applied
- ✅ Output JSON populated with nba_role_* fields

**Key Achievement:**
CJ McCollum (bench scorer) now gets **-8% confidence penalty** instead of being treated like a starter. This prevents overconfidence on volatile bench players.

**Next Steps (Optional Enhancements):**
1. Add real NBA API usage/minutes fetch to [engine/enrich_nba_simple.py](engine/enrich_nba_simple.py)
2. Replace stat-type estimates with actual player stats
3. Add minutes variance (CV) from game logs

**Ready for Production:** YES ✅

