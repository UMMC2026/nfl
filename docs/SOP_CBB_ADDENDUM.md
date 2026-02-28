# CBB SOP Addendum — Standard Operating Procedures
## UNDERDOG ANALYSIS | College Basketball Integration

**Version:** 1.0 (RESEARCH)  
**Status:** Paper trading only — no Telegram broadcast  
**Effective:** Until Phase 6 paper run passes  

---

## 1. Overview

College Basketball (CBB) is integrated as an **isolated module** under `/sports/cbb/`. It follows the same three-layer architecture as NFL/NBA:

```
Layer 1: Monte Carlo (Truth Engine) — Poisson/NegBinom model
Layer 2: LLM Commentary — Evidence interpretation only
Layer 3: Cheat Sheet — Final presentation + risk warnings
```

**Key Differences from NBA:**
- No SLAM tier (max tier = STRONG)
- Stricter confidence caps (STRONG ≥70%, LEAN ≥60%)
- No composite stats (PRA, PR, PA)
- Poisson model (not Normal distribution)
- Variance multipliers for tournament games

---

## 2. Probability Model

### 2.1 Distribution Choice
CBB uses **Poisson** (or Negative Binomial for high-variance players) because:
- Game counts are smaller (discrete events)
- Variance ≠ mean (overdispersion common)
- Better tail behavior for low-sample stats

### 2.2 Confidence Caps
| Stat Class | Max Confidence |
|------------|----------------|
| Core (pts/reb/ast) | 70% (75% with sample gate) |
| Volume Micro (stl/blk/3pm) | 65% |
| Sequence Early (1H, 1Q) | 60% |

### 2.3 Tier Thresholds
| Tier | Probability |
|------|-------------|
| STRONG | ≥70% |
| LEAN | ≥60% |
| NO PLAY | <60% |

**No SLAM tier in CBB.** If probability computes to 80%+, cap at STRONG tier max.

---

## 3. Edge Gates

### 3.1 Base Gates (always active)
| Gate | Condition | Action |
|------|-----------|--------|
| Minutes | <20 mpg avg | Block UNDER |
| Composite | PRA/PR/PA | Block all |
| Blowout | >25% prob | Block OVER |
| Variance | std > 0.3×mean | Cap to LEAN |
| Sample | <8 games | Block all |

### 3.2 Tournament Gates (March Madness)
| Gate | Condition | Action |
|------|-----------|--------|
| Overs Block | Tournament game | Block all OVER |
| Confidence Cap | Tournament game | Max 65% |
| Max Edges | Per game | Max 1 edge |

### 3.3 State Gates
| Gate | Condition | Action |
|------|-----------|--------|
| Unders-Only | After 2 consecutive losses | Block all OVER |
| Daily Exposure | >10u daily | Block new edges |

---

## 4. Season Regimes

CBB season has distinct phases with different variance profiles:

| Regime | Dates | Variance Mult | Max Confidence |
|--------|-------|---------------|----------------|
| EARLY_SEASON | Nov 1-20 | 1.35 | 60% |
| MID_SEASON | Nov 21 - Jan 31 | 1.0 | 70% |
| LATE_SEASON | Feb 1 - Mar 5 | 1.10 | 70% |
| CONF_TOURNAMENT | Mar 6-14 | 1.20 | 65% |
| NCAA_TOURNAMENT | Mar 15 - Apr 10 | 1.30 | 65% |

---

## 5. Model Priors

### 5.1 Conference Strength
Located in `sports/cbb/models/conference_priors.json`.

Multiplies player mean projection:
- Power conferences (ACC, Big 12, Big East, SEC, Big Ten): 1.05-1.10
- Mid-majors (AAC, MWC, WCC, A10): 0.95-0.98
- Low-majors: 0.85-0.93

### 5.2 Coach Priors
Located in `sports/cbb/models/coach_priors.json`.

Adjusts pace and foul rate multipliers:
- Tony Bennett: pace 0.88, fouls 0.85 (slowest)
- Nate Oats: pace 1.15, fouls 1.05 (fastest)
- John Calipari: pace 1.05, fouls 1.15 (freshmen chaos)

### 5.3 Ref Bias
Located in `sports/cbb/models/ref_bias.json`.

Location-based adjustments:
- HOME: foul boost 1.07, variance 0.95
- AWAY: foul boost 0.97, variance 1.05
- NEUTRAL (tournament): foul boost 0.95, variance 1.10

### 5.4 Seed Volatility
Located in `sports/cbb/models/seed_volatility.yaml`.

Tournament seed gap variance multipliers:
- Same seed: 1.00
- Gap 1-2: 1.05
- Gap 5-8: 1.18
- Gap 13+: 1.40

### 5.5 Travel Fatigue
Located in `sports/cbb/models/travel_fatigue.yaml`.

