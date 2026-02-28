# NHL Standard Operating Procedure — v1.0

**STATUS:** DEVELOPMENT  
**EFFECTIVE:** 2026-02-02  
**OWNER:** UNDERDOG ANALYSIS  

---

## 0. Scope Lock (Non-Negotiable)

### v1.0 Markets
| Market | Supported | Notes |
|--------|-----------|-------|
| Moneyline | ✅ | Primary focus |
| Puck Line (±1.5) | ✅ | Poisson-derived |
| Game Totals | ✅ | 5.5 / 6.0 / 6.5 |
| Goalie Saves | ❌ | v1.1 candidate |
| Player Props | ❌ | v2.0+ |
| Live/In-Game | ❌ | v2.0+ |

### Granularity
- **Game-level + Goalie-centric**
- No player-level props until v2.0
- Pre-game only (no live adjustments)

---

## 1. Modeling Philosophy

**Hockey is goalie + shot quality driven. Team averages lie.**

### Primary Drivers (Ordered by Impact)
1. **Confirmed Goalie** — ABSOLUTE GATE
2. **Shot Quality** — xG, slot vs point, high-danger chances
3. **5v5 vs Special Teams** — Separate modeling required
4. **Rest / Travel / Back-to-Back** — Material impact
5. **Home Ice Advantage** — Real, not cosmetic (~3-4%)

### Key Insight
> If goalie is not confirmed → **NO PLAY**. No exceptions.

---

## 2. Data Layers

### LAYER A — Schedule & Context
| Field | Source | Required |
|-------|--------|----------|
| `game_date` | NHL API | ✅ |
| `venue` | NHL API | ✅ |
| `home_team` / `away_team` | NHL API | ✅ |
| `rest_days_home` / `rest_days_away` | Derived | ✅ |
| `travel_distance_away` | Lookup table | ⚠️ v1.1 |
| `is_back_to_back` | Derived | ✅ |

### LAYER B — Goalie Intelligence (CRITICAL)
| Field | Source | Required |
|-------|--------|----------|
| `goalie_confirmed` | DailyFaceoff + beat reporters | ✅ GATE |
| `confirmation_sources` | Array of sources | ✅ (min 2) |
| `last_10_sv_pct` | NHL API / NST | ✅ |
| `last_10_gsaa` | Natural Stat Trick | ✅ |
| `last_10_hd_sv_pct` | High-danger save % | ⚠️ v1.1 |
| `is_b2b_start` | Derived | ✅ |
| `days_since_last_start` | Derived | ✅ |

### LAYER C — Team Shot Profile
| Field | Source | Required |
|-------|--------|----------|
| `xgf_5v5` | Natural Stat Trick | ✅ |
| `xga_5v5` | Natural Stat Trick | ✅ |
| `hdcf_pct` | High-danger chance % | ✅ |
| `shot_suppression_rank` | Derived | ⚠️ v1.1 |

### LAYER D — Special Teams
| Field | Source | Required |
|-------|--------|----------|
| `pp_xg_per_60` | NST | ✅ |
| `pk_xga_per_60` | NST | ✅ |
| `pp_pct` | NHL API | ✅ |
| `pk_pct` | NHL API | ✅ |

---

## 3. Hard Gates (Fail-Fast)

### GATE 1: Goalie Confirmation
```
IF goalie_status NOT IN ["CONFIRMED", "EXPECTED"]
   OR confirmation_sources < 2
THEN:
   pick_state = REJECTED
   reason = "GOALIE_UNCONFIRMED"
```
**No overrides. Ever.**

### GATE 2: Sample Sufficiency
```
IF goalie_starts_last_30_days < 5
THEN:
   max_probability = 0.58
   risk_tag = "SMALL_SAMPLE_GOALIE"
```

### GATE 3: Back-to-Back Goalie
```
IF goalie_is_b2b_start = TRUE
THEN:
   probability -= 0.04  # 4% penalty
   risk_tag = "B2B_GOALIE"
```

### GATE 4: Market Sanity (Edge Threshold)
```
IF ABS(model_prob - implied_prob) < 0.02
THEN:
   pick_state = REJECTED
   reason = "INSUFFICIENT_EDGE"
```
**Minimum edge: 2%**

### GATE 5: Probability Floor
```
IF model_prob < 0.58
THEN:
   pick_state = REJECTED
   reason = "LOW_PROBABILITY"
```

---

## 4. Probability Engine

### Step 1 — Expected Goals Model
```python
xG_team = (
    0.45 * team_5v5_xgf +
    0.25 * opponent_5v5_xga +
    0.20 * goalie_adjusted_sv_pct_delta +
    0.10 * special_teams_delta
)
```

**Goalie Adjustment:**
```python
goalie_delta = (goalie_sv_pct - league_avg_sv_pct) * expected_shots
# league_avg_sv_pct ≈ 0.905 (2025-26)
```

### Step 2 — Goal Distribution (Poisson)
```python
from scipy.stats import poisson

lambda_home = xG_home * home_ice_multiplier  # 1.03-1.04
lambda_away = xG_away

# Simulate 20,000 games
simulations = 20000
```

### Step 3 — Market Probability Extraction
```python
# Moneyline
p_home_win = sum(home > away) / simulations
p_away_win = sum(away > home) / simulations

# Puck Line ±1.5
p_home_cover = sum(home - away > 1.5) / simulations
p_away_cover = sum(away - home > -1.5) / simulations

# Totals
p_over_5_5 = sum(home + away > 5.5) / simulations
p_under_5_5 = sum(home + away < 5.5) / simulations
```

---

## 5. Confidence Tiers

