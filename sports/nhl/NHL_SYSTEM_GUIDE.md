# NHL Hockey Analysis System — Complete Guide

## 🏒 System Overview

The NHL module is a **Risk-First** prop betting analysis engine for hockey. It follows the same governance rules as the main system but with hockey-specific constraints.

**Version:** v3.0.0 (Production)
**Location:** `sports/nhl/`

---

## 📁 File Structure

```
sports/nhl/
├── nhl_menu.py              # Main interactive menu (1800+ lines)
├── universal_parser.py      # Multi-format prop parser (Underdog/PrizePicks)
├── player_stats.py          # Player/goalie stats database (2025-26 season)
├── nhl_report.py            # Professional report generator
├── process_slate.py         # Batch processing utilities
├── outputs/                 # Analysis output files
│   └── *RISK_FIRST*.json    # Standard output format
└── NHL_SYSTEM_GUIDE.md      # This document
```

---

## 🚀 How to Run

### From Main Menu
```
.venv\Scripts\python.exe menu.py
→ Press [HK] for NHL Hockey
```

### Standalone
```
.venv\Scripts\python.exe sports/nhl/nhl_menu.py
```

---

## 📊 Data Flow Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    NHL ANALYSIS PIPELINE                        │
└─────────────────────────────────────────────────────────────────┘

1. INGEST STAGE
   ┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
   │  Underdog    │────▶│ Universal Parser │────▶│  NHLProp     │
   │  Paste       │     │ (auto-detect)    │     │  Objects     │
   └──────────────┘     └──────────────────┘     └──────────────┘
         │                      │
         │              ┌───────▼───────┐
         │              │ Stat Mapping  │
         │              │ SOG, Goals,   │
         │              │ Points, Saves │
         │              └───────────────┘
         │
2. ANALYSIS STAGE
   ┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
   │  NHLSlate    │────▶│  analyze_slate() │────▶│  Probability │
   │  (all props) │     │                  │     │  Assignment  │
   └──────────────┘     └──────────────────┘     └──────────────┘
                               │
                        ┌──────▼──────┐
                        │ Player Stats │
                        │ Lookup       │
                        │ (L10 avg/σ)  │
                        └─────────────┘
                               │
3. GOVERNANCE STAGE
   ┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
   │  Raw Props   │────▶│  Tier Assignment │────▶│  STRONG/LEAN │
   │              │     │  + Risk Flags    │     │  /SKIP/BLOCK │
   └──────────────┘     └──────────────────┘     └──────────────┘
                               │
                        ┌──────▼──────┐
                        │ Goalie Gate │
                        │ (MANDATORY) │
                        └─────────────┘
                               │
4. OUTPUT STAGE
   ┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
   │  Playable    │────▶│  Cross-Sport DB  │────▶│  JSON/Report │
   │  Picks       │     │  Auto-Save       │     │  /Telegram   │
   └──────────────┘     └──────────────────┘     └──────────────┘
```

---

## 🎯 Tier Thresholds (NHL-Specific)

| Tier | Probability | Notes |
|------|-------------|-------|
| **SLAM** | ❌ DISABLED | Too much goalie variance |
| **STRONG** | ≥ 64% | Stricter than NBA (65%) |
| **LEAN** | ≥ 58% | Stricter than NBA (55%) |
| **SKIP** | < 58% | Not playable |

**Why No SLAM Tier?**
- Goalie performance is highly volatile
- Backup goalies can start unexpectedly
- Back-to-back games cause fatigue
- Sample sizes are smaller than NBA

---

## 📈 Supported Prop Types

### Skater Props
| Stat | Internal Key | Description |
|------|--------------|-------------|
| Shots on Goal | `SOG` | Total shots on net |
| Goals | `Goals` | Goals scored |
| Assists | `Assists` | Primary + secondary assists |
| Points | `Points` | Goals + Assists |
| Power Play Points | `PPP` | Points on power play |
| Faceoffs Won | `FOW` | Center/wing faceoff wins |
| Hits | `Hits` | Physical hits recorded |
| Blocked Shots | `Blocked` | Shots blocked on defense |
| 1st Period SOG | `1P_SOG` | First period shots |
| First Goal Scorer | `FGS` | Score first goal of game |
| Plus/Minus | `PM` | +/- rating for game |
| Fantasy Points | `FPTS` | DFS fantasy score |

### Goalie Props
| Stat | Internal Key | Description |
|------|--------------|-------------|
| Saves | `Saves` | Total saves |
| Goals Against | `GA` | Goals allowed |
| 1st Period Saves | `1P Saves` | First period saves |
| 1st Period GA | `1P GA` | First period goals against |

---

## 🧮 Probability Calculation

### For Skaters (Poisson Model)
```python
# Get player's last 10 games average and standard deviation
mu = player_stats.get_l10_avg(player, stat)  # e.g., 3.2 SOG
sigma = player_stats.get_l10_std(player, stat)  # e.g., 1.1

