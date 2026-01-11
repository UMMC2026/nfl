# Quick Start Guide - Ollama Integration

## Run Your Daily Betting Analysis (Takes ~10 seconds)

```bash
python scripts/daily_workflow.py
```

**What it does:**
1. ✅ Loads cached pick data
2. ✅ Generates comprehensive cheatsheet
3. ✅ Extracts top picks + bet sizing
4. ✅ **Validates all picks (NEW - instant)**
5. ✅ Ready for betting!

**Output:**
- `CHEATSHEET_*.txt` - Full analysis report
- `pick_validation_*.json` - Validation results
- Console summary showing strong/lean plays

---

## Commands Quick Reference

### Daily Workflow (All-in-one)
```bash
python scripts/daily_workflow.py
```

### Just Validate Current Picks
```bash
python scripts/smart_validation.py
```

### On-Demand Ollama Analysis (Slower, More Detailed)
```bash
python ollama_spot_check.py --top 5 --model mistral
```

### Check if Ollama is Running
```bash
ollama list
```

### Check Ollama Performance
```bash
python diagnose_ollama.py
```

---

## What's New

**`smart_validation.py`** - Instant pick validation
- ✅ Validates 10 picks in 0.9 seconds
- ✅ Rule-based checks (no LLM latency)
- ✅ Saves results as JSON
- ✅ Detects invalid teams/stats

**Integrated into `daily_workflow.py`** as Step 4
- Now automatically runs after bet sizing
- Results saved alongside cheatsheet

---

## If Validation Fails

### Check 1: Do you have picks_hydrated.json?
```bash
ls picks_hydrated.json
```
If missing, run hydration first:
```bash
python hydrate_new_picks.py
```

### Check 2: Is Ollama running?
```bash
ollama ps
```
If nothing shows, start Ollama:
```bash
ollama serve
```
(in another terminal)

### Check 3: Are your picks valid?
Open `picks.json` and verify:
- Player names are correct
- Teams match NBA teams (ATL, BOS, BRK, etc.)
- Stats are real (points, rebounds, assists, etc.)

---

## File Locations

**Your daily betting picks:**
- `picks.json` - Manual line input
- `picks_hydrated.json` - Picks with stats hydrated
- `outputs/CHEATSHEET_*.txt` - Analysis report
- `outputs/pick_validation_*.json` - Validation results

**Ollama module (from last night):**
- `ollama/data_validator.py`
- `ollama/optimizer.py`
- `ollama/risk_analyst.py`
- `ollama/prompt.txt`

**Diagnostic tools:**
- `ollama_spot_check.py` - Detailed Ollama analysis (slow)
- `diagnose_ollama.py` - Check Ollama health

---

## Performance Summary

| Task | Time | Status |
|------|------|--------|
| Hydrate picks | 2-3s | Optional (cached) |
| Generate cheatsheet | 3-5s | Fast |
| Extract top picks | 1-2s | Fast |
| **Validate picks** | **0.9s** | **✅ Instant** |
| Total workflow | ~10s | Production ready |

---

## Typical Betting Day

### Morning (Before Games)
```bash
python scripts/daily_workflow.py
```
→ Prints top picks + units → Make your picks on Underdog

### During Day (If Lines Change)
```bash
python scripts/smart_validation.py
```
→ Quick validation of new picks → Update your entries

### Advanced (Detailed LLM Analysis)
```bash
python ollama_spot_check.py --top 10 --model mistral
```
→ Get detailed Ollama insights on questionable picks

---

## What's Being Validated?

Each pick is checked for:
- ✅ **Team validity** - Is it a real NBA team?
- ✅ **Stat validity** - Is it a real NBA stat?
- ✅ **Obvious errors** - Any impossible combos?
- ✅ **Caching** - Avoid re-checking same picks

**Time per pick: 0.09 seconds**

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Module not found | Run: `pip install -r requirements-base.txt` |
| Ollama timeout | Increase timeout in smart_validation.py (line 12) |
| Encoding errors | Already fixed - uses utf-8, errors='ignore' |
| No picks to validate | Create picks.json with format: `[{player, team, stat, line, mu}]` |
| Slow validation | Your rule validation is already <1s per 10 picks |

---

## Advanced: Enable Ollama Analysis

Edit `smart_validation.py` line 177:
```python
# Change this:
results = batch_validate_picks(picks, max_picks=10, use_ollama=False)

# To this:
results = batch_validate_picks(picks, max_picks=10, use_ollama=True)
```

Then run:
```bash
python scripts/smart_validation.py
```

**Note:** This will be slower (30+ seconds for 10 picks) but provides LLM analysis.

---

## Summary

✅ **You have a complete, production-ready betting analysis system.**

Run this daily:
```bash
python scripts/daily_workflow.py
```

Output will guide your Underdog entries with validated picks.

