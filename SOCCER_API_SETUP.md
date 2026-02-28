# ⚽ API-Football Integration Setup Guide

## 🎯 What This Adds

Your soccer system now supports **automated player stats fetching** from API-Football!

**Before:** Manual stats entry (15-30 min per slate)  
**After:** Automatic API fetch (2 minutes)

---

## 🔧 Setup Instructions

### Step 1: Get RapidAPI Key

1. Visit: https://rapidapi.com/api-sports/api/api-football
2. Click "Subscribe to Test" (Free tier available)
3. Select pricing tier:
   - **Free:** 100 requests/day (good for testing)
   - **Basic:** $10/month, 1000 requests/day (recommended)
4. Copy your API key from dashboard

### Step 2: Configure API Key

**Option A: Environment Variable (Recommended)**
```bash
# Windows PowerShell
$env:RAPIDAPI_KEY="your_api_key_here"

# Windows CMD
set RAPIDAPI_KEY=your_api_key_here

# Linux/Mac
export RAPIDAPI_KEY=your_api_key_here
```

**Option B: .env File**
```bash
# Create .env file in workspace root
cd "C:\Users\hiday\UNDERDOG ANANLYSIS"
echo RAPIDAPI_KEY=your_api_key_here > .env
```

### Step 3: Install Dependencies

```bash
# Activate virtual environment
.venv\Scripts\activate

# Install requests library (if not already installed)
pip install requests
```

### Step 4: Test API Connection

```bash
# Test the API integration
.venv\Scripts\python.exe soccer\api_football_integration.py
```

**Expected Output:**
```
====================================================
API-FOOTBALL SOCCER STATS FETCHER - TEST MODE
====================================================

🧪 Testing API-Football connection...
   Using API host: api-football-v1.p.rapidapi.com
✅ API connection successful!
   Test player: Cristiano Ronaldo
   Player ID: 874

⚽ Fetching stats from API-Football...
   [1/3] Fetching Mohamed Salah...
   ✓ Found: Mohamed Salah (ID: 306)
   ✓ Stats fetched: 0.82 goals/game, 3.21 SOT/game
...
```

---

## 🎮 How to Use

### Complete Workflow with API

```bash
# 1. Start menu
python menu.py

# 2. Select Soccer
Select: Soccer

# 3. Paste your Underdog props
Select: [4] Paste Underdog Soccer Slate
```

Paste your props:
```
Mohamed Salah
Liverpool vs Arsenal
1.5
Goals
Higher
Lower

Erling Haaland
Man City vs Chelsea
2.5
Shots on Target
Higher
Lower
```

```bash
# 4. Fetch stats from API (NEW!)
Select: [7] 🌐 Fetch Stats from API-Football

Output:
  ⚽ API-FOOTBALL PLAYER STATS FETCHER
  
  Testing API connection...
  ✅ API connection verified!
  
  Fetch stats for:
    [1] Players in current slate (auto-detect)
    [2] Specific players (manual entry)
  
  Select: 1
  
  Found 2 players:
    1. Mohamed Salah
    2. Erling Haaland
  
  Fetching stats for 2 players...
  
  [1/2] Fetching Mohamed Salah...
  ✓ Found: Mohamed Salah (ID: 306)
  ✓ Stats fetched: 0.82 goals/game, 3.21 SOT/game
  
  [2/2] Fetching Erling Haaland...
  ✓ Found: Erling Haaland (ID: 1100)
  ✓ Stats fetched: 1.12 goals/game, 4.83 SOT/game
  
  ✅ SUCCESS!
  Fetched stats for 2/2 players
  Saved to: soccer/data/player_stats_api.json

# 5. Analyze props with fresh stats
Select: [5] ⚽ Analyze Player Props (Monte Carlo)

Output:
  [3/5] FETCHING PLAYER STATS...
  ✓ Loaded stats for 2 players (from API)
  
  [4/5] RUNNING MONTE CARLO...
  ✓ Simulated 2 props (10,000 iterations each)
  
  [5/5] DETECTING EDGES...
  ✓ Generated 2 edges
    SLAM: 1 | STRONG: 1

# 6. View results
Select: [2] View Latest Report
```

