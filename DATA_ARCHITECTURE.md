# 🏗️ FUOOM DATA ARCHITECTURE

## Overview

FUOOM uses a **hybrid data architecture** optimized for sports betting analysis:

| Data Type | Storage | Why |
|-----------|---------|-----|
| **Pick History** | SQLite (`cache/pick_history.db`) | Relational queries, calibration, backtesting |
| **Player Stats** | SQLite (`cache/player_stats.db`) | Fast indexed lookups, validation |
| **Opponent Defense** | SQLite (`cache/opponent_defense.db`) | Matchup context, adjustments |
| **Home/Away Splits** | SQLite (`cache/home_away_splits.db`) | Location-based adjustments |
| **Injury Tracker** | SQLite (`cache/injury_tracker.db`) | Avoid trap lines |
| **Legacy CSV** | CSV (`cache/nba_stats/`) | Human-readable backup, Excel viewing |
| **Config** | JSON (`config/`) | Human-editable, version control |

---

## 📊 Quick Start

```python
from fuoom_data import data

# Get player stats (instant, cached)
stats = data.get_player_stats("Cam Thomas")
# → {'team': 'BKN', 'points_L10': 24.3, 'points_L10_std': 6.2, ...}

# Validate projection (detect bugs like μ=8.7)
result = data.validate_projection("Cam Thomas", "points", 8.7)
# → {'is_valid': False, 'actual_avg': 24.3, 'pct_diff': -64.2%, 'warning': 'SUSPICIOUS'}

# Get matchup context (replaces "vs UNK")
context = data.get_matchup_context("Cam Thomas", "points", "DET")
# → "vs DET 🎯(ranks 29th defending PTS, allows 118.5)"

# Get matchup adjustment
adj = data.get_matchup_adjustment("points", "DET")
# → {'adjustment_pct': 7, 'direction': 'up', 'reason': 'DET terrible defense (rank 29)'}

# Get home/away splits
splits = data.get_player_splits("Stephen Curry")
# → {'home_pts_avg': 25.4, 'away_pts_avg': 29.5, ...}

# Get location adjustment
loc_adj = data.get_location_adjustment("Stephen Curry", "points", is_home=False)
# → {'adjustment': 4.1, 'pct_diff': 16.2%, 'reason': 'AWAY game: 29.5 vs overall 27.3'}

# Check injury status
injury = data.get_injury_warning("Tyler Herro")
# → "🚫 **OUT** (groin strain) - DO NOT BET"

# Check slate for injuries  
injuries = data.check_slate_injuries("outputs/SLATE.json")
# → {'skip': [...], 'caution': [...], 'monitor': [...]}

# Log picks from slate
data.log_slate("outputs/SLATE.json")

# Get calibration report
report = data.get_calibration_report()

# Dashboard
data.print_dashboard()
```

---

## 🌐 Web Dashboard

Start the performance dashboard:
```bash
python dashboard/app.py
```

Then open: **http://localhost:5050**

Features:
- Real-time hit rate metrics
- Calibration by tier/stat/direction
- Active injury report
- Last 7 days performance
- Shareable report: `/share`
- API endpoints: `/api/stats`, `/api/picks`, `/api/injuries`

---

## 🗄️ Database Files

### `cache/pick_history.db` ⭐⭐⭐ (Most Important)

**Every pick ever made.** Enables:
- Real hit rate calculation (not 8000% bugs!)
- Calibration tracking
- Backtesting
- Performance attribution

**Schema:**
```sql
picks (
    id, slate_date, player_name, stat, line, direction,
    mu, sigma, confidence, tier,
    actual_value, hit, margin,
    created_at, resolved_at
)
```

**Key Queries:**
```bash
# Show database stats
python pick_history_db.py --stats

# Log picks from slate
python pick_history_db.py --log outputs/FILE.json

# Show player history
python pick_history_db.py --player "Cam Thomas"

# Show calibration
python pick_history_db.py --calibration

# Export to CSV
python pick_history_db.py --export
```

---

### `cache/player_stats.db` ⭐⭐

**Current player averages.** Enables:
- Fast lookups (no repeated API calls)
- Projection validation (detect μ=8.7 bugs)
- Team mapping source of truth

**Schema:**
```sql
player_stats (
    player_name, team, player_id,
    points_L10, rebounds_L10, assists_L10, fg3_made_L10, pra_L10,
    points_L10_std, rebounds_L10_std,
    last_updated, games_available,
    last_10_games (JSON)
)
```

**Key Queries:**
```bash
# Show database stats
python player_stats_db.py --stats

# Get/update single player
python player_stats_db.py --player "Cam Thomas"

# Update all players from slate
python player_stats_db.py --from-json outputs/FILE.json

# Validate projection
python player_stats_db.py --validate "Cam Thomas,points,8.7"

# Export to CSV
python player_stats_db.py --export
```

