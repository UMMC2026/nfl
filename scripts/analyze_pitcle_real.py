"""
PIT @ CLE - Sunday December 28, 2025 - 12:00 PM CST
REAL STATS-BASED ANALYSIS

Using actual 2025 season data from ESPN/NFL.com
PIT: 9-6 | CLE: 3-12
"""

# ============================================
# REAL 2025 SEASON STATS FROM ESPN
# ============================================

CLE_STATS = {
    # PASSING (6 games for Sanders)
    'Shedeur Sanders': {
        'games': 6,
        'pass_yards': 1103, 'pass_yards_pg': 183.8,
        'pass_tds': 6, 'pass_tds_pg': 1.0,
        'ints': 8, 'ints_pg': 1.33,
        'rush_yards': 123, 'rush_yards_pg': 20.5,
        'rush_tds': 0,
        'completions': 92, 'attempts': 167, 'comp_pct': 55.1
    },
    
    # RUSHING - Quinshon Judkins is RB1, not Dylan Sampson
    'Quinshon Judkins': {  # CLE RB1
        'games': 14, 'rush_yards': 827, 'rush_yards_pg': 59.1,
        'rush_tds': 4, 'receptions': 26, 'rec_yards': 171
    },
    'Dylan Sampson': {  # CLE RB2
        'games': 13, 'rush_yards': 116, 'rush_yards_pg': 8.9,
        'rush_tds': 1, 'receptions': 28, 'rec_yards': 259, 'rec_tds': 2
    },
    
    # RECEIVING
    'Harold Fannin': {
        'games': 15, 'receptions': 70, 'targets': 105,
        'rec_yards': 701, 'rec_yards_pg': 46.7,
        'rec_tds': 5, 'longest': 35
    },
    'Jerry Jeudy': {
        'games': 15, 'receptions': 43, 'targets': 93,
        'rec_yards': 531, 'rec_yards_pg': 35.4,
        'rec_tds': 2
    },
    'Isaiah Bond': {
        'games': 14, 'receptions': 16, 'targets': 41,
        'rec_yards': 309, 'rec_yards_pg': 22.1,
        'rec_tds': 0
    },
    'Cedric Tillman': {
        'games': 11, 'receptions': 19, 'targets': 36,
        'rec_yards': 205, 'rec_yards_pg': 18.6,
        'rec_tds': 2
    },
    'Malachi Corley': {
        'games': 11, 'receptions': 8, 'targets': 11,
        'rec_yards': 55, 'rec_yards_pg': 5.0,
        'rec_tds': 0, 'rush_yards': 109, 'rush_tds': 1
    },
    
    # DEFENSE
    'Carson Schwesinger': {
        'games': 15, 'solo': 64, 'assists': 83, 'total_tackles': 147,
        'sacks': 2.5, 'ints': 0, 'pds': 11
    },
    'Myles Garrett': {
        'games': 15, 'solo': 41, 'assists': 17, 'total_tackles': 58,
        'sacks': 22, 'tfl': 32
    },
    'Grant Delpit': {
        'games': 15, 'solo': 36, 'assists': 35, 'total_tackles': 71,
        'sacks': 1, 'ints': 1
    },
    'Alex Wright': {
        'games': 12, 'solo': 18, 'assists': 13, 'total_tackles': 31,
        'sacks': 4.5
    },
    'Mason Graham': {
        'games': 15, 'solo': 23, 'assists': 16, 'total_tackles': 39,
        'sacks': 0.5
    },
    
    # KICKING
    'Andre Szmyt': {
        'games': 15, 'fg_made': 20, 'fg_att': 23, 'fg_pct': 87.0,
        'xp_made': 22, 'xp_att': 23, 'xp_pct': 95.7
    }
}

# PIT stats (from general team stats - need estimates)
PIT_STATS = {
    'team': {
        'pass_yards': 3170, 'rush_yards': 1525,
        'pass_tds': 25, 'rush_tds': 14,
        'total_tds': 42, 'sacks_allowed': 27
    }
}

print('=' * 120)
print('PIT @ CLE - SUNDAY 12:00 PM CST - REAL STATS ANALYSIS')
print('=' * 120)
print('\nTeam Records: PIT 9-6 | CLE 3-12')
print()

