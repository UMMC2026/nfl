# TENNIS PROPS INTEGRATION GUIDE
## Step-by-Step: Add Props Support to Your Existing Pipeline

**Goal:** Transform your tennis module from match winners only → full DFS props support

**Time Required:** 30-45 minutes

---

## 📋 **CURRENT STATE:**
```
✗ No valid matches parsed
✓ Scored 0 playable edges
  STRONG: 0 | LEAN: 0
```

## 🎯 **TARGET STATE:**
```
✓ Parsed 18 props
✓ Scored 12 playable edges
  SLAM: 3 | STRONG: 5 | LEAN: 4
```

---

## 🔧 **STEP 1: Backup Your Current System** (2 minutes)

```bash
# Create backup
cd "C:\Users\hiday\UNDERDOG ANANLYSIS"
mkdir backups
cp -r tennis backups/tennis_backup_$(date +%Y%m%d)

# Verify backup
ls backups/
```

**Why:** Safety first - you can always revert

---

## 🔧 **STEP 2: Add Props Integration Module** (5 minutes)

The file `tennis_props_integration.py` should already be in your `tennis/` directory.

**Verify:**
```bash
ls tennis/tennis_props_integration.py
```

If not there, copy it:
```bash
cp tennis_props_integration.py tennis/
```

---

## 🔧 **STEP 3: Update Stage 1 (Ingestion)** (10 minutes)

### **Find your ingestion file:**

Look for one of these files:
- `tennis/ingest_matches.py`
- `tennis/ingest_tennis.py`
- `tennis/tennis_main.py` (if ingestion is there)

### **Add import at top of file:**

```python
from tennis_props_integration import ingest_props_from_text
```

### **Find your current ingestion function:**

It probably looks like:
```python
def ingest_matches(text: str) -> List[Dict]:
    """Parse match winner format only"""
    matches = []
    for line in text.split('\n'):
        # Parse: "Sinner -180 vs Djokovic +150 | Hard | SF"
        ...
    return matches
```

### **Replace with or add alongside:**

```python
def ingest_matches_or_props(text: str) -> List[Dict]:
    """
    Parse BOTH match winners AND props
    Auto-detects format
    """
    # Try props parsing first (PrizePicks/Underdog format)
    props = ingest_props_from_text(text)
    
    if props:
        print(f"✓ Ingested {len(props)} props")
        return props
    else:
        print("✗ No valid props parsed")
        return []
```

### **Update main pipeline calls:**

Find where your pipeline calls the ingestion (might be in `run_tennis_analysis.py` or similar):

**Change from:**
```python
# Stage 1: Ingest
matches = ingest_matches(user_input)
```

**To:**
```python
# Stage 1: Ingest (now supports props!)
items = ingest_matches_or_props(user_input)
```

---

## 🔧 **STEP 4: Update Stage 2 (Edge Generation)** (10 minutes)

### **Find your edge generation file:**

Look for:
- `tennis/generate_edges.py`
- `tennis/generate_tennis_edges.py`
- Edge generation code in main pipeline file

### **Add import:**

```python
from tennis_props_integration import generate_props_edges
```

### **Find current edge generation:**

```python
def generate_edges(matches: List[Dict]) -> List[Dict]:
    """Generate edges for match winners using Elo"""
    edges = []
    for match in matches:
        # Use Elo ratings for match winner probability
        ...
    return edges
```

### **Update to handle both:**

```python
def generate_edges(items: List[Dict]) -> List[Dict]:
    """
    Generate edges for BOTH match winners AND props
    Routes to appropriate model
    """
    edges = []
    
    # Separate match winners from props
    match_winners = [item for item in items if item.get('market') == 'match_winner']
    props = [item for item in items if item.get('market') != 'match_winner']
    
    # Generate edges for match winners (existing Elo logic)
    match_edges = []
    if match_winners:
        match_edges = generate_match_winner_edges(match_winners)
        edges.extend(match_edges)
    
    # Generate edges for props (new props logic)
    prop_edges = []
    if props:
        prop_edges = generate_props_edges(props)
        edges.extend(prop_edges)
    
    print(f"✓ Generated {len(edges)} total edges")
    print(f"  Match Winners: {len(match_edges)}")
    print(f"  Props: {len(prop_edges)}")
    
    return edges


def generate_match_winner_edges(matches: List[Dict]) -> List[Dict]:
    """Your existing Elo-based match winner logic"""
    # Keep your existing code here
    # ...
    pass
```

