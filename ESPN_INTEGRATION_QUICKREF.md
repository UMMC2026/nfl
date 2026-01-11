# ESPN Integration — Quick Reference

## TL;DR: 3-Step Setup

### Step 1: Get ESPN Game ID
```
ESPN URL: https://www.espn.com/nba/game?gameId=401547819
Extract:  401547819
```

### Step 2: Update picks.json
```json
{
  "game_id": "401547819",
  "player_name": "LeBron James",
  "stat": "points",
  "direction": "OVER",
  "line": 25.5,
  ...
}
```

### Step 3: Run Pipeline
```bash
# After game is FINAL on ESPN:
python load_game_results.py
python generate_resolved_ledger.py
```

---

## What Gets Fetched

| Stat | Source | Example |
|------|--------|---------|
| points | ESPN box score | 28.0 |
| rebounds | ESPN box score | 8.0 |
| assists | ESPN box score | 7.0 |
| 3pm | ESPN box score | 2.0 |
| steals | ESPN box score | 1.0 |
| blocks | ESPN box score | 0.0 |
| turnovers | ESPN box score | 3.0 |
| **pra** | **computed** | **43.0** |

---

## Supported Games

- ✅ NBA (full support)
- ⚠️ NFL (skeleton, needs extension)
- ⚠️ CFB (skeleton, needs extension)

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| 0 games loaded | picks.json missing game_ids | Add ESPN numeric IDs |
| Game not found | Invalid game_id format | Use numeric ESPN ID only |
| Game pending | Not finalized yet | Wait, then retry |
| Player name mismatch | ESPN spelling differs | Check ESPN box score, update picks.json |

---

## Files Modified

- ✅ **load_game_results.py** (117 → 217 lines)
  - Added ESPN API integration
  - Stat extraction + PRA computation
  - Error handling for unfinalized games

- ✅ **ops/ESPN_INTEGRATION_GUIDE.md** (NEW)
  - Comprehensive integration docs

---

## Status

```
ESPN Integration:  ✅ COMPLETE
Testing:          ✅ READY
Production Use:   ✅ READY
```