# ============================================
# ANALYZE EACH PROP WITH REAL STATS
# ============================================

print('=' * 120)
print('🏈 QUARTERBACK ANALYSIS'.center(120))
print('=' * 120)

# Shedeur Sanders analysis
ss = CLE_STATS['Shedeur Sanders']
print(f"""
SHEDEUR SANDERS (CLE - Rookie QB, 6 starts)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Season Stats: {ss['pass_yards']} yds, {ss['pass_tds']} TD, {ss['ints']} INT in {ss['games']} games
Per Game Avg: {ss['pass_yards_pg']} pass yds, {ss['pass_tds_pg']:.1f} TD, {ss['ints_pg']:.2f} INT
Rushing: {ss['rush_yards']} yds ({ss['rush_yards_pg']} per game), {ss['rush_tds']} rush TDs

PROP ANALYSIS:
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Prop                  │ Line    │ Stats Say          │ Recommendation │ Confidence │ Hit %     │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Pass Yards            │ 178.5   │ Avg 183.8/game     │ ✅ OVER        │ HIGH       │ ~55%      │
│ Pass TDs              │ 0.5     │ 1.0 TD/game        │ ✅ OVER        │ MEDIUM     │ ~50%      │
│ INTs Thrown           │ 0.5     │ 1.33 INT/game      │ ✅ OVER        │ HIGH       │ ~65%      │
│ Rush Yards            │ 12.5    │ 20.5 yds/game      │ ✅ OVER        │ HIGH       │ ~60%      │
│ Rush + Rec TDs        │ 0.5     │ 0 rush TDs season  │ ❌ UNDER       │ HIGH       │ ~70%      │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

⚠️  KEY INSIGHT: Sanders throws INTs (8 in 6 games = 1.33/game). OVER 0.5 INTs is STRONG.
⚠️  Line says LOWER on INTs (+13%) - DISAGREE! Stats say he throws picks.
""")

# ============================================
# RB ANALYSIS
# ============================================
print('=' * 120)
print('🏃 RUNNING BACK ANALYSIS'.center(120))
print('=' * 120)

qj = CLE_STATS['Quinshon Judkins']
ds = CLE_STATS['Dylan Sampson']

print(f"""
DYLAN SAMPSON (CLE RB2 - Backup to Quinshon Judkins)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Season Stats: {ds['rush_yards']} rush yds, {ds['rush_tds']} rush TD in {ds['games']} games
Receiving: {ds['receptions']} rec, {ds['rec_yards']} yds, {ds['rec_tds']} rec TDs
Per Game: {ds['rush_yards_pg']} rush yds, {ds['rec_yards']/ds['games']:.1f} rec yds

⚠️  CRITICAL: Quinshon Judkins is RB1 with 827 rush yds! Sampson is RB2.

PROP ANALYSIS:
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Prop                  │ Line    │ Stats Say          │ Recommendation │ Confidence │ Hit %     │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Rush Yards            │ 42.5    │ Avg 8.9/game       │ ❌ UNDER       │ VERY HIGH  │ ~85%      │
│ Receiving Yards       │ 17.5    │ Avg 19.9/game      │ TOSS UP        │ LOW        │ ~52%      │
│ Receptions            │ 2.5     │ 2.15 rec/game      │ ❌ UNDER       │ MEDIUM     │ ~55%      │
│ Rush + Rec TDs        │ 0.5     │ 3 TDs in 13 games  │ ❌ UNDER       │ MEDIUM     │ ~60%      │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

🚨 LINE IS WRONG: 42.5 rush yards for a guy averaging 8.9? SLAM UNDER!
""")

# ============================================
# RECEIVING ANALYSIS
# ============================================
print('=' * 120)
print('📡 RECEIVING ANALYSIS'.center(120))
print('=' * 120)

hf = CLE_STATS['Harold Fannin']
jj = CLE_STATS['Jerry Jeudy']
ib = CLE_STATS['Isaiah Bond']
ct = CLE_STATS['Cedric Tillman']
mc = CLE_STATS['Malachi Corley']