| Tier | Probability Range | Allowed in Parlay |
|------|-------------------|-------------------|
| **STRONG** | 64% – 69% | ✅ Max 2 legs |
| **LEAN** | 58% – 63% | ✅ Singles only |
| **NO PLAY** | < 58% | ❌ |

### ⚠️ NO SLAM TIER IN NHL v1.0
Variance too high. Goalie variance alone introduces ±5% swing.

### Confidence Caps by Condition
| Condition | Max Confidence |
|-----------|----------------|
| Small sample goalie (<5 starts) | 58% |
| B2B goalie start | 64% |
| Travel >2 time zones | 66% |
| Backup goalie | 60% |

---

## 6. Risk Tags

| Tag | Trigger | Impact |
|-----|---------|--------|
| `GOALIE_DEPENDENT` | Always (NHL default) | Info only |
| `B2B_GOALIE` | Same goalie on back-to-back | -4% prob |
| `SMALL_SAMPLE_GOALIE` | <5 starts in 30 days | Cap 58% |
| `BACKUP_GOALIE` | Non-starter confirmed | Cap 60% |
| `TRAVEL_FATIGUE` | >2 timezone shift | -2% prob |
| `RIVALRY_GAME` | Divisional / historical | Info only |
| `PLAYOFF_IMPLICATIONS` | Late season, tight race | +2% variance |

---

## 7. Output Schema

```json
{
  "sport": "NHL",
  "game_id": "2026020XXX",
  "game": "BOS @ NYR",
  "game_time": "2026-02-15T19:00:00-05:00",
  "goalies": {
    "away": {
      "name": "Jeremy Swayman",
      "status": "CONFIRMED",
      "confirmation_sources": ["dailyfaceoff", "bruins_beat"],
      "last_10_sv_pct": 0.921,
      "last_10_gsaa": 2.4,
      "is_b2b": false
    },
    "home": {
      "name": "Igor Shesterkin",
      "status": "CONFIRMED",
      "confirmation_sources": ["dailyfaceoff", "nyr_beat"],
      "last_10_sv_pct": 0.928,
      "last_10_gsaa": 4.1,
      "is_b2b": false
    }
  },
  "market": "Moneyline",
  "side": "NYR",
  "model_prob": 0.621,
  "implied_prob": 0.565,
  "edge": 0.056,
  "tier": "LEAN",
  "pick_state": "OPTIMIZABLE",
  "risk_tags": ["GOALIE_DEPENDENT"],
  "model_inputs": {
    "home_xg": 2.85,
    "away_xg": 2.41,
    "simulations": 20000
  },
  "sources": ["nhl_api", "naturalstattrick", "dailyfaceoff"],
  "run_id": "nhl_20260215_001",
  "audit_hash": "sha256:abc123..."
}
```

---

## 8. Calibration Requirements

### Pre-Production (MANDATORY)
- [ ] Paper trade 50 games minimum
- [ ] Achieve Brier score ≤ 0.24
- [ ] Goalie confirmation accuracy ≥ 95%
- [ ] Edge profitability: ROI ≥ 3% on STRONG tier

### Ongoing
- Track all picks in `calibration/calibration_history.csv`
- Weekly calibration report via `calibration/unified_tracker.py --sport nhl`
- Auto-pause if Brier > 0.28 for 20+ picks

---

## 9. Data Sources

| Source | Purpose | Rate Limit |
|--------|---------|------------|
| NHL API | Schedule, scores, basic stats | None |
| Natural Stat Trick | xG, GSAA, HD chances | Scrape cautiously |
| DailyFaceoff | Goalie confirmations | Manual check |
| MoneyPuck | Advanced metrics (backup) | None |
| Odds API | Market implied probabilities | API key |

---

## 10. Directory Structure

```
sports/nhl/
├── __init__.py
├── SOP_NHL_v1.0.md          # This file
├── README.md
├── config/
│   ├── thresholds.py        # NHL-specific caps
│   └── teams.json           # Team metadata
├── ingest/
│   ├── schedule.py          # NHL API schedule
│   ├── goalie_status.py     # DailyFaceoff scraper
│   └── xg_stats.py          # NST integration
├── goalies/
│   ├── confirmation_gate.py # HARD GATE
│   └── goalie_model.py      # SV%, GSAA processing
├── models/
│   ├── xg_model.py          # Expected goals
│   └── poisson_sim.py       # Game simulation
├── gates/
│   ├── goalie_gate.py       # Gate 1
│   ├── sample_gate.py       # Gate 2
│   ├── b2b_gate.py          # Gate 3
│   └── edge_gate.py         # Gate 4
├── outputs/
│   └── .gitkeep
├── run_daily.py             # Main entry point
└── validate_output.py       # Render gate
```

---

## 11. Integration Points

### Calibration
```python
from calibration.unified_tracker import UnifiedCalibration
tracker = UnifiedCalibration()
tracker.log_pick(pick, sport="nhl")
```

### Telegram
```python
from telegram_push import push_signals
# NHL picks follow same schema as NBA
```

### Thresholds
```python
# In config/thresholds.py, add:
SPORT_TIER_OVERRIDES["NHL"] = {
    "SLAM": None,      # DISABLED
    "STRONG": 0.64,
    "LEAN": 0.58,
}
```

---

## 12. Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-02-02 | Initial release. Moneyline, Puck Line, Totals. |

---

## 13. Approval

- [ ] SOP reviewed by system owner
- [ ] Paper trading complete (50 games)
- [ ] Calibration Brier ≤ 0.24 achieved
- [ ] Integration tests passing

**DO NOT ENABLE PRODUCTION UNTIL ALL BOXES CHECKED.**
