# CALIBRATION_HISTORY.CSV Schema

## Purpose
Immutable log of every pick: prediction → governance → decision → result → learning.

One row per pick. Never updated (new rows only). Indexed by `pick_id`.

---

## Field Definitions

### A. PICK IDENTIFICATION (Immutable)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `pick_id` | STRING (UUID) | `pick_2026010201_jones_pts` | Globally unique. Format: `pick_YYYYMMDDSS_playername_stat` |
| `slate_date` | DATE | `2026-01-02` | Game date (not entry date) |
| `slate_id` | STRING | `JAN02_2026` | Slate identifier for grouping |
| `player_name` | STRING | `LeBron James` | Must match exact roster spelling |
| `team` | STRING | `LAL` | 3-letter team code |
| `stat_category` | STRING | `points\|assists\|rebounds\|pts+reb+ast\|...` | Enumerated stat type |
| `line` | FLOAT | `24.5` | Sportsbook line (exact) |
| `direction` | STRING | `OVER\|UNDER` | Case-sensitive |
| `opponent_team` | STRING | `BOS` | Opposing team code |

---

### B. PREDICTION DATA (From CDF Model)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `prob_raw` | FLOAT [0.0–1.0] | `0.872` | Pure CDF probability, no governance |
| `mu` | FLOAT | `28.4` | Mean from 10-game rolling average |
| `sigma` | FLOAT | `4.2` | Std dev from 10-game rolling average |
| `sample_size` | INT | `8` | Number of recent games available |
| `tier_statistical` | STRING | `SLAM\|STRONG\|LEAN\|BELOW` | Based on `prob_raw` at statistical thresholds (90%, 80%, 70%) |

---

### C. GOVERNANCE FLAGS (Applied Before Decision)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `blowout_risk` | STRING | `Low\|Moderate\|High` | Spread-based classification |
| `player_role` | STRING | `franchise_star\|high_usage\|solid_contributor\|bench_scorer\|role_player` | Role classification from PLAYER_ROLES |
| `minutes_survival_base` | FLOAT [0.0–1.0] | `0.78` | Role-specific survival probability |
| `garbage_time_eligible` | BOOLEAN | `True\|False` | True = risk of early benching in blowouts |
| `rest_days` | INT | `2` | Days since last game (if available) |
| `rest_flag` | STRING | `OK\|CAUTION\|RISK` | OK=2+d, CAUTION=1d, RISK=B2B |
| `sample_size_flag` | STRING | `OK\|CAUTION\|RISK` | OK=10+ games, CAUTION=5–9, RISK=<5 |
| `usage_trend` | STRING | `UP\|STABLE\|DOWN\|UNKNOWN` | Usage rate direction (if detectable) |
| `overtime_flag` | BOOLEAN | `True\|False` | True if game went to OT (valid outcome but isolated in learning) |

---

### D. GOVERNANCE ADJUSTMENTS (Penalties Applied)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `penalty_blowout_pct` | FLOAT | `-0.06` | Blowout risk adjustment (negative = reduction) |
| `penalty_rest_pct` | FLOAT | `-0.05` | Rest-related adjustment |
| `penalty_shrinkage_pct` | FLOAT | `-0.28` | Regression-to-mean shrinkage (for high-conf picks) |
| `penalty_other_pct` | FLOAT | `0.0` | Any other manual adjustment |
| `total_penalty_pct` | FLOAT | `-0.39` | Sum of all penalties |

---

### E. CALIBRATED DECISION (After Governance)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `prob_calibrated` | FLOAT [0.0–1.0] | `0.482` | `prob_raw + total_penalty_pct` (floor 0.0, no ceiling) |
| `tier_calibrated` | STRING | `STRONG\|LEAN\|BELOW` | Based on `prob_calibrated` at calibrated thresholds (75%, 60%, 52%) |
| `recommended_action` | STRING | `PLAY\|CONDITIONAL\|PASS` | System recommendation (not user decision) |
| `confidence_note` | STRING | `"High blowout risk, bench scorer"` | Human-readable summary of concerns |

---