---

### `cache/injury_tracker.db` ⭐⭐ (Avoid Trap Lines)

**Active injuries.** Prevents betting on:
- OUT players (total trap!)
- QUESTIONABLE/GTD (game-time decisions)
- Returning from injury (minute restrictions)

**CLI:**
```bash
# Full injury report
python injury_tracker_db.py --report

# Check specific player
python injury_tracker_db.py --player "Tyler Herro"

# Check team injuries
python injury_tracker_db.py --team MIA

# Check slate for injured players
python injury_tracker_db.py --check outputs/SLATE.json
```

---

## 🔧 CLI Commands

### Unified Data Layer
```bash
# Dashboard
python fuoom_data.py --dashboard

# Player profile (stats + picks)
python fuoom_data.py --player "Cam Thomas"

# Validate slate
python fuoom_data.py --validate outputs/FILE.json

# Log picks
python fuoom_data.py --log outputs/FILE.json

# Calibration report
python fuoom_data.py --calibration

# Export all
python fuoom_data.py --export
```

### Pick History
```bash
python pick_history_db.py --stats          # Database stats
python pick_history_db.py --log FILE.json  # Log picks
python pick_history_db.py --player "Name"  # Player history
python pick_history_db.py --calibration    # Calibration
python pick_history_db.py --unresolved     # Pending picks
python pick_history_db.py --export         # Export CSV
```

### Player Stats
```bash
python player_stats_db.py --stats              # Database stats
python player_stats_db.py --player "Name"      # Get/update player
python player_stats_db.py --from-json FILE     # Bulk update
python player_stats_db.py --validate "N,s,mu"  # Validate
python player_stats_db.py --team BKN           # Team players
python player_stats_db.py --export             # Export CSV
```

---

## 🔍 How This Fixes Your Bugs

### Bug #1: Cam Thomas μ=8.7

**Before (Manual):** Check 200+ files, find wrong number
**Now (Automatic):**
```python
data.validate_projection("Cam Thomas", "points", 8.7)
# → {'is_valid': False, 'actual_avg': 24.3, 'warning': 'SUSPICIOUS'}
```

### Bug #2: Hit Rate 8000%

**Before (Bug):** Code calculated wrong
**Now (Database):**
```python
data.get_hit_rate(stat="points")
# → {'total': 97, 'hits': 78, 'hit_rate': 80.4}  ← Real percentage!
```

---

## 📁 File Structure

```
cache/
├── pick_history.db      # All picks ever made (SQLite)
├── player_stats.db      # Player averages cache (SQLite)
└── nba_stats/           # Legacy CSV backup
    ├── all_player_stats.csv
    └── gamelogs/
        ├── Cam_Thomas.csv
        └── Stephen_Curry.csv

exports/                 # Generated exports
├── player_stats.csv
└── pick_history.csv
```

---

## 🚀 Daily Workflow

### 1. Start of Day
```bash
# Update stats for today's slate
python player_stats_db.py --from-json outputs/TODAY.json
```

### 2. Run Analysis
```bash
# Validate projections BEFORE running
python fuoom_data.py --validate outputs/TODAY.json
```

### 3. Log Picks
```bash
# Log all picks to history
python fuoom_data.py --log outputs/TODAY.json
```

### 4. End of Day
```bash
# Check dashboard
python fuoom_data.py --dashboard
```

---

## 🔧 Integration Example

```python
from fuoom_data import data

def process_slate(json_file):
    """Full slate processing with validation"""
    
    # 1. Update stats cache
    print("📊 Updating player stats...")
    data.update_stats_from_slate(json_file)
    
    # 2. Validate projections
    print("🔍 Validating projections...")
    issues = data.validate_slate(json_file)
    
    if issues:
        print(f"⚠️  {len(issues)} suspicious projections found!")
        for issue in issues:
            print(f"   - {issue['player']} {issue['stat']}: {issue['message']}")
        return False
    
    # 3. Log picks
    print("📋 Logging picks...")
    count = data.log_slate(json_file)
    print(f"✅ Logged {count} picks")
    
    return True

# Run
process_slate("outputs/FRYDAY8DAT_RISK_FIRST_20260130_FROM_UD.json")
```

---

## 📊 Why SQLite > CSV

| Feature | CSV | SQLite |
|---------|-----|--------|
| Query speed | Slow (scan all) | Fast (indexed) |
| Data types | Strings only | Proper types |
| Concurrent access | No | Yes |
| Data integrity | Fragile | ACID |
| File corruption | Breaks everything | Recoverable |
| Storage size | Large | Compressed |

**Result:** 10-100x faster queries, no data corruption, proper analytics.
