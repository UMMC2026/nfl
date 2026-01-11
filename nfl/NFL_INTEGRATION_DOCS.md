# NFL INTEGRATION SYSTEM
**Extended SOP v2.1 with Sport Segmentation**

---

## 1. Architecture Overview

The NFL system uses the **same EDGE-FIRST architecture** as NBA with **stricter validation gates**:

```
ESPN NFL Stats + NFL.com Stats
        ↓
Gate 2: Stat Agreement Validation (±5 yards, ±1 rec, ±0 TD)
        ↓
ingest_nfl_stats.py → Normalized Player Stats
        ↓
nfl_feature_builder.py → 11 Approved Features
        ↓
nfl_edge_generator.py → EDGE(player, game, direction)
        ↓
nfl_validation.py → 4 Gates (FINAL, cooldown, snap%, injury)
        ↓
nfl_resolve_results.py → Graded Picks
        ↓
generate_resolved_ledger.py (sport='NFL') → Unified Truth Ledger
```

---

## 2. Data Sources & Stat Agreement

**Primary Sources:**
- ESPN NFL Player Stats API
- NFL.com Official Stats Portal

**Gate 2 Validation (HARD BLOCK on Mismatch):**
```
Passing Yards:   ESPN ≠ NFL.com ±5 → BLOCK
Rushing Yards:   ESPN ≠ NFL.com ±3 → BLOCK
Receiving Yards: ESPN ≠ NFL.com ±3 → BLOCK
Receptions:      ESPN ≠ NFL.com ±1 → BLOCK
Touchdowns:      ESPN ≠ NFL.com ±0 → BLOCK (zero tolerance)
```

If mismatch detected, that game's learning is **BLOCKED**. No edge generation.

---

## 3. Confidence Caps (SOP v2.1 NFL)

Lower than NBA due to higher variance and play-dependent volatility:

```
Core Plays (snap ≥ 35%, role clear):    70% max confidence
Alt Plays (snap 20-35%, situational):   65% max confidence
Touchdown Props:                         55% max confidence
```

These are **hard caps** — no override, no exceptions.

---

## 4. The 11 Approved Features

Any feature outside this set → **BLOCKED**.

### Usage & Opportunity (snap-based)
- `snap_pct_rolling_7d` — Avg snap % last 7 days
- `snap_pct_rolling_14d` — Avg snap % last 14 days
- `targets_per_snap` — Usage rate (WR/TE)
- `carries_per_snap` — Usage rate (RB)
- `red_zone_share` — Team red zone touches / player red zone touches

### Efficiency
- `yards_per_target` — (rec yards / targets) — WR/TE
- `yards_per_carry` — (rush yards / carries) — RB
- `catch_rate` — (receptions / targets) — WR/TE
- `air_yards_share` — (air yards / team air yards) — WR/TE

### Volatility
- `week_to_week_std` — Standard deviation in production (last 8 weeks)
- `role_stability_score` — 1.0 - (std / mean snap %) — consistency metric

### Market Alignment
- `closing_line_value` — Official closing odds vs consensus
- `implied_team_total` — Vegas implied team points

---

## 5. Validation Gates (Sequential)

All 4 must **PASS** or edge is **NON-LEARNING**.

### Gate 1: Game Status = FINAL
```python
if game_status.upper() != "FINAL":
    BLOCK edge (do not generate)
```

### Gate 2: Stat Agreement (ESPN vs NFL.com)
```python
# Hardcoded tolerances
for each stat:
    diff = abs(espn[stat] - nfl_com[stat])
    if diff > tolerance:
        BLOCK learning for entire game
```

### Gate 3: 30-Minute Cooldown
```python
# NFL scores get corrected frequently
if (now - game_final_time) < 30 minutes:
    BLOCK edge (wait for corrections)
```

### Gate 4: Injury Certainty + Snap Data
```python
if injury_status == "QUESTIONABLE" (post-game):
    FLAG non-learning
if snap_pct is None:
    BLOCK edge
if snap_pct < 20% and snap_pct > 0%:
    FLAG non-learning (insufficient role)
```

---

## 6. Parlay Rules (Stricter for NFL)

**Blocked Correlations:**
```
WR + QB (same team)     → ❌ BLOCKED
RB + DEF (same team)    → ❌ BLOCKED
Any skill stack (same team) → ❌ BLOCKED (default)
```

**Allow Override (requires explicit flag):**
```python
ALLOW_CORRELATED=TRUE, RISK_TAG="HIGH_CORRELATION"
# But this is discouraged in SOP v2.1 NFL
```

---

## 7. Sport Segmentation in Resolved Ledger

The unified `resolved_ledger.csv` includes a `sport` column:

