# 🔧 SYSTEM UPDATE — February 3, 2026
## For: Data & Software Engineering Team

---

## 📋 EXECUTIVE SUMMARY

| Category | Count | Priority |
|----------|-------|----------|
| 🔴 CRITICAL BUGS (Fixed Today) | 2 | Resolved |
| 🟠 URGENT: Incomplete Implementations | 6 | HIGH |
| 🟡 DISABLED Features (Ready to Enable) | 4 | MEDIUM |
| 🔵 DEVELOPMENT Status Sports | 2 | LOW |
| ⚪ Future Enhancements | 5 | BACKLOG |

---

## ✅ BUGS FIXED TODAY (Feb 3, 2026)

### 1. Soccer Cross-Sport Save Error
**File:** `soccer/soccer_menu.py` (line 217-228)
**Issue:** Code called `.get()` on `AnalyzedProp` dataclass (should use attribute access)
**Fix:** Changed `prop.get('tier')` → `prop.tier`
**Status:** ✅ RESOLVED

### 2. Soccer 100% Probability Bug  
**File:** `soccer/soccer_slate_analyzer.py`
**Issue:** When player avg = 0, Poisson returned 100% UNDER (mathematically impossible for betting)
**Fix:** Added:
- Minimum average floor per stat (goals: 0.15, saves: 2.0, etc.)
- Confidence caps: ESTIMATE max 72%, DATABASE max 92%
**Status:** ✅ RESOLVED

---

## 🔴 URGENT: INCOMPLETE IMPLEMENTATIONS

### 1. Live Ingestion System (PAUSED)
**Location:** `live_ingestion/`
**Status:** 🟠 SKELETON CODE ONLY
**TODOs Found:**
```python
# pbp_normalizer.py:44
# TODO: Implement NBA API PBP fetching

# pbp_normalizer.py:49  
# TODO: Implement NBA API live streaming

# pbp_normalizer.py:69
# TODO: Implement boxscore polling for basic events
```
**Impact:** No live/in-game adjustments possible
**Effort:** 2-3 days
**Priority:** HIGH (for in-game betting)

---

### 2. Usage/Minutes Enrichment (HARDCODED)
**Location:** `engine/enrich_usage_minutes.py`
**Status:** 🟠 USING PLACEHOLDER DATA
**TODOs Found:**
```python
# Line 112
TODO: Replace with real data from:
    - nba_api endpoint
    - Manual CSV
    - Rotation tracker

# Line 152  
# TODO: Real data integration
```
**Impact:** Usage rate projections unreliable
**Effort:** 1 day
**Priority:** HIGH

---

### 3. Slate Gate (NOT IMPLEMENTED)
**Location:** `engine/slate_gate.py`
**Status:** 🔴 RAISES NotImplementedError
```python
# Line 58-59
# TODO: Integrate with ufa.ingest.espn or data_center
raise NotImplementedError("Call ESPN API or load from data_center/slate.json")
```
**Impact:** Cannot validate slate automatically
**Effort:** 0.5 day
**Priority:** MEDIUM

---

### 4. CFB Roster Gate (NOT IMPLEMENTED)
**Location:** `engine/roster_gate.py`
**Status:** 🔴 RAISES NotImplementedError
```python
# Line 239
raise NotImplementedError("CFB roster fetch requires CFBD_API_KEY integration")
```
**Impact:** College football pipeline blocked
**Effort:** 1 day (if CFB is priority)
**Priority:** LOW (CFB not in production)

---

### 5. Golf Weather API (PLACEHOLDER)
**Location:** `golf/ingest/manual_ingest.py`
**Status:** 🟡 STUBBED
```python
# Line 238
# TODO: Implement actual weather API
```
**Impact:** Weather adjustments not applied
**Effort:** 0.5 day
**Priority:** MEDIUM

---

### 6. Tennis Report Generation (NOT IMPLEMENTED)
**Location:** `generate_game_reports.py`
**Status:** 🟡 STUBBED
```python
# Line 402
# TODO: Implement tennis report generation logic
```
**Impact:** No automated tennis reports
**Effort:** 1 day
**Priority:** LOW

---

## 🟡 DISABLED FEATURES (Ready to Enable)

### Feature Flags Status (`config/feature_flags.json`)

| Feature | Status | Risk | Recommendation |
|---------|--------|------|----------------|
| `matchup_memory_enabled` | ❌ OFF | LOW | **ENABLE** — Code exists, tested |
| `probability_lineage` | ❌ OFF | LOW | **ENABLE** — Audit trail |
| `mc_hardening` | ❌ OFF | MEDIUM | Test first, then enable |
| `enable_new_features` (global) | ❌ OFF | HIGH | Keep OFF until features validated |