### F. EXECUTION & RESULT (After Game)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `actually_placed` | BOOLEAN | `True\|False` | Was the pick actually wagered? (not filled until after game) |
| `entry_format` | STRING | `POWER_3L\|FLEX_4L\|STANDALONE` | Format if placed |
| `actual_value` | FLOAT | `23.8` | Actual stat value at end of game (null if not played) |
| `outcome` | STRING | `HIT\|MISS\|PUSH\|NOT_PLAYED\|INJURY\|UNKNOWN` | Result enumeration |
| `minutes_played` | INT | `28` | Actual minutes played (null if unknown) |
| `terminal_state` | STRING | `NO_GAME` | `NO_GAME` when game never played (POSTPONED/CANCELLED/RESCHEDULED), else null |

---

### G. FAILURE ATTRIBUTION (If `outcome` = MISS)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `failure_primary_cause` | STRING | `MINUTES_CUT\|INJURY\|USAGE_COLLAPSE\|SMALL_SAMPLE\|VARIANCE\|GOVERNANCE_MISS\|LATE_SCRATCH_OR_REMOVAL` | **Single cause only (no double-counting)** |
| `failure_detail` | STRING | `"Benched in Q4 (blowout +28 at halftime)"` | Context for why miss happened |
| `governance_flag_present` | BOOLEAN | `True` | Was the risk flag in place? |
| `governance_flag_name` | STRING | `blowout_risk\|minutes_survival\|rest_flag` | Which flag applied (if any) |
| `penalty_was_sufficient` | BOOLEAN | `False` | In hindsight, did penalty cushion enough? |
| `suggested_penalty_increase_pct` | FLOAT | `0.12` | If insufficient, how much should penalty have been? |

---

### H. LEARNING & UPDATES (For Feedback Loop)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `learning_signal` | BOOLEAN | `True` | Does this pick teach the system something? |
| `learning_type` | STRING | `CONFIRM\|REFUTE\|EDGE_CASE\|NONE` | Type of learning |
| `suggested_rule_change` | STRING | `"Blowout penalty: −6% → −9% for bench scorers"` | Auto-generated rule suggestion |
| `confidence_in_suggestion` | STRING | `HIGH\|MEDIUM\|LOW` | How confident is this change? |
| `learning_gate_passed` | BOOLEAN | `True\|False` | True if `is_learning_ready()` approved this row for learning |
| `correction_risk` | BOOLEAN | `True\|False` | True if post-final stat correction risk was detected (row excluded from automated learning) |

---

### I. METADATA (Bookkeeping)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `created_at` | DATETIME | `2026-01-02T14:23:45Z` | When row was created |
| `result_posted_at` | DATETIME | `2026-01-03T02:15:30Z` | When outcome was recorded (null if pending) |
| `audited` | BOOLEAN | `False` | Has human verified failure attribution? |
| `notes` | STRING | `"Multiple data quality issues; treat with caution"` | Optional audit notes |

---

## Enumeration Values (Locked)

### `stat_category`
```
points, assists, rebounds, steals, blocks, turnovers,
pts+reb, pts+ast, reb+ast, pts+reb+ast,
1q_pts, 2q_pts, 3q_pts, 4q_pts
```

### `outcome`
```
HIT              — Pick hit the line
MISS             — Pick missed the line
PUSH             — Exact line hit (no W/L)
NOT_PLAYED       — Player didn't take court
INJURY           — Injury prevented play
CANCELLED        — Game/slate cancelled
UNKNOWN          — Can't determine (data gap)
```

### `failure_primary_cause`
```
MINUTES_CUT      — Blowout or rest-related benching
INJURY           — In-game or pre-game injury
USAGE_COLLAPSE   — Player's role/touches dropped unexpectedly
SMALL_SAMPLE     — <10 games of data led to overestimate
VARIANCE         — Correct prediction, unlucky outcome
GOVERNANCE_MISS  — Missing flag or insufficient penalty
LATE_SCRATCH_OR_REMOVAL — Active pregame but did not meaningfully play (<5 minutes)
```

### `player_role`
```
franchise_star        — High minutes guarantee (LeBron, Giannis, Luka)
high_usage            — High % of offense (most #1 options)
solid_contributor     — Consistent rotation (75%+ games)
role_player           — Specialist/limited role (40–60% availability)
bench_scorer          — Secondary bench (high blowout risk)
```

### `blowout_risk`
```
Low               — Spread ≤ 3.5
Moderate          — Spread 3.5–6.0
High              — Spread > 6.0
```

### `tier_*`
```
SLAM              — ≥ threshold
STRONG            — Middle threshold
LEAN              — Lower threshold
BELOW             — Below threshold
```

