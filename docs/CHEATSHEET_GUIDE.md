# CONSOLIDATED CHEAT SHEET — User Guide
**Clear OVER/UNDER Probability Reports**

## Overview
The Consolidated Cheat Sheet generates clean, easy-to-read reports that clearly show:
- **OVER probabilities** for Higher plays
- **UNDER probabilities** for Lower plays  
- **Clear separation** between OVERS and UNDERS
- **Tier grouping** (SLAM, STRONG, LEAN)
- **Edge calculations** vs the line

---

## Quick Start

### Generate Cheat Sheet from Latest Analysis
```bash
# NBA
python scripts/generate_consolidated_cheatsheet.py --sport nba

# Tennis
python scripts/generate_consolidated_cheatsheet.py --sport tennis

# NFL
python scripts/generate_consolidated_cheatsheet.py --sport nfl

# CBB
python scripts/generate_consolidated_cheatsheet.py --sport cbb
```

### Generate from Specific File
```bash
python scripts/generate_consolidated_cheatsheet.py --input "path/to/analysis.json"
```

### Quick Reference Only (Compact View)
```bash
python scripts/generate_consolidated_cheatsheet.py --sport nba --quick
```

---

## VS Code Tasks

Access via **Ctrl+Shift+P** → "Tasks: Run Task":

1. **Cheat Sheet: NBA (Full Report)** — Complete NBA cheat sheet
2. **Cheat Sheet: NBA (Quick Reference)** — Compact top plays only
3. **Cheat Sheet: Tennis (Full Report)** — Tennis full report
4. **Cheat Sheet: CBB (Full Report)** — College basketball
5. **Cheat Sheet: NFL (Full Report)** — NFL cheat sheet

---

## Report Format

### Full Report Structure
```
════════════════════════════════════════════════════════════════
  NBA CONSOLIDATED CHEAT SHEET — 2026-01-24 12:38
════════════════════════════════════════════════════════════════

📊 TOTAL PLAYS: 4
   OVERS:  2
   UNDERS: 2

   📊 LEAN: 4

────────────────────────────────────────────────────────────────

📊 LEAN PLAYS (4)
────────────────────────────────────────────────────────────────

  📈 OVERS:
  Player                    Stat         Line     OVER %     UNDER %    Edge
  ─────────────────────────────────────────────────────────────────────────
  Pascal Siakam             REB+AST      10.5     68.0       32.0       +18.0%
  Jaylen Brown              POINTS       24.5     67.8       32.2       +17.8%

  📉 UNDERS:
  Player                    Stat         Line     UNDER %    OVER %     Edge
  ─────────────────────────────────────────────────────────────────────────
  Giannis Antetokounmpo     PRA          44.5     68.0       32.0       +18.0%
  Donovan Mitchell          PRA          40.5     65.7       34.3       +15.7%

────────────────────────────────────────────────────────────────

LEGEND:
  🔥 SLAM:   ≥80% confidence | Highest conviction plays
  ✅ STRONG: 65-79% confidence | High conviction plays
  📊 LEAN:   55-64% confidence | Moderate conviction plays

  OVER %:  Probability of going OVER the line
  UNDER %: Probability of going UNDER the line
  Edge:    Statistical advantage vs line
```

### Key Features

#### 1. Clear Probability Display
- **OVERS section**: Shows `OVER %` first (primary probability), `UNDER %` second
- **UNDERS section**: Shows `UNDER %` first (primary probability), `OVER %` second
- **No confusion**: The primary probability is always listed first

#### 2. Tier Grouping
Reports are organized by tier (highest conviction first):
- 🔥 **SLAM**: 80%+ confidence — Highest conviction
- ✅ **STRONG**: 65-79% confidence — High conviction  
- 📊 **LEAN**: 55-64% confidence — Moderate conviction

#### 3. Edge Calculation
Shows statistical advantage:
- `+18.0%` = 18% above break-even (50%)
- Calculated as: `probability - 50%`

---

## Quick Reference Format

Ultra-compact view for quick scanning:

```
╔════════════════════════════════════════════════════════════════╗
║  NBA QUICK REFERENCE — 01/24 12:38PM                           ║
╠════════════════════════════════════════════════════════════════╣
║  📈 TOP OVERS:                                                  ║
║  1. Pascal Siakam         REB+AST  O10.5   68% 📊              ║
║  2. Jaylen Brown          POINTS   O24.5   68% 📊              ║
║                                                                ║
║  📉 TOP UNDERS:                                                 ║
║  1. Giannis Antetokounmpo PRA      U44.5   68% 📊              ║
║  2. Donovan Mitchell      PRA      U40.5   66% 📊              ║
╚════════════════════════════════════════════════════════════════╝
```

Shows:
- Top 5 OVERS
- Top 5 UNDERS
- Probability + Tier icon
- Compact format for mobile/quick view

---

## Command Line Options

### Basic Options
```bash
--sport {nba,tennis,cbb,nfl}    # Sport to generate for (default: nba)
--input PATH                     # Input JSON file path
--output PATH                    # Output file path (default: auto-generated)
--min-tier {SLAM,STRONG,LEAN}   # Minimum tier to include (default: LEAN)
--quick                          # Generate quick reference only
```

### Examples
```bash
# NBA full report, STRONG tier and above only
python scripts/generate_consolidated_cheatsheet.py --sport nba --min-tier STRONG

# Tennis quick reference
python scripts/generate_consolidated_cheatsheet.py --sport tennis --quick

# Custom input and output
python scripts/generate_consolidated_cheatsheet.py \
  --input "archives/nba/2026-01/analysis.json" \
  --output "my_cheatsheet.txt"
```