---

## 📊 API Data Format

### What Gets Fetched
```json
{
  "Mohamed Salah": {
    "player": "Mohamed Salah",
    "team": "Liverpool",
    "position": "Attacker",
    "games_played": 28,
    
    "avg_goals": 0.82,
    "avg_assists": 0.45,
    "avg_shots": 4.21,
    "avg_shots_on_target": 3.21,
    "avg_tackles": 0.82,
    "avg_fouls": 1.12,
    "avg_passes": 42.3,
    "avg_key_passes": 2.1,
    
    "total_goals": 23,
    "total_assists": 13,
    "total_shots": 118,
    "total_shots_on_target": 90,
    "total_tackles": 23,
    
    "data_source": "api_football",
    "last_updated": "2026-01-29T12:00:00",
    "season": "2024"
  }
}
```

### How It Integrates

The API stats are saved to `soccer/data/player_stats_api.json` which can then be:
1. Automatically loaded by the Monte Carlo pipeline
2. Manually imported via option [6]
3. Cached for future use

---

## 🚨 Troubleshooting

### "No API key found"
- Check environment variable: `echo $env:RAPIDAPI_KEY`
- Verify .env file exists and has correct format
- Make sure there are no quotes around the key in .env

### "API connection failed"
- Verify API key is valid on RapidAPI dashboard
- Check you have remaining API calls (check quota)
- Ensure internet connection is working
- Try the test mode: `python soccer\api_football_integration.py`

### "Player not found"
- Try exact spelling from transfermarkt/official sources
- API searches current season (2024) - player may have moved
- Some lesser-known players may not be in API database
- Check player name spelling variations

### "Stats not available"
- Player may not have played recent matches
- Check if player is in a supported league
- Free tier may have limited league coverage
- Try with a well-known player first

### "API rate limit exceeded"
- Free tier: 100 requests/day
- Each player = 2 API calls (search + stats)
- Wait 24 hours or upgrade to paid tier
- Cache fetched stats for reuse

---

## 💡 Pro Tips

### 1. Batch Fetch for Efficiency
```
Instead of fetching one player at a time:
- Paste entire slate first ([4])
- Fetch all players at once ([7])
- Saves API calls and time
```

### 2. Cache Stats for Reuse
```
Stats are saved to player_stats_api.json
Reuse for same players in different slates
Only re-fetch when you need latest updates
```

### 3. Mix API + Manual
```
Use API for most players
Add manual overrides for specific situations
Best of both worlds
```

### 4. Verify Before Betting
```
API stats are automated - always cross-check:
- Recent injuries
- Lineup confirmations
- Form changes
```

---

## 📈 Cost Breakdown

### Free Tier (100 req/day)
- 50 player stats per day (2 calls each)
- Good for testing and light use
- Resets every 24 hours

### Basic Tier ($10/month)
- 1000 requests/day
- 500 player stats per day
- Sufficient for daily DFS analysis

### Recommended Usage
- Fetch stats 1-2 times per day
- Cache results for multiple slates
- Only re-fetch if major lineup changes

---

## 🔐 Security Notes

- **Never commit API keys to git**
- Use .env file (already in .gitignore)
- Don't share keys publicly
- Rotate keys if accidentally exposed
- Monitor usage on RapidAPI dashboard

---

## 🎯 Integration Summary

### Files Added
```
soccer/
├── api_football_integration.py  ← API fetching logic
└── data/
    └── player_stats_api.json     ← Cached API results
```

### Files Modified
```
soccer/
└── soccer_main.py                ← Added option [7]
```

### Menu Changes
```
OLD:
  [6] Import Player Stats (JSON)
  [0] Back

NEW:
  [6] Import Player Stats (JSON)
  [7] 🌐 Fetch Stats from API-Football (Real-time)
  [0] Back
```

---

## 🚀 Next Steps

1. ✅ Get RapidAPI key
2. ✅ Configure environment variable
3. ✅ Test connection
4. ✅ Fetch stats for a slate
5. ✅ Run Monte Carlo analysis
6. ✅ Compare results to manual workflow

**Questions?** Test with `python soccer\api_football_integration.py` first!