---

## Example Rows

### Example 1: HIT (High Confidence, No Governance Issues)

```csv
pick_id,slate_date,slate_id,player_name,team,stat_category,line,direction,opponent_team,
prob_raw,mu,sigma,sample_size,tier_statistical,
blowout_risk,player_role,minutes_survival_base,garbage_time_eligible,rest_days,rest_flag,sample_size_flag,usage_trend,
penalty_blowout_pct,penalty_rest_pct,penalty_shrinkage_pct,penalty_other_pct,total_penalty_pct,
prob_calibrated,tier_calibrated,recommended_action,confidence_note,
actually_placed,entry_format,actual_value,outcome,minutes_played,
failure_primary_cause,failure_detail,governance_flag_present,governance_flag_name,penalty_was_sufficient,suggested_penalty_increase_pct,
learning_signal,learning_type,suggested_rule_change,confidence_in_suggestion,
created_at,result_posted_at,audited,notes

pick_2026010201_giannis_pts,2026-01-02,JAN02_2026,Giannis Antetokounmpo,MIL,points,27.5,OVER,BOS,
0.847,31.5,4.2,10,STRONG,
Low,franchise_star,0.94,False,2,OK,OK,STABLE,
-0.03,0.0,-0.12,0.0,-0.15,
0.697,STRONG,PLAY,"Close matchup, franchise star, no risk flags",
True,POWER_3L,32.1,HIT,36,
NULL,NULL,False,NULL,True,NULL,
True,CONFIRM,NULL,NULL,
2026-01-02T14:23:45Z,2026-01-03T02:15:30Z,False,NULL
```

### Example 2: MISS (Blowout Penalty Insufficient)

```csv
pick_id,slate_date,slate_id,player_name,team,stat_category,line,direction,opponent_team,
prob_raw,mu,sigma,sample_size,tier_statistical,
blowout_risk,player_role,minutes_survival_base,garbage_time_eligible,rest_days,rest_flag,sample_size_flag,usage_trend,
penalty_blowout_pct,penalty_rest_pct,penalty_shrinkage_pct,penalty_other_pct,total_penalty_pct,
prob_calibrated,tier_calibrated,recommended_action,confidence_note,
actually_placed,entry_format,actual_value,outcome,minutes_played,
failure_primary_cause,failure_detail,governance_flag_present,governance_flag_name,penalty_was_sufficient,suggested_penalty_increase_pct,
learning_signal,learning_type,suggested_rule_change,confidence_in_suggestion,
created_at,result_posted_at,audited,notes

pick_2026010202_clarkson_pts,2026-01-02,JAN02_2026,Jordan Clarkson,UTA,points,8.5,OVER,PHX,
0.798,15.1,3.8,9,STRONG,
High,bench_scorer,0.78,True,1,CAUTION,CAUTION,DOWN,
-0.08,-0.05,0.0,0.0,-0.13,
0.668,STRONG,PLAY,"High blowout risk, bench scorer flagged",
True,POWER_3L,4.2,MISS,14,
MINUTES_CUT,"Benched in Q4 after PHX went up +32",True,blowout_risk,False,0.08,
True,REFUTE,"Bench scorer + High blowout: increase penalty from −8% to −16%",HIGH,
2026-01-02T14:23:45Z,2026-01-03T02:15:30Z,True,"Confirmed benching via replay"
```

### Example 3: MISS (Missing Flag — Variance)

```csv
pick_id,slate_date,slate_id,player_name,team,stat_category,line,direction,opponent_team,
prob_raw,mu,sigma,sample_size,tier_statistical,
blowout_risk,player_role,minutes_survival_base,garbage_time_eligible,rest_days,rest_flag,sample_size_flag,usage_trend,
penalty_blowout_pct,penalty_rest_pct,penalty_shrinkage_pct,penalty_other_pct,total_penalty_pct,
prob_calibrated,tier_calibrated,recommended_action,confidence_note,
actually_placed,entry_format,actual_value,outcome,minutes_played,
failure_primary_cause,failure_detail,governance_flag_present,governance_flag_name,penalty_was_sufficient,suggested_penalty_increase_pct,
learning_signal,learning_type,suggested_rule_change,confidence_in_suggestion,
created_at,result_posted_at,audited,notes

pick_2026010203_anunoby_pts,2026-01-02,JAN02_2026,OG Anunoby,NYK,points,16.5,OVER,ATL,
0.902,25.6,3.1,10,SLAM,
Moderate,solid_contributor,0.87,False,3,OK,OK,STABLE,
-0.04,0.0,-0.28,0.0,-0.32,
0.582,LEAN,PLAY,"Solid contributor, moderate blowout risk mitigated by form",
True,POWER_3L,14.8,MISS,32,
VARIANCE,"Hit line in 8/10 recent games; unlucky shooting night (4–16 FG)",False,NULL,True,NULL,
False,CONFIRM,NULL,NULL,
2026-01-02T14:23:45Z,2026-01-03T02:15:30Z,True,"Confirmed via box score; variance not governance"
```