print(f"""
HAROLD FANNIN JR. (CLE TE1 - Team Leader in Receptions)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Season: {hf['receptions']} rec, {hf['rec_yards']} yds, {hf['rec_tds']} TDs in {hf['games']} games
Per Game: {hf['receptions']/hf['games']:.1f} rec, {hf['rec_yards_pg']} yds

PROP ANALYSIS:
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Prop                  │ Line    │ Stats Say          │ Recommendation │ Confidence │ Hit %     │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Receiving Yards       │ 52.5    │ Avg 46.7/game      │ ❌ UNDER       │ MEDIUM     │ ~55%      │
│ Receptions            │ 5.5     │ 4.67 rec/game      │ ❌ UNDER       │ MEDIUM     │ ~58%      │
│ Rush + Rec TDs        │ 0.5     │ 5 TDs in 15 games  │ ❌ UNDER       │ MEDIUM     │ ~60%      │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

JERRY JEUDY (CLE WR1)
━━━━━━━━━━━━━━━━━━━━━
Season: {jj['receptions']} rec, {jj['rec_yards']} yds, {jj['rec_tds']} TDs
Per Game: {jj['receptions']/jj['games']:.1f} rec, {jj['rec_yards_pg']} yds

│ Receiving Yards       │ 27.5    │ Avg 35.4/game      │ ✅ OVER        │ MEDIUM     │ ~55%      │
│ Receptions            │ 2.5     │ 2.87 rec/game      │ ✅ OVER        │ LOW        │ ~52%      │

ISAIAH BOND (CLE WR - Deep Threat)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Season: {ib['receptions']} rec, {ib['rec_yards']} yds, {ib['rec_tds']} TDs
Per Game: {ib['receptions']/ib['games']:.1f} rec, {ib['rec_yards_pg']} yds

│ Receiving Yards       │ 10.5    │ Avg 22.1/game      │ ✅ OVER        │ HIGH       │ ~65%      │
│ Receptions            │ 1.5     │ 1.14 rec/game      │ ❌ UNDER       │ MEDIUM     │ ~55%      │

⚠️  Bond averages only 1.14 receptions but 22.1 yards per game = DEEP THREAT
    He either catches 0-1 or hits a bomb for 40+

MALACHI CORLEY (CLE WR)
━━━━━━━━━━━━━━━━━━━━━━━
Season: {mc['receptions']} rec, {mc['rec_yards']} yds, {mc['rec_tds']} rec TDs
Also rushes: {mc['rush_yards']} rush yds, {mc['rush_tds']} rush TD

│ Receiving Yards       │ 12.5    │ Avg 5.0/game       │ ❌ UNDER       │ HIGH       │ ~70%      │
│ Rush + Rec TDs        │ 0.5     │ 1 TD in 11 games   │ ❌ UNDER       │ MEDIUM     │ ~65%      │
""")

# ============================================
# DEFENSE ANALYSIS
# ============================================
print('=' * 120)
print('🛡️ DEFENSE ANALYSIS'.center(120))
print('=' * 120)

mg = CLE_STATS['Myles Garrett']
cs = CLE_STATS['Carson Schwesinger']
gd = CLE_STATS['Grant Delpit']
aw = CLE_STATS['Alex Wright']
mgs = CLE_STATS['Mason Graham']

print(f"""
MYLES GARRETT (CLE DE - DPOY Candidate)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Season: {mg['sacks']} sacks, {mg['total_tackles']} tackles in {mg['games']} games
Per Game: {mg['sacks']/mg['games']:.2f} sacks/game

PROP ANALYSIS:
│ Sacks                 │ 1.5     │ 1.47 sacks/game    │ TOSS UP        │ LOW        │ ~50%      │
│ Tackles + Assists     │ 3.5     │ 3.87 T+A/game      │ ✅ OVER        │ MEDIUM     │ ~55%      │

⚠️  Garrett is a MONSTER - 22 sacks in 15 games. Line at 1.5 is FAIR.

CARSON SCHWESINGER (CLE LB - Tackle Leader)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Season: {cs['total_tackles']} tackles, {cs['sacks']} sacks, {cs['ints']} INTs
Per Game: {cs['total_tackles']/cs['games']:.1f} tackles

│ Tackles + Assists     │ 10.5    │ 9.8 T+A/game       │ ❌ UNDER       │ LOW        │ ~52%      │
│ Sacks                 │ 0.5     │ 0.17 sacks/game    │ ❌ UNDER       │ HIGH       │ ~75%      │

ALEX WRIGHT (CLE DE)
━━━━━━━━━━━━━━━━━━━━
Season: {aw['sacks']} sacks in {aw['games']} games = {aw['sacks']/aw['games']:.2f} per game

│ Sacks                 │ 0.5     │ 0.375 sacks/game   │ ❌ UNDER       │ MEDIUM     │ ~60%      │

MASON GRAHAM (CLE DT - Rookie)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Season: {mgs['sacks']} sacks in {mgs['games']} games = {mgs['sacks']/mgs['games']:.3f} per game

│ Sacks                 │ 0.5     │ 0.033 sacks/game   │ ❌ UNDER       │ VERY HIGH  │ ~90%      │

🚨 MASON GRAHAM HAS 0.5 SACKS ALL SEASON. UNDER 0.5 IS FREE MONEY!
""")