Rest and travel adjustments:
- Back-to-back: mean 0.94, variance 1.25
- Tournament deep (Sweet 16+): mean 0.95, variance 1.30

---

## 6. State Management

### 6.1 Session Tracking
State stored in `sports/cbb/runs/state.json`:
- Daily record (W/L/P)
- Net units
- Current streak
- Bankroll policy

### 6.2 Auto-Unders Trigger
After **2 consecutive losses**:
1. `unders_only_mode` activates automatically
2. All OVER edges blocked
3. Clears after 2 consecutive wins

### 6.3 Bankroll Policies
| Policy | Trigger | Unit Mult |
|--------|---------|-----------|
| NORMAL | Net ≥0 | 1.0 |
| CONSERVATIVE | Win rate <40% | 0.75 |
| MARCH | Tournament | 0.5-0.8 |
| RECOVERY | Net ≤-3u | 0.5 |

---

## 7. Live Controls

### 7.1 Lock-Unders Trigger
In-game detection via `sports/cbb/live/lock_unders.py`.

Signals:
1. Pace ratio < 0.85 (pace collapse)
2. Fouls per minute > 0.6 (foul fest)
3. Shot clock violations ≥ 3

Combined momentum score ≥ 2.0 → LOCK_UNDERS_ALERT

**Note:** This surfaces alerts for manual confirmation, not automatic switching.

---

## 8. Menu Integration

CBB appears in main menu when `enabled: true` in `config/sport_registry.json`.

Current menu options:
1. Run Daily Pipeline (dry-run)
2. Run Daily Pipeline (full)
3. Check Session State
4. Toggle Unders-Only Mode
5. View Exposure Summary
6. Force Season Regime

---

## 9. Data Sources

**Primary:**
- CollegeFootballData API (via `cbb_api` wrapper)
- Manual line inputs (Underdog paste)

**Secondary:**
- KenPom (if available)
- ESPN CBB stats

**Blocked:**
- No scraping
- No real-time odds APIs without approval

---

## 10. Validation & Promotion

### 10.1 Phase Gates
| Phase | Requirement | Status |
|-------|-------------|--------|
| 1 | Module skeleton | ✅ Complete |
| 2 | Edge gates | ✅ Complete |
| 3 | Priors + regimes | ✅ Complete |
| 4 | State management | ✅ Complete |
| 5 | Paper run (2 weeks) | ⏳ Pending |
| 6 | Calibration review | ⏳ Pending |

### 10.2 Promotion to BETA
Requirements:
- 50+ edges tracked
- Calibration within ±5%
- No gate failures
- Manual sign-off

### 10.3 Promotion to PRODUCTION
Requirements:
- 200+ edges tracked
- Positive ROI on paper
- Full postmortem review
- Telegram integration tested

---

## 11. Emergency Procedures

### 11.1 Kill Switch
Set `enabled: false` in `config/sport_registry.json` to disable CBB instantly.

### 11.2 Full Rollback
Delete `/sports/cbb/` folder entirely — zero collateral damage to NFL/NBA.

### 11.3 Manual Override
```python
from sports.cbb.runs import force_unders_only, clear_unders_only

# Force unders-only
force_unders_only("Manual emergency stop")

# Clear override
clear_unders_only()
```

---

## Appendix A: File Structure

```
sports/cbb/
├── __init__.py          # Module init (RESEARCH status)
├── config.py            # CBB-specific settings
├── run_daily.py         # Pipeline entry point
├── menu_integration.py  # Main menu wiring
├── config/
│   ├── cbb_runtime.json
│   ├── thresholds.yaml
│   ├── season_regimes.yaml
│   ├── tournament_mode.yaml
│   └── unit_policy.yaml
├── models/
│   ├── probability.py
│   ├── calibration.py
│   ├── conference_priors.json
│   ├── coach_priors.json
│   ├── ref_bias.json
│   ├── ref_crews.json
│   ├── seed_volatility.yaml
│   ├── seed_coach_matrix.yaml
│   ├── travel_fatigue.yaml
│   └── public_fade.yaml
├── ingest/
├── features/
├── edges/
├── render/
├── validate/
├── live/
│   ├── __init__.py
│   └── lock_unders.py
└── runs/
    ├── __init__.py
    ├── state.json
    ├── update_state.py
    └── risk_manager.py
```

---

## Appendix B: Quick Reference

### Run Commands
```bash
# Dry run
python sports/cbb/run_daily.py --dry-run

# Full run
python sports/cbb/run_daily.py --surface HARD

# Check state
python -c "from sports.cbb.runs import get_session_summary; print(get_session_summary())"
```

### VS Code Task
Use task `Tennis: Daily Run (Dry Run)` template, adjust for CBB.

---

**Document Owner:** System  
**Last Updated:** Auto-generated  
**Review Cycle:** After each phase gate