# Calculate probability of going OVER the line
from scipy.stats import poisson
lambda_param = mu
prob_over = 1 - poisson.cdf(line, lambda_param)
prob_under = poisson.cdf(line - 0.5, lambda_param)  # For half-lines
```

### For Goalies (Adjusted Poisson)
```python
# Goalies have additional adjustments
base_prob = calculate_poisson_prob(goalie_stats, line)

# Apply goalie-specific penalties
if is_backup_goalie:
    base_prob = min(base_prob, 0.60)  # Cap at 60%
if games_started < 5:
    base_prob = min(base_prob, 0.58)  # Small sample cap
if is_back_to_back:
    base_prob *= 0.96  # 4% penalty
```

---

## 🚨 Risk Flags & Gates

### Goalie Confirmation Gate (MANDATORY)
```python
# Goalie props REQUIRE confirmation from 2+ sources
if prop.stat in GOALIE_STATS:
    if not goalie_confirmed(prop.player, sources=2):
        prop.pick_state = "REJECTED"
        prop.risk_flags.append("GOALIE_NOT_CONFIRMED")
```

### Risk Flag Types
| Flag | Trigger | Impact |
|------|---------|--------|
| `GOALIE_NOT_CONFIRMED` | <2 source confirmation | REJECT |
| `BACKUP_GOALIE` | Not confirmed starter | Cap 60% |
| `B2B_GOALIE` | Back-to-back game | -4% prob |
| `SMALL_SAMPLE` | <5 games started | Cap 58% |
| `LOW_TOI` | Time on ice <12 min | -5% prob |
| `INJURED_RECENTLY` | DTD or GTD status | VETTED only |
| `LINE_MOVEMENT` | Line moved >10% | Flag for review |

---

## 🔧 Diagnostic Commands

### Check Parser
```python
from sports.nhl.universal_parser import parse_universal

text = """athlete or team avatar
Tage Thompson
BUF vs PIT - 6:00PM CST
3.5
Shots on Goal
Higher
1.06x
"""

props, meta = parse_universal(text)
print(f"Parsed: {len(props)} props")
print(f"Format: {meta['formats_detected']}")
```

### Check Player Stats
```python
from sports.nhl.player_stats import get_player_stats

stats = get_player_stats("Sidney Crosby")
print(f"SOG L10: {stats['sog_avg']:.2f} ± {stats['sog_std']:.2f}")
print(f"Points L10: {stats['pts_avg']:.2f}")
```

### Manual Analysis
```python
from sports.nhl.nhl_menu import NHLSlate, NHLProp, analyze_slate
from sports.nhl.universal_parser import parse_universal
from datetime import date

# Read props
with open('nhl_slate.txt', 'r') as f:
    text = f.read()

# Parse
props, _ = parse_universal(text)

# Convert to NHLProp
nhl_props = [
    NHLProp(
        player=p.player,
        team=p.team,
        position=p.position,
        opponent=p.opponent,
        game_time=p.game_time,
        stat=p.stat,
        line=p.line,
        direction=p.direction,
    ) for p in props
]

# Create and analyze slate
slate = NHLSlate(date=date.today().isoformat(), props=nhl_props, games={})
analyzed = analyze_slate(slate)

