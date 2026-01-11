# §3.1 — NFL Stat Hydration (2026-01-10)

**Clarification:**

> NFL stat hydration requires play-by-play or team-context aggregation. NBA-style APIs and assumptions do not generalize to NFL. All NFL props must be hydrated using a dedicated engine (see `hydrators/nfl_stat_hydrator.py`).

- No rolling averages or empirical probabilities are possible without this subsystem.
- Roster and schedule gates do not generate stats.
- Until implemented, NFL scoring is forbidden by design.

**Action:**
- All future NFL stat logic must be routed through the NFL_STAT_HYDRATOR interface.
- No forced probabilities or gate relaxation is permitted.

---

*This section is locked as of 2026-01-10. All changes must be auditable and approved.*
# 🔒 SPORTS BETTING RESEARCH & DEPLOYMENT — TRUTH GOVERNANCE SOP

**Version:** 1.0 | **Date:** 2026-01-05 | **Status:** LOCKED

---

## THE FIVE INVIOLABLE RULES

### ✅ RULE 1 — NO SLATE, NO SIGNAL
- If a team is **not playing today**, it is **ILLEGAL** to output.
- Enforced by: `engine/slate_gate.py::enforce_today_slate()`
- Fail mode: **Abort pipeline** (not soft warning)
- Minimum match rate: **95%** of picks must align with today's teams

### ✅ RULE 2 — ROSTER TRUTH OVERRIDES ALL
- Player → team mapping comes **from roster data ONLY**.
- If `picks.json` says Kevin Durant → BOS but roster says Kevin Durant → HOU, **roster wins**.
- Enforced by: `engine/roster_gate.py::bind_player_team()`
- Fail mode: **Override** (picks.json is not a source of truth)

### ✅ RULE 3 — VALIDATED OUTPUT IS THE ONLY SOURCE
- All views, Telegram, reports, summaries **read from:**
  ```
  outputs/validated_primary_edges.json
  ```
- **Never** read directly from `picks.json` or intermediate files.
- Enforced by: `engine/slate_roster_validator.py::load_validated_picks()`
- Fail mode: **FileNotFoundError** if validated file missing

### ✅ RULE 4 — FAIL CLOSED (NO DRIFT)
- Any mismatch > **5%** = **abort pipeline**.
- Silent failures = **prohibited**.
- All errors raise `RuntimeError` immediately.
- Enforced by: `engine/slate_gate.py::min_match_rate=0.95`
- Example: If 100 picks, 94 match today's slate → **FAIL** (94% < 95%)

### ✅ RULE 5 — MODULE EXECUTION ONLY
- All runs must use **module invocation** (from repo root):
  ```bash
  python -m menu.interactive_menu
  python -m Telegram.send
  python -m engine.tests.test_slate_gate
  ```
- **Never:**
  ```bash
  python scripts/old_script.py  # ❌ NO
  python direct_test.py         # ❌ NO
  ```

---

## DEPLOYMENT CHECKLIST

### Before Running Any Analysis:
- [ ] `.env` contains `SPORTS_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- [ ] `requirements.txt` updated (cryptography version safe, aiohttp added)
- [ ] Run `pip install -r requirements.txt` to sync env
- [ ] `data_center/rosters/` has today's roster (or mock roster for testing)
- [ ] ESPN API or data source is accessible

### Before Sending Telegram:
- [ ] `outputs/validated_primary_edges.json` exists
- [ ] File is **< 1 hour old** (checked by `utils/freshness.py::assert_fresh()`)
- [ ] Run via: `python -m Telegram.send`
- [ ] Never call `Telegram/send.py` directly

### Before Reporting Results:
- [ ] Load picks **only** from `outputs/validated_primary_edges.json`
- [ ] Verify `validated_count` > 0
- [ ] Check timestamp in file

---

## ARCHITECTURE

```
┌──────────────────────────────────────────────────────┐
│  PICKS INPUT (JSON / CLI)                            │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│  ROSTER GATE (engine/roster_gate.py)                │
│  Rule: Kevin Durant HOU (roster) > BOS (picks.json) │
│  Output: picks with corrected teams                 │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│  SLATE GATE (engine/slate_gate.py)                  │
│  Rule: All picks must match today_teams             │
│  Fail mode: min_match_rate=95% or abort             │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│  WRITE VALIDATED OUTPUT                             │
│  File: outputs/validated_primary_edges.json         │
│  Timestamp: ISO-8601                                │
│  Content: { validated_count, picks, timestamp }     │
└────────────────────┬─────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┐
        ▼            ▼            ▼            ▼
   TELEGRAM    REPORTS      RANKINGS     ANALYSIS
   (send.py)   (reporters)  (views)      (research)
   
   ALL MUST READ FROM validated_primary_edges.json