---

## Integration with Daily Pipelines

### Auto-Generate After Analysis

Add to your daily pipeline scripts:

**NBA** (`daily_pipeline.py`):
```python
# After analysis completes
from scripts.generate_consolidated_cheatsheet import ConsolidatedCheatSheet
import json

with open("outputs/latest_analysis.json", "r") as f:
    data = json.load(f)

sheet = ConsolidatedCheatSheet(data["results"], sport="NBA")
report = sheet.generate_text_report(Path("outputs/NBA_CHEATSHEET_LATEST.txt"))
print(report)
```

**Tennis** (`tennis/run_daily.py`):
```python
from scripts.generate_consolidated_cheatsheet import ConsolidatedCheatSheet

sheet = ConsolidatedCheatSheet(tennis_edges, sport="Tennis")
sheet.generate_text_report(Path("outputs/TENNIS_CHEATSHEET_LATEST.txt"))
```

---

## Supported Input Formats

The cheat sheet generator automatically detects and converts:

### 1. Risk-First Analysis Format
```json
{
  "total_props": 35,
  "results": [
    {
      "player": "Pascal Siakam",
      "stat": "reb+ast",
      "line": 10.5,
      "direction": "higher",
      "effective_confidence": 68.0,
      "decision": "LEAN"
    }
  ]
}
```

### 2. Edge Format
```json
{
  "edges": [
    {
      "entity": "Pascal Siakam",
      "market": "REB+AST",
      "line": 10.5,
      "direction": "Higher",
      "probability": 68.0,
      "tier": "LEAN"
    }
  ]
}
```

### 3. Direct Edge List
```json
[
  {
    "entity": "Pascal Siakam",
    "market": "REB+AST",
    "line": 10.5,
    "direction": "Higher",
    "probability": 68.0,
    "tier": "LEAN"
  }
]
```

---

## Reading the Cheat Sheet

### For OVERS
```
Pascal Siakam    REB+AST    10.5    68.0    32.0    +18.0%
                                    ^^^^    ^^^^
                                    OVER    UNDER
```
- **68.0%** = Probability of going OVER 10.5
- **32.0%** = Probability of going UNDER 10.5
- **+18.0%** = 18% edge above break-even

**Interpretation**: Pascal has a 68% chance to get MORE than 10.5 Reb+Ast

### For UNDERS
```
Giannis Antetokounmpo    PRA    44.5    68.0    32.0    +18.0%
                                        ^^^^    ^^^^
                                        UNDER   OVER
```
- **68.0%** = Probability of going UNDER 44.5
- **32.0%** = Probability of going OVER 44.5  
- **+18.0%** = 18% edge above break-even

**Interpretation**: Giannis has a 68% chance to get LESS than 44.5 PRA

---

## Output Locations

### Auto-Generated Files
```
outputs/
  NBA_CHEATSHEET_YYYYMMDD_HHMM.txt      # Full NBA report
  TENNIS_CHEATSHEET_YYYYMMDD_HHMM.txt   # Full Tennis report
  CBB_CHEATSHEET_YYYYMMDD_HHMM.txt      # Full CBB report
  NFL_CHEATSHEET_YYYYMMDD_HHMM.txt      # Full NFL report
```

### Latest Symlinks (Optional)
You can create shortcuts to latest reports:
```bash
# Windows PowerShell
New-Item -ItemType SymbolicLink -Path "outputs\NBA_CHEATSHEET_LATEST.txt" -Target "outputs\NBA_CHEATSHEET_20260124_1238.txt"
```

---

## Troubleshooting

### "No edges found"
- Run analysis first: `[2] ANALYZE SLATE` in menu
- Or use `--input` to specify a file
- Check that analysis file has LEAN/PLAY/STRONG picks

### "0 plays filtered"
- Adjust `--min-tier`: Try `--min-tier LEAN` to include more plays
- Check that analysis produced qualifying picks (not all BLOCKED/NO_PLAY)

### Wrong probabilities showing
- Check `direction` field in source data
- Verify conversion is handling "higher"/"lower" correctly
- For UNDERS, probability should be the confidence of going UNDER

---

## Advanced Usage

### Custom Filtering
```python
from scripts.generate_consolidated_cheatsheet import ConsolidatedCheatSheet

# Load edges
edges = load_edges()

# Create sheet
sheet = ConsolidatedCheatSheet(edges, sport="NBA")

# Filter to specific stats only
pts_edges = [e for e in sheet.edges if e["market"] == "POINTS"]
sheet.edges = pts_edges

# Generate report
report = sheet.generate_text_report()
```

### Batch Generation
```python
# Generate cheat sheets for all sports
for sport in ["nba", "tennis", "cbb", "nfl"]:
    edges = load_latest_edges(sport)
    if edges:
        sheet = ConsolidatedCheatSheet(edges, sport=sport)
        output_path = Path(f"outputs/{sport.upper()}_CHEATSHEET_LATEST.txt")
        sheet.generate_text_report(output_path)
```

---

## Best Practices

1. **Generate after every analysis run** — Always have fresh cheat sheet
2. **Use tier filtering** — Focus on STRONG+ for high-conviction plays
3. **Print quick reference** — Easy mobile access
4. **Archive old cheat sheets** — Track performance over time
5. **Compare OVER/UNDER balance** — Watch for directional bias

---

**Generated**: 2026-01-24  
**Version**: 1.0  
**File**: `scripts/generate_consolidated_cheatsheet.py`
