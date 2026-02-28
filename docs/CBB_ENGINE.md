# CBB ENGINE — TRUTH-ENFORCED (March-Safe)

**Version:** 1.0  
**Status:** RESEARCH (Paper Trading Only)  
**Architecture:** Monte Carlo Truth → Evidence Interpretation → Risk Controls

---

## System Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                         CBB ENGINE FLOW                           │
└───────────────────────────────────────────────────────────────────┘

┌───────────────┐
│  FINAL DATA   │ ◄── 2+ sources required (CollegeFootballData + manual)
└──────┬────────┘
       │
       ↓
┌───────────────┐
│ FEATURE BUILD │ ◄── Conference / Coach / Ref / Travel / Seed
└──────┬────────┘
       │
       ↓
┌───────────────┐
│  EDGE GEN     │ ◄── Poisson/NegBin model (NOT Normal)
└──────┬────────┘
       │
       ↓
┌───────────────┐
│ EDGE GATES    │ ◄── Minutes / Role / Blowout / Public / Tournament
└──────┬────────┘     (10 gates total, all hard-fail)
       │
       ↓
┌───────────────┐
│ VARIANCE GOV. │ ◄── Seed × Ref × Coach (triple interaction)
└──────┬────────┘
       │
       ↓
┌───────────────┐
│ PROB MODEL    │ ◄── NegBin with variance governors applied
└──────┬────────┘
       │
       ↓
┌───────────────┐
│ CONF + UNITS  │ ◄── March Compression + Unit Policy
└──────┬────────┘
       │
       ↓
┌───────────────┐
│ LIVE MONITOR  │ ◄── Pace / Fouls / Foul-Out / 2H Module
└──────┬────────┘
       │
       ↓
┌───────────────┐
│  DASHBOARD    │ ◄── Observable state (JSON + CLI)
└──────┬────────┘
       │
       ↓
┌───────────────┐
│ LADDER ENGINE │ ◄── Conditional in-game escalation (March only)
└──────┬────────┘
       │
       ↓