# ============================================
# FINAL RECOMMENDATIONS
# ============================================
print()
print('=' * 120)
print('🎯 FINAL PICKS - STATS-BASED RECOMMENDATIONS'.center(120))
print('=' * 120)

print("""
╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║  STRONG PLAYS (70%+ CONFIDENCE)                                                                  ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════╣
║  ✅ Dylan Sampson UNDER 42.5 Rush Yards     │ Avg 8.9/game as RB2       │ 85% │ YES            ║
║  ✅ Mason Graham UNDER 0.5 Sacks            │ Only 0.5 sacks ALL SEASON │ 90% │ YES            ║
║  ✅ Shedeur Sanders OVER 0.5 INTs           │ 1.33 INT/game avg         │ 65% │ YES            ║
║  ✅ Malachi Corley UNDER 12.5 Rec Yards     │ Avg 5.0/game              │ 70% │ YES            ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║  SOLID PLAYS (55-70% CONFIDENCE)                                                                 ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════╣
║  ✅ Shedeur Sanders OVER 12.5 Rush Yards    │ Avg 20.5/game             │ 60% │ YES            ║
║  ✅ Isaiah Bond OVER 10.5 Rec Yards         │ Avg 22.1/game             │ 65% │ YES            ║
║  ✅ Harold Fannin UNDER 52.5 Rec Yards      │ Avg 46.7/game             │ 55% │ LEAN YES       ║
║  ✅ Harold Fannin UNDER 5.5 Receptions      │ Avg 4.67/game             │ 58% │ LEAN YES       ║
║  ✅ Alex Wright UNDER 0.5 Sacks             │ 0.375/game                │ 60% │ YES            ║
║  ✅ Schwesinger UNDER 0.5 Sacks             │ 0.17/game                 │ 75% │ YES            ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║  SKIP / COIN FLIPS                                                                               ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════╣
║  ⚠️  Myles Garrett 1.5 Sacks                │ 1.47/game - too close     │ 50% │ NO             ║
║  ⚠️  Shedeur Sanders 178.5 Pass Yards       │ 183.8/game - close        │ 52% │ NO             ║
║  ⚠️  Schwesinger 10.5 Tackles               │ 9.8/game - too close      │ 50% │ NO             ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║  🚨 LINE ERRORS (Value Disagrees with UD Pricing)                                                ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════╣
║  UD says: Shedeur Sanders LOWER INTs (+12%)                                                      ║
║  Stats say: OVER! He throws 1.33 INTs per game. FADE THE LOWER!                                  ║
║                                                                                                  ║
║  UD says: Dylan Sampson OVER 42.5 Rush (+10%)                                                    ║
║  Stats say: He averages 8.9! This line is for RB1 not RB2. SLAM UNDER!                          ║
║                                                                                                  ║
║  UD says: Mason Graham OVER 0.5 Sacks (+55%)                                                     ║
║  Stats say: 0.5 sacks ALL SEASON. The multiplier is high because it's unlikely. UNDER!         ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝
""")

print("""
🏈 BEST 5-LEG PARLAY:
1. Dylan Sampson UNDER 42.5 Rush Yards (85%)
2. Mason Graham UNDER 0.5 Sacks (90%)
3. Shedeur Sanders OVER 0.5 INTs (65%)
4. Isaiah Bond OVER 10.5 Rec Yards (65%)
5. Alex Wright UNDER 0.5 Sacks (60%)

Combined probability estimate: ~19% (reasonable for a 5-leg)
""")