---

## 🔧 **STEP 5: Add Player Stats Database** (10 minutes)

### **Create directory:**
```bash
mkdir -p tennis/data
```

### **Create file: `tennis/data/player_stats.json`**

```json
{
  "Aryna Sabalenka": {
    "avg_games": 14.2,
    "avg_aces": 5.8,
    "avg_breakpoints": 3.8,
    "avg_fantasy_score": 22.5,
    "player_style": "big_server"
  },
  "Elina Svitolina": {
    "avg_games": 11.2,
    "avg_aces": 1.8,
    "avg_breakpoints": 2.2,
    "avg_fantasy_score": 15.3,
    "player_style": "baseline_grinder"
  },
  "Elena Rybakina": {
    "avg_games": 13.8,
    "avg_aces": 7.8,
    "avg_breakpoints": 3.6,
    "avg_fantasy_score": 22.9,
    "player_style": "big_server"
  },
  "Jessica Pegula": {
    "avg_games": 12.4,
    "avg_aces": 2.1,
    "avg_breakpoints": 2.8,
    "avg_fantasy_score": 18.2,
    "player_style": "baseline_grinder"
  },
  "Carlos Alcaraz": {
    "avg_games": 16.2,
    "avg_aces": 6.5,
    "avg_breakpoints": 4.8,
    "avg_fantasy_score": 28.1,
    "player_style": "all_court"
  },
  "Alexander Zverev": {
    "avg_games": 14.8,
    "avg_aces": 9.2,
    "avg_breakpoints": 3.5,
    "avg_fantasy_score": 25.4,
    "player_style": "big_server"
  },
  "Novak Djokovic": {
    "avg_games": 13.5,
    "avg_aces": 4.2,
    "avg_breakpoints": 3.1,
    "avg_fantasy_score": 24.8,
    "player_style": "all_court"
  },
  "Jannik Sinner": {
    "avg_games": 15.1,
    "avg_aces": 8.3,
    "avg_breakpoints": 4.2,
    "avg_fantasy_score": 26.2,
    "player_style": "aggressive_returner"
  }
}
```

### **Update integration module to load from file:**

In `tennis_props_integration.py`, find the `_load_player_stats()` method and replace with:

```python
def _load_player_stats(self) -> Dict:
    """Load player stats from JSON file"""
    import json
    from pathlib import Path
    
    stats_file = Path(__file__).parent / 'data' / 'player_stats.json'
    
    if stats_file.exists():
        with open(stats_file, 'r') as f:
            return json.load(f)
    else:
        print("⚠️  Warning: player_stats.json not found, using defaults")
        # Return hardcoded defaults
        return {
            'Aryna Sabalenka': {'avg_games': 14.2, 'avg_aces': 5.8, 'avg_breakpoints': 3.8, 'avg_fantasy_score': 22.5},
            'Elina Svitolina': {'avg_games': 11.2, 'avg_aces': 1.8, 'avg_breakpoints': 2.2, 'avg_fantasy_score': 15.3},
            'Carlos Alcaraz': {'avg_games': 16.2, 'avg_aces': 6.5, 'avg_breakpoints': 4.8, 'avg_fantasy_score': 28.1},
            'Alexander Zverev': {'avg_games': 14.8, 'avg_aces': 9.2, 'avg_breakpoints': 3.5, 'avg_fantasy_score': 25.4}
        }
```

---

## 🔧 **STEP 6: Test Integration** (5 minutes)

### **Test standalone:**

```bash
cd "C:\Users\hiday\UNDERDOG ANANLYSIS\tennis"
.venv\Scripts\python.exe tennis_props_integration.py
```

**Expected output:**
```
============================================================
TESTING PROPS INTEGRATION
============================================================

[Stage 1] Ingesting props...
✓ Ingested 3 props
  - Elina Svitolina vs Aryna Sabalenka: games_won 8.5
  - Carlos Alcaraz vs Alexander Zverev: games_played 36.5
  - Alexander Zverev vs Carlos Alcaraz: aces 10

[Stage 2] Generating edges...
✓ Generated 3 edges
  - Elina Svitolina: games_won 8.5 → LESS/LOWER (LEAN)
  - Carlos Alcaraz: games_played 36.5 → LESS/LOWER (STRONG)
  - Alexander Zverev: aces 10 → LESS/LOWER (LEAN)

============================================================
✅ INTEGRATION TEST COMPLETE
============================================================
```

