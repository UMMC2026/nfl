# Golf Stats Quick Reference Guide

## 📊 COMPLETE DATA MANAGEMENT WORKFLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     GOLF PLAYER DATA ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────┐                                                      │
│  │   DATA SOURCES    │                                                      │
│  ├───────────────────┤                                                      │
│  │ • DataGolf API    │──┐                                                   │
│  │   ($50/mo, best)  │  │                                                   │
│  │                   │  │     ┌────────────────────┐                        │
│  │ • PGA Tour Stats  │  │     │                    │                        │
│  │   (free, manual)  │──┼────►│  sync_players.py   │                        │
│  │                   │  │     │  import_players.py │                        │
│  │ • CSV/JSON Files  │──┤     │  add_player.py     │                        │
│  │   (bulk import)   │  │     │                    │                        │
│  │                   │  │     └─────────┬──────────┘                        │
│  │ • Manual Entry    │──┘               │                                   │
│  │   (add_player.py) │                  ▼                                   │
│  └───────────────────┘     ┌────────────────────────┐                       │
│                            │  player_database.json  │◄── PERSISTENT STORE   │
│                            │  (golf/data/)          │                       │
│                            └────────────┬───────────┘                       │
│                                         │                                   │
│                                         ▼                                   │
│                            ┌────────────────────────┐                       │
│                            │   PlayerDatabase()     │◄── IN-MEMORY CACHE    │
│                            │   class                │                       │
│                            └────────────┬───────────┘                       │
│                                         │                                   │
│                                         ▼                                   │
│                            ┌────────────────────────┐                       │
│                            │   generate_edges.py    │◄── MONTE CARLO        │
│                            │   (uses stats for MC)  │                       │
│                            └────────────────────────┘                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  BACKUPS: golf/data/backups/player_database_YYYYMMDD_HHMMSS.json      │ │
│  │  Auto-created before any sync/import operation (keeps last 10)         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ QUICK COMMANDS

```bash
# View database status
.venv\Scripts\python.exe golf/tools/sync_players.py --status

# Interactive management menu
.venv\Scripts\python.exe golf/tools/sync_players.py -i

# Sync from DataGolf API (requires DATAGOLF_API_KEY env var)
.venv\Scripts\python.exe golf/tools/sync_players.py --sync

# Sync tournament field (paste player names)
.venv\Scripts\python.exe golf/tools/sync_players.py --tournament

# Create backup manually
.venv\Scripts\python.exe golf/tools/sync_players.py --backup

# Restore from backup
.venv\Scripts\python.exe golf/tools/sync_players.py --restore

# Import from CSV file
.venv\Scripts\python.exe golf/tools/import_players.py players.csv

# Import from JSON file  
.venv\Scripts\python.exe golf/tools/import_players.py datagolf_export.json

# Add single player interactively
.venv\Scripts\python.exe golf/tools/add_player.py
```

---

## 🏆 FREE STAT SOURCES

### 1. PGA Tour Stats (BEST FREE SOURCE)
**URL**: https://www.pgatour.com/stats

| Stat Needed | Where to Find |
|-------------|---------------|
| **Scoring Average** | Stats → Scoring → Scoring Average |
| **Birdies/Round** | Stats → Scoring → Birdie Average |
| **SG Total** | Stats → Strokes Gained → SG: Total |
| **SG Off-the-Tee** | Stats → Strokes Gained → SG: Off-the-Tee |
| **SG Approach** | Stats → Strokes Gained → SG: Approach the Green |
| **SG Around Green** | Stats → Strokes Gained → SG: Around the Green |
| **SG Putting** | Stats → Strokes Gained → SG: Putting |

**Tips:**
- Use "2024-25" season filter for current stats
- Click player name for full profile
- SG stats are the MOST IMPORTANT for matchup modeling

---

### 2. ESPN Golf Statistics
**URL**: https://www.espn.com/golf/statistics

| Stat Needed | Where to Find |
|-------------|---------------|
| Scoring Average | Leaderboard → Stats dropdown |
| Birdies | Limited availability |
| SG | Not available |

**Tips:**
- Good for quick scoring checks
- Less detailed than PGA Tour site

---

### 3. DataGolf (Free Tier)
**URL**: https://datagolf.com/datagolf-rankings

| Stat Needed | Where to Find |
|-------------|---------------|
| **DG Ranking** | Homepage rankings |
| **True SG** | Click player → Skill Profile |
| **SG Breakdown** | Requires subscription |

**Tips:**
- Free rankings include approximate SG Total
- Most accurate source but paid API needed for full data

---

### 4. Golf Stats Pro
**URL**: https://www.golfstatspro.com

| Stat Needed | Where to Find |
|-------------|---------------|
| Historical Scoring | Player Search |
| Course History | Course Database |

---

## 📊 STAT INTERPRETATION GUIDE

### Strokes Gained Total (Most Important)
| SG Total | Tier | Description |
|----------|------|-------------|
| +2.0+ | ELITE | Top 10 in world |
| +1.0 to +2.0 | TOP | Top 30-50 |
| +0.5 to +1.0 | MID | Solid Tour player |
| 0.0 to +0.5 | AVERAGE | Tour average |
| Below 0.0 | BELOW AVG | Struggling |

### Scoring Average
| Scoring Avg | Quality |
|-------------|---------|
| Under 69.5 | Elite |
| 69.5 - 70.5 | Good |
| 70.5 - 71.5 | Average |
| Over 71.5 | Below Average |

### Birdies Per Round
| Birdies/Rd | Quality |
|------------|---------|
| 4.5+ | Aggressive scorer |
| 4.0 - 4.5 | Good |
| 3.5 - 4.0 | Average |
| Under 3.5 | Conservative |

---

## 🔧 ADDING PLAYERS TO DATABASE

### Method 1: Interactive Tool
```bash
python golf/tools/add_player.py
```
Follow prompts to enter stats.

### Method 2: Bulk Add (CSV-style)
```bash
python golf/tools/add_player.py
# Select option [2]
# Enter: NAME, SCORING_AVG, BIRDIES, SG_TOTAL
```

### Method 3: Direct Edit
Edit `golf/data/player_database.py` → `KNOWN_PLAYERS` dict:
```python
"Player Name": {
    "scoring_avg": 70.0,
    "scoring_stddev": 3.0,
    "birdies_per_round": 4.0,
    "sg_total": 0.5,
    "tier": "mid",
    "sample_size": 40,
},
```

---

## 📅 TOURNAMENT FIELD LOOKUP

Before each tournament, add players from the field:

1. **PGA Tour Field**: pgatour.com → Tournament → Field
2. **Fantasy Labs**: fantasylabs.com/pga/
3. **RotoGrinders**: rotogrinders.com/golf

---

## ⚡ QUICK COPY-PASTE TEMPLATE

For bulk adding players, use this format:
```
Collin Morikawa, 69.5, 4.3, 1.5
Tony Finau, 69.8, 4.1, 1.2
Viktor Hovland, 69.6, 4.4, 1.4
Wyndham Clark, 70.0, 4.0, 1.0
Sahith Theegala, 70.2, 4.2, 0.8
```
