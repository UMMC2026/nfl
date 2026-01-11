# Quick Start: Manual CSV Reconciliation

## 1️⃣ EDIT CSV (5 minutes)

Open `data/reconciliation_results.csv` and add results as games complete:

```csv
date,player,team,stat,line,direction,tier,result,actual_value,notes
2025-12-31,OG Anunoby,NYK,points,16.5,higher,SLAM,HIT,18.5,Played 31 min
2025-12-31,Jamal Shead,TOR,points,7.5,higher,SLAM,MISS,6.2,Inj report
2026-01-01,Giannis,MIL,points,27.5,higher,SLAM,PUSH,27.5,Line exact
```

**Rules:**
- `date`: YYYY-MM-DD (game date, not pick date)
- `player`: Exact spelling from picks.json
- `stat`: Exact stat (e.g., "points", "assists", "pts+reb+ast")
- `result`: HIT / MISS / PUSH (case-sensitive)
- `actual_value`: Player's actual stat value (numeric)

---

## 2️⃣ GENERATE CHEATSHEET (1 command)

```bash
python -m ufa.daily_pipeline
```

Output will show:
```
✅ Loaded 156 picks from picks_hydrated.json
✅ Processed 156 picks through calibration pipeline

============================================================
⚙️  DATA STATUS
============================================================
  Resolved picks: 3
  Pending picks: 153
  Win rate: 2/3 (67%)
  ROI: +1.0 units
  Last reconciliation: 2026-01-01 20:04 UTC
============================================================
```

---

## 3️⃣ CHECK METRICS (In Cheatsheet Output)

Look for:
```
📈 YESTERDAY'S PERFORMANCE (2025-12-31)
==================================================
  Status: 3 resolved | 43 pending
  Resolved Record: 2-1 (67%)
  SLAM Plays: 2/2 (100%)
  ROI (resolved): +1.0 units
```

**What this means:**
- 3 picks have been graded (HIT/MISS/PUSH)
- 43 picks still pending (games not done or not yet graded)
- Of graded picks: 2 wins, 1 loss = 67% win rate
- All 2 SLAM picks graded hit (100%)
- ROI: +1 unit (2 hits at +1 each, 1 miss at -1)

---

## 4️⃣ TROUBLESHOOTING

**Q: Nothing changed in cheatsheet after adding to CSV**
- Verify CSV file is saved (Ctrl+S)
- Check date format: YYYY-MM-DD
- Check player name spelling exactly matches picks.json
- Verify result is HIT/MISS/PUSH (uppercase)

**Q: Error "Invalid result: ..."**
- Result must be HIT, MISS, or PUSH
- Must be uppercase
- No typos

**Q: Error "Invalid date format"**
- Must be YYYY-MM-DD format
- Example: 2025-12-31 (not 12/31/2025)

**Q: Error "No pick found for ..."**
- Player name or stat spelling doesn't match picks.json
- Check exact spelling (case-sensitive)
- Make sure stat is singular (e.g., "points" not "Points")

---

## 5️⃣ DAILY WORKFLOW

**Each morning:**
1. Open `data/reconciliation_results.csv`
2. Add yesterday's game results from ESPN/Underdog
3. Run `python -m ufa.daily_pipeline`
4. View cheatsheet in `outputs/`
5. Check DATA STATUS telemetry
6. Verify metrics are correct

**Each evening:**
1. Generate fresh picks for next day
2. Run pipeline again
3. Send Telegram signals

---

## CSV EXAMPLE (Full Row)

```csv
date,player,team,stat,line,direction,tier,result,actual_value,notes
2025-12-31,OG Anunoby,NYK,points,16.5,higher,SLAM,HIT,18.5,Played 31 min vs TOR
2025-12-31,Giannis Antetokounmpo,MIL,pts+reb+ast,42.5,higher,STRONG,MISS,41.2,Off night
2025-12-31,Luka Doncic,DAL,points,27.5,higher,LEAN,PUSH,27.5,Exact line hit
```

---

## NEXT PHASE

After 7-14 days of clean manual reconciliation:
- **Phase 3 Decision:** Automate with ESPN API or Telegram reactions
- **No changes needed:** Reconciliation loader will work with any input

For now: Keep using CSV. Build confidence. Document hit rates.

---

**Questions?** Check RECONCILIATION_IMPLEMENTATION.md for full technical details.