---

## Governance-Safe Defaults

When a field is unknown or unavailable, use:

| Field | Default | Rationale |
|-------|---------|-----------|
| `rest_days` | `2` | Assume adequate rest if unknown (minimize over-penalizing) |
| `sample_size_flag` | `CAUTION` | Default to caution if <10 games |
| `usage_trend` | `UNKNOWN` | Do not guess |
| `minutes_survival_base` | `0.80` | Neutral role-player default |
| `penalty_other_pct` | `0.0` | No unaccounted adjustments |
| `learning_signal` | `False` | Only confirm intentional learning |
| `audited` | `False` | Start unverified |

---

## Immutability Rules

**NEVER UPDATE** an existing row.

**DO:**
* Create a new row if pick is re-evaluated before game
* Create a new row if new information emerges
* Add `notes` field for corrections (e.g., "Data correction: actual_value was 24.1, not 24.0")

**Examples of New Rows:**
```
pick_2026010201_giannis_pts_v1    (initial entry)
pick_2026010201_giannis_pts_v2    (updated on injury news)
pick_2026010201_giannis_pts_v3    (final result post-game)
```

---

## CSV Export Format

```csv
pick_id,slate_date,slate_id,player_name,team,stat_category,line,direction,opponent_team,prob_raw,mu,sigma,sample_size,tier_statistical,blowout_risk,player_role,minutes_survival_base,garbage_time_eligible,rest_days,rest_flag,sample_size_flag,usage_trend,penalty_blowout_pct,penalty_rest_pct,penalty_shrinkage_pct,penalty_other_pct,total_penalty_pct,prob_calibrated,tier_calibrated,recommended_action,confidence_note,actually_placed,entry_format,actual_value,outcome,minutes_played,failure_primary_cause,failure_detail,governance_flag_present,governance_flag_name,penalty_was_sufficient,suggested_penalty_increase_pct,learning_signal,learning_type,suggested_rule_change,confidence_in_suggestion,created_at,result_posted_at,audited,notes
```

---

## Access Patterns

### Query 1: Daily Performance
```sql
SELECT tier_calibrated, outcome, COUNT(*) as picks, SUM(CASE WHEN outcome='HIT' THEN 1 ELSE 0 END) as hits
FROM calibration_history
WHERE slate_date = '2026-01-02'
GROUP BY tier_calibrated, outcome
```

### Query 2: Failure Attribution
```sql
SELECT failure_primary_cause, COUNT(*) as misses, AVG(penalty_was_sufficient::int) as avg_penalty_sufficient
FROM calibration_history
WHERE outcome='MISS'
GROUP BY failure_primary_cause
ORDER BY misses DESC
```

### Query 3: Governance Learning
```sql
SELECT suggested_rule_change, confidence_in_suggestion, COUNT(*) as signal_count
FROM calibration_history
WHERE learning_signal=True AND suggested_rule_change IS NOT NULL
GROUP BY suggested_rule_change, confidence_in_suggestion
ORDER BY signal_count DESC
```

---

## Summary

**This schema:**

✅ Logs every pick immutably
✅ Captures all governance decisions
✅ Forces single-cause failure attribution
✅ Enables learning without opinions
✅ Supports rollback and versioning
✅ Never rewards hindsight bias
✅ Produces clean, queryable data

**Once locked, you can:**

1. Backfill Jan 02 manually
2. Audit governance decisions in real-time
3. Run daily performance queries
4. Suggest penalty adjustments with confidence
5. Track improvement over weeks
6. Never lose history

---

**Is this the schema you want to lock?** Or do you need fields added/removed/clarified?
