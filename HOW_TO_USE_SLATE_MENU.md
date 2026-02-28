# 🎯 HOW TO USE: Slate Menu with Your Underdog Paste

## ✅ IT'S WORKING!

The parser successfully extracted **12 props** from your paste:

```
✓ Jalen Johnson Under 7.5 Assists - 93.92% (STRONG)
✓ Nickeil Alexander-Walker Under 19.5 Points - 93.34% (STRONG)  
✓ Jalen Johnson Under 38.5 PRA - 74.61% (STRONG)
✓ Jalen Johnson Under 21.5 Points - 72.96% (STRONG)
```

---

## 🚀 TWO WAYS TO USE

### Option 1: Direct Launcher (Recommended)
```bash
python launch_slate_menu.py
```

**This bypasses the old menu completely.**

### Option 2: Quick Analysis (One Command)
```bash
python slate_menu.py quick-underdog test_underdog_parse.json
```

---

## 📋 STEP-BY-STEP WORKFLOW

### Method A: Interactive Menu

**1. Launch:**
```bash
python launch_slate_menu.py
```

**2. When menu appears, select option `1`** (Paste Underdog slate)

**3. Copy your Underdog slate** from the website (exactly as you pasted it)

**4. Paste into terminal** and press:
   - **Windows**: Ctrl+Z then Enter
   - **Mac/Linux**: Ctrl+D

**5. Select option `4`** - Analyze all props

**6. Select option `5`** - View ranked results

**7. Select option `6`** - Build optimal entries
   - Choose "power" or "flex"
   - Choose 2-8 legs
   - Get top EV combinations

**8. Select option `7`** - Save results (auto-saves to outputs/)

---

### Method B: Quick File Analysis

**1. Your slate is already parsed:**
```bash
test_underdog_parse.json  # ← Generated from your paste
```

**2. Run analysis:**
```bash
python slate_menu.py quick-underdog test_underdog_parse.json
```

**3. Results appear instantly** - no menu needed

---

## 🎲 TODAY'S RESULTS (From Your Paste)

### Top Picks (60%+):
1. **Jalen Johnson U7.5 Assists** - 93.92% 🔥
2. **N. Alexander-Walker U19.5 Pts** - 93.34% 🔥
3. **Jalen Johnson U38.5 PRA** - 74.61% ⭐
4. **Jalen Johnson U21.5 Points** - 72.96% ⭐

### Avoid (<50%):
- Ryan Rollins O5.5 Reb (11.78%)
- Kyle Kuzma U9.5 Pts (12.57%)
- Bobby Portis props (23-28%)
- All Giannis props (26-40%)

---

## 📊 NEXT STEPS

### Build a 3-Leg Parlay:

**Manual command:**
```bash
python -c "from slate_menu import SlateManager; m = SlateManager(); m.load_from_file('test_underdog_parse.json', 'underdog'); m.analyze_all(); entries = m.build_optimal_entries('power', 3, 10); m.display_analysis()"
```

**Or use the menu:**
```bash
python launch_slate_menu.py
# Option 3 → Load file → test_underdog_parse.json
# Option 4 → Analyze
# Option 6 → Build entries (power, 3 legs)
```

---

## 💡 ADDING PRIZEPICKS

Want to compare with PrizePicks props?

**1. In menu, select option `2`** (Paste PrizePicks)

**2. Paste in this format:**
```
LeBron James OVER 25.5 Points (LAL)
Anthony Davis UNDER 12.5 Rebounds (LAL)
```

**3. Both platforms analyzed together!**

---

## 🔧 TROUBLESHOOTING

### "Old menu keeps appearing"
Use the launcher:
```bash
python launch_slate_menu.py
```

### "Parser didn't find all props"
The parser looks for this pattern:
```
TEAM - Position
(Line value as number)
(Stat name)
(More/Less)
```

Your paste worked perfectly - got all 12 props!

### "Want to re-analyze same slate"
Your parsed props are saved in:
```
test_underdog_parse.json
```

Just run:
```bash
python slate_menu.py quick-underdog test_underdog_parse.json
```

---

## 📁 FILES FOR YOU

| File | Purpose |
|------|---------|
| `launch_slate_menu.py` | Direct launcher (use this!) |
| `test_underdog_parse.json` | Your parsed props |
| `slate_menu.py` | Main analysis engine |
| `outputs/` | Where results are saved |

---

## ✅ SUMMARY

**Your workflow is now:**

1. Copy Underdog slate from website
2. Run: `python launch_slate_menu.py`
3. Paste slate (Ctrl+Z / Ctrl+D when done)
4. Get instant analysis with probabilities
5. Build optimal entries automatically
6. Save and track results

**The parser works with your exact paste format!** 🎉