### To Enable Matchup Memory:
```json
// config/feature_flags.json
{
  "nba": {
    "matchup_memory_enabled": true  // Change from false
  }
}
```

---

## 🔵 SPORTS IN DEVELOPMENT STATUS

### 1. Golf
**Registry:** `config/sport_registry.json` → `status: "DEVELOPMENT"`
**Blocker:** Weather API not implemented
**To Promote:**
1. Implement weather API
2. Run 50+ pick validation
3. Change status to PRODUCTION

### 2. NHL  
**Registry:** `config/sport_registry.json` → `enabled: false, status: "DEVELOPMENT"`
**Blocker:** Goalie confirmation gate needs 2+ source validation
**To Promote:**
1. Enable in registry
2. Add DailyFaceoff scraper for goalie confirmation
3. Run 30+ pick validation
4. Change status to PRODUCTION

---

## 📊 SPORT-BY-SPORT HEALTH CHECK

| Sport | Status | Data Source | Known Issues |
|-------|--------|-------------|--------------|
| **NBA** | ✅ PRODUCTION | nba_api | Rate limits (429), usage data hardcoded |
| **Tennis** | ✅ PRODUCTION | Tennis Abstract | Manual entry, no live API |
| **CBB** | ✅ PRODUCTION | Sports Reference | No SLAM tier, volatile |
| **Soccer** | ✅ PRODUCTION | Manual | Limited DB (~100 players), estimate-heavy |
| **NFL** | ✅ FROZEN v1.0 | nflverse | READ-ONLY, no modifications |
| **Golf** | 🟡 DEVELOPMENT | DataGolf | Weather API missing |
| **NHL** | 🟡 DEVELOPMENT | NHL API | Disabled, goalie gate incomplete |

---

## 🔧 RECOMMENDED ACTION PLAN

### Week 1 (Immediate)
- [ ] Enable `matchup_memory_enabled` flag
- [ ] Enable `probability_lineage` flag  
- [ ] Complete `enrich_usage_minutes.py` real data integration

### Week 2
- [ ] Implement `slate_gate.py` ESPN integration
- [ ] Implement `golf/ingest/manual_ingest.py` weather API
- [ ] Promote Golf to PRODUCTION

### Week 3
- [ ] Enable NHL in registry
- [ ] Implement DailyFaceoff goalie scraper
- [ ] Complete `live_ingestion/pbp_normalizer.py`

### Week 4
- [ ] Test `mc_hardening` features
- [ ] Enable Beta distribution optimizer
- [ ] Full system calibration review

---

## 📁 FILES TO REVIEW

```
HIGH PRIORITY:
├── engine/enrich_usage_minutes.py      # Hardcoded data
├── engine/slate_gate.py                 # NotImplementedError
├── live_ingestion/pbp_normalizer.py    # TODOs everywhere
├── config/feature_flags.json            # Disabled features
└── config/sport_registry.json           # Sport status

MEDIUM PRIORITY:
├── golf/ingest/manual_ingest.py        # Weather TODO
├── soccer/data/player_database.py      # Only ~100 players
└── generate_game_reports.py            # Tennis TODO

LOW PRIORITY:
├── engine/roster_gate.py               # CFB integration
└── sports/nhl/                          # Disabled sport
```

---

## 🔐 CONFIGURATION LOCATIONS

| Config | Path | Purpose |
|--------|------|---------|
| Tier Thresholds | `config/thresholds.py` | SLAM/STRONG/LEAN cutoffs |
| Sport Registry | `config/sport_registry.json` | Enable/disable sports |
| Feature Flags | `config/feature_flags.json` | Toggle new features |
| Penalty Mode | `config/penalty_mode.json` | Data-driven vs full penalties |
| Data-Driven Penalties | `config/data_driven_penalties.py` | Calibration multipliers |

---

## 📝 NOTES FOR ENGINEERS

1. **Virtual Environment**: Always use `.venv/` (PEP 405)
2. **Testing**: Run `python -c "import <module>"` before deploying
3. **Governance**: All picks must go through `core/decision_governance.py`
4. **MC Immutability**: LLMs NEVER override Monte Carlo probabilities
5. **Calibration**: Track results in `calibration_history.csv`

---

## 📞 CONTACT

For questions about this system update, reference:
- `copilot-instructions.md` — Full system documentation
- `ARCHITECTURE.md` — Technical architecture
- `docs/ALL_SPORTS_ENGINEERING_REVIEW.md` — Detailed sport analysis

---

*Generated: February 3, 2026*
*System Version: UNDERDOG ANALYSIS v2.4*