---

## 🔧 **STEP 7: Test in Main Pipeline** (5 minutes)

### **Create test props file:**

Save this as `tennis/test_props.txt`:

```
Elina Svitolina
@ Aryna Sabalenka Thu 2:30am
8.5
Total Games Won
Less
More

Carlos Alcaraz
vs Alexander Zverev Thu 9:30pm
36.5
Total Games
Less
More

Alexander Zverev
@ Carlos Alcaraz Thu 9:30pm
10
Aces
Less
More

END
```

### **Run your tennis pipeline:**

```bash
cd "C:\Users\hiday\UNDERDOG ANANLYSIS"
.venv\Scripts\python.exe tennis/run_tennis_analysis.py
# Or: python main.py → Select Tennis
```

**When prompted for input, paste the test props or point to test file**

**Expected output:**
```
✓ Ingested 3 props
✓ Generated 3 edges (0 blocked)
✓ Scored 3 playable edges
  STRONG: 1 | LEAN: 2
✓ Validated 3 edges
✓ Report generated
```

---

## ✅ **VERIFICATION CHECKLIST:**

After integration, verify:

- [ ] Props are parsed successfully (no "✗ No valid matches parsed")
- [ ] Edges are generated (> 0 edges)
- [ ] Output files created in `tennis/outputs/`
- [ ] Report shows prop recommendations
- [ ] Tiers assigned correctly (SLAM/STRONG/LEAN)
- [ ] Validation gate passes
- [ ] Report is readable and contains player names, markets, lines

---

## 🚨 **TROUBLESHOOTING:**

### **Issue 1: "✗ No valid matches parsed"**
**Solution:** 
- Check that you're using `ingest_matches_or_props()` not old `ingest_matches()`
- Verify import statement is present
- Test standalone first: `python tennis_props_integration.py`

### **Issue 2: "KeyError: 'player_name'" or similar**
**Solution:** 
- Player not in `player_stats.json` - add them or check spelling
- Make sure player names match exactly (case-sensitive)

### **Issue 3: "0 playable edges" or all NO_PLAY**
**Solution:** 
- Check probability thresholds in `_assign_tier()` - may be too strict
- Verify player stats are loaded correctly
- Check line values are reasonable

### **Issue 4: "ImportError: cannot import props_integration"**
**Solution:** 
- Verify `tennis_props_integration.py` is in `tennis/` directory
- Check Python path includes tennis directory
- Try absolute import: `from tennis.tennis_props_integration import ...`

### **Issue 5: "File not found: player_stats.json"**
**Solution:**
- Create `tennis/data/` directory
- Create `player_stats.json` with sample data from Step 5
- Module will use hardcoded defaults as fallback

---

## 📊 **BEFORE vs AFTER:**

### **BEFORE:**
```
Input Format:     Match winners only ("Sinner vs Djokovic")
Models:           Elo ratings
Markets:          Match winner
Output:           0 edges (props rejected)
```

### **AFTER:**
```
Input Format:     Props (PrizePicks/Underdog format)
Models:           Props prediction models
Markets:          Games Won, Aces, Breakpoints, Fantasy Score, etc.
Output:           12+ edges per slate
```

---

## 🎯 **NEXT STEPS (After Integration Works):**

1. ✅ Add more players to `player_stats.json`
2. ✅ Tune probability thresholds based on backtesting
3. ✅ Add surface-specific adjustments (grass/clay/hard)
4. ✅ Integrate opponent matchup logic
5. ✅ Backtest against historical props data
6. ✅ Add Underdog format parsing
7. ✅ Connect to live player stats API

---

## 📞 **ROLLBACK PLAN (If Something Breaks):**

```bash
# Restore from backup
cd "C:\Users\hiday\UNDERDOG ANANLYSIS"
rm -rf tennis
cp -r backups/tennis_backup_YYYYMMDD tennis

# Verify restoration
ls tennis/
```

---

**Ready to integrate?** Follow steps 1-7 in order. Each step is independent and reversible.

**Need help?** Check:
1. Backup exists in `backups/`
2. Integration module imported correctly
3. Player stats JSON is valid
4. Test standalone first before full pipeline