┌───────────────┐
│ RENDER / HALT │ ◄── Output or ABORT (no partial states)
└───────────────┘
```

---

## Pipeline Order (LOCKED)

1. **Ingest** FINAL data (2+ sources required)
2. **Build features** (minutes, conference, coach, ref, travel, seed)
3. **Generate edges** (Poisson model)
4. **Apply gates** (minutes → role → blowout → public → tournament)
5. **Apply variance governors** (seed × ref × coach triple interaction)
6. **Probability model** (NegBin with adjustments)
7. **Confidence caps** + unit compression
8. **Live monitors** (foul-out, pace, refs, 2H module)
9. **Dashboard update** (observable state)
10. **Ladder check** (conditional escalation)
11. **Render** or **ABORT** (no partial states)

---

## Season Regimes

| Regime | Dates | Variance Mult | Confidence Cap | Notes |
|--------|-------|---------------|----------------|-------|
| EARLY | Nov 1-20 | 1.35 | 60% | Unders favored, overs blocked |
| MID | Nov 21 - Jan 31 | 1.00 | 70% | Selective overs allowed |
| LATE | Feb 1 - Mar 5 | 1.10 | 70% | Conference positioning games |
| CONF_TOURN | Mar 6-14 | 1.20 | 65% | Unders-heavy |
| NCAA | Mar 15 - Apr 10 | 1.30 | 65% | Unders-only, unit compression |

---

## Kill Switches (Auto-Trigger)

| Condition | Action | Recovery |
|-----------|--------|----------|
| Public ≥75% | BLOCK edge | N/A |
| One loss day | UNDERS_ONLY | 2 consecutive wins |
| Live lock triggers ≥2 | UNDERS_ONLY | Game end |
| Foul-out prob ≥35% | UNDERS_ONLY | Game end |
| Daily exposure ≥10u | BLOCK new edges | Next day |

---

## Risk Controls (March)

| Control | Value | Enforcement |
|---------|-------|-------------|
| Daily risk | ≤1.25% | Hard block |
| Max units/day | 2.0u | Hard block |
| Max edges/game | 1 | Hard block |
| Stop-after-loss | Enabled | Auto-trigger |
| Overs allowed | NO | Hard block |

---

## Triple Interaction Variance Governor

The `seed_ref_coach.yaml` config handles **interaction effects** that single priors miss:

| Interaction | Variance Mult | Confidence Cap |
|-------------|---------------|----------------|
| HIGH seed + HIGH_FOUL refs + Calipari | 1.35 | 65% |
| LOW seed + LOW_FOUL refs + Tony Bennett | 0.92 | 72% |
| HIGH seed + NEUTRAL refs + Izzo | 1.18 | 70% |

---

## Live Modules

### Foul-Out Engine
- Computes per-player foul-out probability using Poisson hazard model
- Auto-locks unders when top 2 players have ≥35% foul-out risk
- Updates dashboard with risk levels

### Second-Half Module
- Triggers when: pace_ratio < 0.92 AND foul_rate < 0.90×baseline AND lead ≥ 6
- Blocks pregame overs, allows only 2H unders
- Reduces units by 20%

### Hedge Allocator
- Computes correlation score from seed gap, ref profile, pace volatility
- Recommends hedge % based on correlation (10-30%)
- Never hedges with overs in March

---

## Dashboard State (Observable)

```json
{
  "pace_ratio": 0.88,
  "fouls_per_min": 0.42,
  "baseline_fouls": 0.50,
  "top_foulout_probs": [0.38, 0.22],
  "variance_mult": 1.18,
  "confidence_cap": 0.70,
  "mode": "UNDERS_ONLY",
  "second_half_only": true,
  "hedge_active": true,
  "ladder_step": "HALF_TIME",
  "timestamp": "2026-03-21T14:32:00Z"
}
```

---

## Ladder Policy (March Only)

| Step | Condition | Unit Mult |
|------|-----------|-----------|
| PREGAME | March mode | 0.60 |
| HALF_TIME | Unders locked + foul_rate < 0.95×baseline | 0.40 |
| SECOND_HALF | pace < 0.90 + foulout_prob ≥ 0.30 | 0.30 |
| LOSS | Any loss | HALT |

**Philosophy:** Conditional reinforcement, NOT martingale. Any loss stops the ladder.

---

## File Structure

```
sports/cbb/
├── config/
│   ├── cbb_runtime.json
│   ├── thresholds.yaml
│   ├── season_regimes.yaml
│   ├── tournament_mode.yaml
│   ├── unit_policy.yaml
│   └── second_half.yaml          ← NEW
├── models/
│   ├── probability.py
│   ├── calibration.py
│   ├── conference_priors.json
│   ├── coach_priors.json
│   ├── ref_bias.json
│   ├── ref_crews.json
│   ├── seed_volatility.yaml
│   ├── seed_coach_matrix.yaml
│   ├── seed_ref_coach.yaml       ← NEW (triple interaction)
│   ├── travel_fatigue.yaml
│   ├── public_fade.yaml
│   └── hedge_allocator.py        ← NEW
├── live/
│   ├── __init__.py
│   ├── lock_unders.py
│   ├── foulout_model.py          ← NEW
│   ├── second_half.py            ← NEW
│   ├── dashboard_state.py        ← NEW
│   ├── ladder_policy.yaml        ← NEW
│   └── ladder_engine.py          ← NEW
├── runs/
│   ├── state.json
│   ├── update_state.py
│   └── risk_manager.py
├── edges/
├── features/
├── ingest/
├── render/
└── validate/
```

---

## Guarantees (Post-Implementation)

✔ Automation is **observable** (dashboard state)  
✔ Unders escalation is **conditional** (not reactive)  
✔ No doubling, no revenge  
✔ March risk curve is **convex-down**  
✔ Triple interactions are **enforced**  
✔ Live foul-outs **auto-defend capital**  
✔ Second-half unders are **systemic**  
✔ Hedges are **quantified**  
✔ Fully auditable (dashboard + logs)  

---

## Document Owner

**System:** CBB Engine  
**Status:** RESEARCH (promote to BETA after 50+ edges tracked)  
**Review Cycle:** After each phase gate  
