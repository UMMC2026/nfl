# Slate Menu - Quick Start Guide

## Interactive Menu System for PrizePicks & Underdog

### Launch the Menu
```bash
python slate_menu.py menu
```

## Usage Workflows

### 1. Interactive Mode (Recommended)
```bash
python slate_menu.py menu
```

**Menu Options:**
- **Option 1**: Paste Underdog slate directly from terminal
- **Option 2**: Paste PrizePicks slate from chat
- **Option 3**: Load from JSON file
- **Option 4**: Analyze all loaded props
- **Option 5**: View analysis results (ranked by probability)
- **Option 6**: Build optimal entries (2-8 legs, power/flex)
- **Option 7**: Save results to JSON
- **Option 8**: Clear all props and start fresh
- **Option q**: Quit

### 2. Quick Analysis (Command Line)

**Underdog only:**
```bash
python slate_menu.py quick-underdog mil_atl_jan19_props.json
```

**PrizePicks only:**
```bash
python slate_menu.py quick-prizepicks my_prizepicks_slate.json
```

**Both sources combined:**
```bash
python slate_menu.py combined --underdog-file underdog.json --prizepicks-file prizepicks.json
```

## Data Input Formats

### Underdog Format (from your paste)
```
Ryan Rollins
MIL - G
Ryan Rollins
@ ATL Mon 12:10pm

5.5
Rebounds
More
```

### PrizePicks Format
```
LeBron James OVER 25.5 Points (LAL)
Anthony Davis UNDER 12.5 Rebounds (LAL)
Stephen Curry OVER 28.5 PRA (GSW)
```

### JSON Format (Both)
```json
[
  {
    "player": "Giannis Antetokounmpo",
    "team": "MIL",
    "stat": "points",
    "line": 30.5,
    "direction": "lower"
  }
]
```

## Example Workflow

### Step 1: Launch Menu
```bash
python slate_menu.py menu
```

### Step 2: Add Underdog Props
- Select option `1`
- Paste your Underdog slate
- Press Ctrl+Z (Windows) or Ctrl+D (Unix) when done

### Step 3: Add PrizePicks Props (Optional)
- Select option `2`
- Paste your PrizePicks slate
- Press Ctrl+Z/Ctrl+D when done

### Step 4: Analyze
- Select option `4`
- System hydrates recent stats from NBA API
- Calculates probabilities for all props

### Step 5: View Results
- Select option `5`
- See ranked props with confidence levels
- Review recent performance data

### Step 6: Build Entries
- Select option `6`
- Choose format (power/flex)
- Choose legs (2-8)
- Get optimal combinations with EV calculations

### Step 7: Save
- Select option `7`
- Results saved to `outputs/` folder

## Advanced Features

### Cross-Platform Analysis
The system automatically:
- Identifies source (PrizePicks vs Underdog)
- Normalizes stat names
- Combines props from both platforms
- Finds optimal cross-platform entries

### Smart Entry Building
- Enforces min 2 teams per entry
- Prevents duplicate player props
- Calculates true EV using probability × payout
- Ranks by expected value

### Data Validation
- Hydrates recent game stats (last 10 games)
- Uses Normal distribution for probability
- Flags unsupported stats
- Defaults to 50% for missing data

## Output Files

All results saved to `outputs/` directory:
- `combined_analysis_YYYYMMDD_HHMMSS.json` - Full analysis results
- Includes probabilities, recent values, source platform

## Tips

1. **For best results**: Analyze props from both platforms to find the best edges
2. **High confidence**: Focus on ≥60% probability picks
3. **Entry building**: Use 3-leg power entries for best risk/reward
4. **Save frequently**: Results persist between menu sessions
5. **Roster gate**: For production, add `--roster-file` to validate active players

## Troubleshooting

**"No props parsed"**: Check paste format matches examples above

**"Missing data"**: Some players may not have recent games; system defaults to 50%

**"Unsupported stat"**: Some exotic stats (like 2pt_att) aren't in NBA API; defaults to 50%

## Next Steps

Once you're comfortable with the menu:
- Integrate with Telegram bot for automated alerts
- Add bankroll management
- Set up scheduled analysis for daily slates
- Build tracking for verified results