```

---

## MODULE STRUCTURE

```
engine/
├── __init__.py
├── slate_gate.py                # Team availability gate
├── roster_gate.py               # Player-to-team truth
└── slate_roster_validator.py    # Combined pipeline entry point

Telegram/
├── __init__.py
├── send.py                      # Governed sender (reads validated output)
└── transport.py                 # API client (fail loud on config missing)

utils/
├── __init__.py
├── freshness.py                 # File age validation
└── ...

outputs/
└── validated_primary_edges.json # THE SOURCE OF TRUTH (only file this directory writes)
```

---

## ERROR HANDLING PATTERNS

### ✅ GOOD: Fail Loud
```python
if not token:
    raise RuntimeError("❌ SPORTS_BOT_TOKEN not set in .env")
```

### ❌ BAD: Silent Failure
```python
token = os.getenv("SPORTS_BOT_TOKEN")  # Returns None, no error
```

### ✅ GOOD: Check Before Slate
```python
picks = bind_player_team(picks, roster_map)  # Fix teams first
picks = enforce_today_slate(picks, today_teams)  # Then validate slate
```

### ❌ BAD: Skip Validation
```python
send_telegram(picks)  # No validation, picks might be wrong
```

---

## TESTING YOUR SOP

### Quick Test: Roster Gate
```python
from engine.roster_gate import bind_player_team

roster = {"Kevin Durant": "HOU", "LeBron James": "LAL"}
picks = [{"player": "Kevin Durant", "team": "BOS", ...}]

result = bind_player_team(picks, roster)
assert result[0]["team"] == "HOU"  # ✅ Team overridden
```

### Quick Test: Slate Gate
```python
from engine.slate_gate import enforce_today_slate

picks = [
    {"player": "LeBron", "team": "LAL"},
    {"player": "Giannis", "team": "MIL"},
]
today_teams = {"LAL", "BOS"}  # Only LAL playing, not MIL

try:
    enforce_today_slate(picks, today_teams, min_match_rate=0.95)
except RuntimeError as e:
    print(f"✅ Correctly failed: {e}")
```

### Full Pipeline Test
```python
from engine.slate_roster_validator import validate_and_render
from engine.roster_gate import load_roster_map

roster = load_roster_map("data_center/rosters/nba_2024-25.json")
picks = [...]  # Your picks
today_teams = {"LAL", "BOS", "MIA"}  # Today's games

validated = validate_and_render(picks, roster, today_teams)
print(f"✅ {len(validated)} picks validated")
```

---

## WHEN THIS SOP STOPS YOU

| Scenario | Error | Fix |
|----------|-------|-----|
| Pick has team not in today_teams | `SLATE GATE FAIL` | Get today's actual teams from ESPN |
| 94% of picks match today (< 95%) | `SLATE GATE FAIL` | Remove wrong teams from picks |
| picks.json says Kevin Durant → BOS, roster says HOU | No error, team overridden | ✅ This is correct behavior |
| `validated_primary_edges.json` missing | `FileNotFoundError` | Run `validate_and_render()` first |
| Telegram token not set | `RuntimeError` | Add `SPORTS_BOT_TOKEN` to `.env` |
| Pick file > 1 hour old | `assert_fresh()` fails | Re-run validation pipeline |

---

## FUTURE ENHANCEMENTS (Optional)

- [ ] Add "Today Slate %" meter to CLI
- [ ] Auto-drop instead of hard abort (with audit log)
- [ ] Unit tests for each gate (test_slate_gate.py, test_roster_gate.py)
- [ ] Slack integration (same pattern as Telegram)
- [ ] Dashboard view of validated picks (with timestamp)

---

## QUICK REFERENCE

| What | Where | Command |
|------|-------|---------|
| Run analysis | `menu.py` | `python -m menu.interactive_menu` |
| Send Telegram | `Telegram/send.py` | `python -m Telegram.send` |
| Validate picks | `engine/slate_roster_validator.py` | Import & call `validate_and_render()` |
| Check roster | `data_center/rosters/` | Load JSON, confirm player → team |
| Check freshness | `utils/freshness.py` | `assert_fresh("outputs/validated_primary_edges.json")` |

---

## WHO CAN CHANGE THIS SOP?

**Only:** You, after explicit review.
**Review required for:**
- Changing `min_match_rate` (currently 95%)
- Adding new gates (before/after slate or roster)
- Changing `VALIDATED_OUTPUT` location
- Adding bypass logic

**No changes to:**
- Rule 1–5 (core governance)
- Module execution pattern
- Fail-closed behavior

---

**Last Updated:** 2026-01-05  
**Next Review:** 2026-02-05 (or after major regression)