```csv
date,game_id,sport,player_name,stat,line,actual,outcome,confidence
2025-01-04,NFL_PIT_CLE,NFL,Lamar Jackson,passing_yards,275,284,HIT,0.68
2025-01-04,NBA_LAL_GSW,NBA,LeBron James,points,26.5,28,HIT,0.72
```

**Calibration by Sport:**
- NBA 7/14/30-day windows separate from NFL
- Confidence caps validated separately
- Rolling calibration checks by sport

---

## 8. Example: Complete NFL Edge Resolution

### Pick Submitted
```json
{
  "player_name": "Lamar Jackson",
  "team": "BAL",
  "game_id": "NFL_BAL_PIT_20250104",
  "stat": "passing_yards",
  "direction": "OVER",
  "line": 275,
  "position": "QB"
}
```

### Ingestion (ingest_nfl_stats.py)
1. Fetch ESPN: Lamar Jackson 284 passing yards
2. Fetch NFL.com: Lamar Jackson 284 passing yards
3. Gate 2: |284 - 284| = 0 ≤ tolerance (5) → PASS

### Features (nfl_feature_builder.py)
```python
snap_pct: 85%
snap_pct_rolling_7d: 87%
snap_pct_rolling_14d: 85%
yards_per_attempt: 8.2
week_to_week_std: 42
role_stability: 0.92  # Very consistent
```

### Edge Generation (nfl_edge_generator.py)
```
✓ EDGE(Lamar Jackson, BAL, passing_yards, OVER)
  snap_pct = 85% >= 20% → PASS
  position = QB → PASS
  features_complete = True → PASS
```

### Validation (nfl_validation.py)
```
Gate 1: game_status = FINAL ✓
Gate 2: stat_agreement = PASS ✓
Gate 3: cooldown = 40 min >= 30 min ✓
Gate 4: snap_pct = 85% >= 20%, no QUESTIONABLE ✓
Overall: PASS
```

### Resolution (nfl_resolve_results.py)
```
Outcome: 284 > 275 → HIT
Confidence: 68% (QB, snap 85%, stable role)
Sport: NFL
Non-learning: False
Feed to ledger ✓
```

---

## 9. Troubleshooting

### "Gate 2 FAILED: Stat Mismatch"
**Cause:** ESPN and NFL.com stats differ beyond tolerance  
**Action:** Wait 2-4 hours for official correction, re-ingest, or mark as NON-LEARNING  
**Prevention:** Check stat sources early (before 30-min cooldown expires)

### "Snap% < 20% — Edge Blocked"
**Cause:** Player had low snap count (injured, benched, rotational)  
**Action:** Review game notes; if unexpected, mark pick as NON-LEARNING context  
**Prevention:** Flag players with snap warnings before pick submission

### "QUESTIONABLE Status Post-Game"
**Cause:** Player listed as QUESTIONABLE for next game, retroactively  
**Action:** Mark as non-learning context, review next game's readiness  
**Prevention:** Avoid injury-prone players in touchdown props (most volatile)

### "Cooldown Not Met — Waiting 10 More Minutes"
**Cause:** Game finalized < 30 min ago  
**Action:** Automatic; edge will resolve after cooldown expires  
**Prevention:** Don't query during live game; wait for final status first

---

## 10. Configuration Reference

**File:** `nfl/nfl_config.yaml`

Key parameters (locked for SOP v2.1):
```yaml
cooldown_minutes: 30          # Wait before learning
min_snap_pct: 0.20            # Minimum play time
confidence_caps:
  core: 0.70                   # Main plays
  alt: 0.65                    # Situational
  touchdown: 0.55              # Highest variance
stat_tolerances:
  passing_yards: 5
  rushing_yards: 3
  receiving_yards: 3
  receptions: 1
  touchdowns: 0                # Zero tolerance
```

---

## 11. Integration Point

NFL feeds directly into `generate_resolved_ledger.py`:

```python
# In generate_resolved_ledger.py
if sport == "NFL":
    apply_nfl_calibration_checks()
    use_nfl_confidence_caps()
    separate_rolling_windows()
elif sport == "NBA":
    apply_nba_calibration_checks()
    use_nba_confidence_caps()
    separate_rolling_windows()
```

Both sports share the same ledger CSV with segmentation by `sport` column.

---

## 12. Next Steps

1. **ESPN API Integration** — Connect live ESPN NFL stats fetch (higher priority than NFL.com scraping)
2. **Position Models** — Build WR/RB/QB-specific feature weighting
3. **Auto-Calibration** — Adjust confidence caps by position/situation (2-week rolling)
4. **Audit Dashboard** — Weekly NFL calibration report vs NBA

---

**Status:** Production-ready (pending ESPN/NFL.com API keys)  
**Last Updated:** 2025-01-04  
**SOP Version:** v2.1 (NFL Extension)