# Show results
print(f"Total: {analyzed.total_props}")
print(f"Playable: {analyzed.playable_props}")
print(f"STRONG: {analyzed.strong_picks}")
print(f"LEAN: {analyzed.lean_picks}")
```

---

## 🐛 Common Issues & Fixes

### Issue: "No props parsed from input"
**Cause:** PowerShell paste handling issue
**Fix:** Use file input method:
1. Save props to `nhl_slate.txt`
2. In menu, press `[1]` → `[2]` to load from file

### Issue: All picks show as REJECTED
**Cause:** Goalie gate failing or no stats available
**Fix:** 
1. Check goalie confirmation sources
2. Verify player exists in `player_stats.py`
3. Check for typos in player names

### Issue: Probabilities show 0%
**Cause:** Player not in stats database
**Fix:**
1. Add player to `sports/nhl/player_stats.py`
2. Or run with `--skip-stats` flag

### Issue: NHL not in Cross-Sport Parlays
**Cause:** Analysis not run today
**Fix:**
1. Run NHL menu `[HK]`
2. Ingest slate `[1]` → `[2]`
3. Analyze `[2]` - auto-saves to cross-sport DB

---

## 📋 Menu Options Reference

```
============================================================
  NHL ANALYSIS MENU v3.0.0
============================================================

  [1] Ingest Underdog Slate (paste props)
      → [1] Paste mode (press ENTER twice)
      → [2] Load from file (nhl_slate.txt)
      
  [2] Analyze Slate — Run full probability analysis
  [3] Show Playable Picks — Display STRONG/LEAN only
  [5] Show TOP 5 PICKS — Best plays

  [S] Filter: SOG Only
  [O] Filter: Goals Only
  [B] Filter: Blocked Shots Only
  [P] Analyze Player Props (Goals/Assists/Points)

  [G] Goalie Confirmation Check — Verify starting goalies
  [E] Export Picks (JSON)
  [R] GENERATE PROFESSIONAL REPORT
  [T] SEND TO TELEGRAM

  [M] MONTE CARLO PARLAY OPTIMIZER
  [C] CALIBRATION REPORT
  [L] REFRESH LIVE STATS

  [H] Help
  [Q] Quit
```

---

## 🔄 Integration with Cross-Sport System

### Auto-Save to Daily DB
After `[2] Analyze Slate`, NHL automatically saves top 5 picks to:
```
cache/daily_picks.db
```

### Cross-Sport Parlay Access
From main menu:
```
[XP] Cross-Sport Parlays
  → [1] View Today's Picks (All Sports)
  → [4] Build 4-Leg Cross-Sport Parlays
```

### Manual Save
If auto-save fails:
```
[XP] → [6] Save Current NHL Picks to Database
```

---

## 📊 Output Format

### JSON Output Schema
```json
{
  "date": "2026-02-05",
  "sport": "NHL",
  "total_props": 102,
  "playable_props": 45,
  "strong_picks": 18,
  "lean_picks": 27,
  "picks": [
    {
      "player": "Sidney Crosby",
      "team": "PIT",
      "opponent": "BUF",
      "stat": "Points",
      "line": 0.5,
      "direction": "More",
      "probability": 91.8,
      "tier": "STRONG",
      "pick_state": "OPTIMIZABLE",
      "risk_flags": []
    }
  ]
}
```

---

## 🎓 Best Practices

### 1. Always Check Goalie Confirmation
Before betting goalie props, verify the starter:
- DailyFaceoff.com
- LeftWingLock.com
- Team official Twitter

### 2. Avoid Back-to-Back Goalies
Goalies playing second game of B2B have:
- Lower save percentage
- Higher GAA
- More variance

### 3. SOG is Most Predictable
Shots on Goal has the lowest variance of all NHL props. Prioritize:
- SOG overs for high-volume shooters
- SOG unders for defensive matchups

### 4. First Period Props = More Variance
1st period stats have smaller sample sizes. Adjust confidence:
- 1P SOG: Less reliable than full game
- 1P Saves: Highly dependent on opponent's 1P strategy

### 5. Power Play Points Require PP1 Confirmation
Only bet PPP if player is confirmed on first power play unit.

---

## 🔗 Related Files

| File | Purpose |
|------|---------|
| `config/thresholds.py` | NHL tier thresholds (SLAM=None) |
| `engine/daily_picks_db.py` | Cross-sport database |
| `nhl_slate.txt` | Current props file (root directory) |
| `cache/nhl_slate_cache.json` | Cached slate data |

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| v3.0.0 | 2026-02 | Universal parser, Monte Carlo, Cross-sport integration |
| v2.1.0 | 2026-01 | Goalie gate mandatory, file input mode |
| v2.0.0 | 2025-12 | Real stats integration, Poisson model |
| v1.0.0 | 2025-11 | Initial release |
