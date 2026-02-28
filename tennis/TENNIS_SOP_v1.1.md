# TENNIS SOP v1.1 — SURFACE-AWARE · LOCKED

**Status:** PRODUCTION-READY  
**Version:** 1.1.0  
**Lock Date:** 2026-01-28  
**Breaking Changes:** Surface parameter now MANDATORY

No structural changes without version bump.

---

## I. SCOPE

| Item | Value |
|------|-------|
| Sport | Tennis (ATP / WTA singles) |
| Markets Enabled | Total Sets, Player Aces, Total Games |
| Markets Excluded | Match Winner, Parlays, Live Betting |

---

## II. SURFACE GATE (NEW — MANDATORY)

### Surface Must Be Specified

```bash
# REQUIRED parameter
python tennis/run_daily.py --surface HARD|CLAY|GRASS
```

| Condition | Action |
|-----------|--------|
| Surface missing | ❌ **ABORT** |
| Mixed data (indoor + outdoor) | ❌ **ABORT** |
| Player < 15 matches on surface | ⚠️ Confidence cap 62% |
| Surface mismatch with tournament | ❌ **ABORT** |

### Surface-Specific Adjustments

| Surface | Ace Prior | Hold Prior | Variance | Notes |
|---------|-----------|------------|----------|-------|
| **HARD** | Baseline | Baseline | Baseline | Default surface |
| **CLAY** | -15% | -3% | +5% | Longer rallies, fewer aces |
| **GRASS** | +20% | +5% | +15% | Serve dominance, high variance |

### Tournament → Surface Mapping (Canonical)

| Surface | Tournaments |
|---------|-------------|
| **HARD** | Australian Open, US Open, ATP Finals, Indian Wells, Miami, Cincinnati, Shanghai |
| **CLAY** | French Open, Monte-Carlo, Rome, Madrid, Barcelona, Roland Garros |
| **GRASS** | Wimbledon, Halle, Queen's Club, Eastbourne, Stuttgart |

If tournament not in mapping → surface MUST be explicitly provided or **ABORT**.

### Surface Experience Gate

| Matches on Surface | Action |
|--------------------|--------|
| < 5 | ❌ **BLOCK** player |
| 5-14 | ⚠️ Cap confidence at 62% |
| 15-29 | ⚠️ Cap confidence at 68% |
| ≥ 30 | ✅ No penalty |

---

## III. ENGINES DEPLOYED

### 1️⃣ TOTAL SETS ENGINE ✅ (Primary)

- **Role:** Core tennis profit driver
- **Why:** Clean parity signal, low data noise
- **Volume:** Moderate
- **Risk:** Controlled

### 2️⃣ PLAYER ACES ENGINE ⚠️ (Selective)

- **Role:** Opportunistic edge capture
- **Why:** Strong when constrained, deadly when loose
- **Volume:** Very low (1 play max)
- **Risk:** High if undisciplined

### 3️⃣ TOTAL GAMES ENGINE ⚠️ (Secondary)

- **Role:** Situational supplement
- **Why:** Sensitive to tiebreak math
- **Volume:** Low
- **Risk:** Medium

---

## III. PRODUCTION CONSTRAINTS (LOCKED)

| Constraint | Value |
|------------|-------|
| Max plays / day | **5 total** |
| Max plays / engine | **2** (1 for aces) |
| Max markets / player | **1** |
| Probability clamp | **55% – 72%** |
| Output if validation fails | **ABORT** |

---

## IV. CORE TRUTH RULES

1. **One engine = one market**  
2. **One player = one market per slate**  
3. **Hard BLOCK gates before probability**  
4. **Validation failure aborts output**  
5. **Max 5 plays total, always**

---

## V. CONFIDENCE TIERS

| Tier | Probability | Action |
|------|-------------|--------|
| STRONG | ≥ 66% | Play |
| LEAN | 58% – 65% | Play (reduced) |
| NO_PLAY | < 58% | Skip |
| BLOCKED | N/A | Filtered by gate |

---

## VI. EXECUTION ORDER (MANDATORY)

```
1. ingest_tennis.py        # Load player data
2. generate_*_edges.py     # Run all 3 engines
3. validate_tennis_output.py  ← HARD STOP
4. render_report.py        # Read-only output
5. send_telegram.py        # Optional delivery
```

**Skipping step 3 is forbidden.**

---

## VII. BLOCK RULES

### Global Blocks (All Engines)
- Missing player stats
- Elo gap > 200
- Either player hold% < 75%
- Surface mismatch (no surface data)

### Total Sets Specific
- Qualifier vs Top-20 (massive ranking gap)
- Straight set rate > 72%

### Player Aces Specific
- Ace rate < 7%
- Non-elite server (ace < 9% AND rank > 30)
- Clay + ace rate < 8%
- First serve % < 60%

### Total Games Specific
- Line ≥ 36.5 AND elo gap > 120
- Line ≥ 36.5 AND hold% < 78%

---

## VIII. BACKTEST THRESHOLDS

| Engine | Minimum Win Rate |
|--------|------------------|
| TOTAL_SETS | ≥ 58% |
| PLAYER_ACES | ≥ 56% |
| TOTAL_GAMES | ≥ 55% |

If not met (n ≥ 20 sample) → engine downgrade.

---

## IX. FILE STRUCTURE

```
tennis/
├── config/
│   ├── tennis_global.json
│   ├── totals_games.json
│   ├── totals_sets.json
│   └── player_aces.json
├── ingest/
│   └── ingest_tennis.py
├── engines/
│   ├── generate_totals_sets_edges.py
│   ├── generate_player_aces_edges.py
│   └── generate_totals_games_edges.py
├── validate/
│   └── validate_tennis_output.py
├── render/
│   └── render_report.py
├── telegram/
│   └── send.py
├── backtest/
│   ├── backtest_engine.py
│   ├── run_backtest.py
│   └── data/
├── inputs/          # Daily slate files
├── outputs/         # Generated edges
├── run_daily.py     # Main orchestrator
└── run_tennis_pipeline.py  # Alternative runner
```

---

## X. VS CODE TASKS

| Task | Description |
|------|-------------|
| Tennis: Daily Run (Full) | Complete pipeline with Telegram |
| Tennis: Daily Run (Dry Run) | Validation only |
| Tennis: Backtest | Run historical backtest |
| Tennis: Run Full Pipeline | Alternative orchestrator |
| Tennis: Validate Output (HARD GATE) | Manual validation |

---

## XI. ENVIRONMENT VARIABLES

```
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_CHAT_ID=<your_chat_id>
```

---

## XII. WHAT THIS MODULE CAN DO

- ✅ Run unattended daily
- ✅ Sell standalone
- ✅ Disable independently
- ✅ Calibrate other sports
- ✅ Full audit trail

---

## XIII. WHAT THIS MODULE WILL NOT DO

- ❌ Match Winner (yet)
- ❌ Parlays
- ❌ Live betting
- ❌ Same-player multi-market
- ❌ SLAM tier
- ❌ Intuition overrides

---

**This SOP is governance-binding.**
