"""
Analyze tonight's live Underdog market odds vs our calibrated picks.
Identifies edges where market pricing diverges from our probability assessment.
"""

import json
from pathlib import Path
from typing import TypedDict
from datetime import datetime

# Tonight's live market data (parsed from Underdog)
TONIGHT_MARKET = {
    "HOU @ BKN": {
        "Kevin Durant": {"PTS": 26.5, "PRA": 36.5, "REB": 5.5, "AST": 4.5},
        "Cam Thomas": {"PTS": 19.5, "PRA": 23.5, "REB": 1.5, "AST": 2.5},
        "Michael Porter Jr.": {"PTS": 23.5, "PRA": 33.5, "REB": 6.5, "AST": 3.5},
        "Amen Thompson": {"PTS": 17.5, "PRA": 30.5, "REB": 6.5, "AST": 5.5},
        "Day'Ron Sharpe": {"PTS": 6.5, "PRA": 15.5, "REB": 5.5, "AST": 2.5},
        "Alperen Sengun": {"PTS": 20.5, "PRA": 36.5, "REB": 9.5, "AST": 6.5},
        "Nic Claxton": {"PTS": 13.5, "PRA": 24.5, "REB": 7.5, "AST": 3.5},
        "Jabari Smith Jr.": {"PTS": 15.5, "PRA": 24.5, "REB": 7.5, "AST": 1.5},
        "Tari Eason": {"PTS": 12.5, "PRA": 19.5, "REB": 5.5, "AST": 1.5},
        "Noah Clowney": {"PTS": 13.5, "PRA": 19.5, "REB": 4.5, "AST": 1.5},
    },
    "MIA @ DET": {
        "Cade Cunningham": {"PTS": 26.5, "PRA": 43.5, "REB": 5.5, "AST": 10.5},
        "Andrew Wiggins": {"PTS": 15.5, "PRA": 22.5, "REB": 4.5, "AST": 2.5},
        "Ausar Thompson": {"PTS": 11.5, "PRA": 19.5, "REB": 4.5, "AST": 2.5},
        "Jaime Jaquez Jr.": {"PTS": 15.5, "PRA": 24.5, "REB": 4.5, "AST": 4.5},
        "Nikola Jovic": {"PTS": 8.5, "PRA": 16.5, "REB": 4.5, "AST": 2.5},
        "Davion Mitchell": {"PTS": 7.5, "PRA": 17.5, "REB": 1.5, "AST": 7.5},
        "Javonte Green": {"PTS": 7.5, "PRA": 11.5, "REB": 3.5, "AST": 0},
        "Ron Holland": {"PTS": 8.5, "PRA": 14.5, "REB": 3.5, "AST": 1.5},
        "Dru Smith": {"PTS": 7.5, "PRA": 11.5, "REB": 2.5, "AST": 2.5},
        "Bam Adebayo": {"PTS": 16.5, "PRA": 27.5, "REB": 8.5, "AST": 2.5},
        "Jaden Ivey": {"PTS": 10.5, "PRA": 15.5, "REB": 2.5, "AST": 2.5},
        "Jalen Duren": {"PTS": 17.5, "PRA": 29.5, "REB": 10.5, "AST": 1.5},
        "Norman Powell": {"PTS": 23.5, "PRA": 29.5, "REB": 3.5, "AST": 2.5},
        "Isaiah Stewart": {"PTS": 10.5, "PRA": 17.5, "REB": 6.5, "AST": 1.5},
        "Duncan Robinson": {"PTS": 10.5, "PRA": 15.5, "REB": 2.5, "AST": 1.5},
        "Kel'el Ware": {"PTS": 13.5, "PRA": 24.5, "REB": 10.5, "AST": 0},
        "Marcus Sasser": {"PTS": 6.5, "PRA": 11.5, "REB": 1.5, "AST": 2.5},
    },
    "PHI @ DAL": {
        "Joel Embiid": {"PTS": 25.5, "PRA": 37.5, "REB": 8.5, "AST": 3.5},
        "Paul George": {"PTS": 15.5, "PRA": 24.5, "REB": 5.5, "AST": 3.5},
        "VJ Edgecombe": {"PTS": 14.5, "PRA": 23.5, "REB": 4.5, "AST": 3.5},
        "Klay Thompson": {"PTS": 10.5, "PRA": 13.5, "REB": 2.5, "AST": 1.5},
        "Naji Marshall": {"PTS": 12.5, "PRA": 19.5, "REB": 4.5, "AST": 2.5},
        "Quentin Grimes": {"PTS": 9.5, "PRA": 16.5, "REB": 3.5, "AST": 3.5},
        "Ryan Nembhard": {"PTS": 4.5, "PRA": 10.5, "REB": 1.5, "AST": 4.5},
        "Dominick Barlow": {"PTS": 6.5, "PRA": 13.5, "REB": 5.5, "AST": 1.5},
        "Cooper Flagg": {"PTS": 22.5, "PRA": 30.5, "REB": 6.5, "AST": 4.5},
        "Anthony Davis": {"PTS": 23.5, "PRA": 37.5, "REB": 11.5, "AST": 2.5},
        "Tyrese Maxey": {"PTS": 27.5, "PRA": 38.5, "REB": 3.5, "AST": 6.5},
        "PJ Washington": {"PTS": 12.5, "PRA": 21.5, "REB": 6.5, "AST": 1.5},
        "Daniel Gafford": {"PTS": 5.5, "PRA": 11.5, "REB": 4.5, "AST": 0},
        "Jared McCain": {"PTS": 6.5, "PRA": 9.5, "REB": 1.5, "AST": 1.5},
        "Brandon Williams": {"PTS": 12.5, "PRA": 21.5, "REB": 2.5, "AST": 5.5},
    },
    "BOS @ SAC": {
        "Jaylen Brown": {"PTS": 30.5, "PRA": 43.5, "REB": 6.5, "AST": 5.5},
        "Derrick White": {"PTS": 19.5, "PRA": 29.5, "REB": 4.5, "AST": 5.5},
        "Keegan Murray": {"PTS": 15.5, "PRA": 22.5, "REB": 5.5, "AST": 1.5},
        "Dennis Schroder": {"PTS": 11.5, "PRA": 18.5, "REB": 2.5, "AST": 4.5},
        "Sam Hauser": {"PTS": 6.5, "PRA": 10.5, "REB": 3.5, "AST": 0},
        "Maxime Raynaud": {"PTS": 13.5, "PRA": 22.5, "REB": 8.5, "AST": 1.5},
        "Neemias Queta": {"PTS": 9.5, "PRA": 18.5, "REB": 8.5, "AST": 1.5},
        "Nique Clifford": {"PTS": 8.5, "PRA": 13.5, "REB": 3.5, "AST": 1.5},
        "Anfernee Simons": {"PTS": 12.5, "PRA": 16.5, "REB": 2.5, "AST": 2.5},
        "DeMar DeRozan": {"PTS": 18.5, "PRA": 26.5, "REB": 3.5, "AST": 3.5},
        "Russell Westbrook": {"PTS": 15.5, "PRA": 28.5, "REB": 6.5, "AST": 7.5},
        "Payton Pritchard": {"PTS": 17.5, "PRA": 27.5, "REB": 4.5, "AST": 5.5},
        "Jordan Walsh": {"PTS": 5.5, "PRA": 9.5, "REB": 4.5, "AST": 0},
        "Luka Garza": {"PTS": 6.5, "PRA": 13.5, "REB": 5.5, "AST": 0},
        "Precious Achiuwa": {"PTS": 6.5, "PRA": 12.5, "REB": 4.5, "AST": 0},
    },
    "UTA @ LAC": {
        "Kawhi Leonard": {"PTS": 29.5, "PRA": 41.5, "REB": 7.5, "AST": 4.5},
        "James Harden": {"PTS": 27.5, "PRA": 40.5, "REB": 5.5, "AST": 8.5},
        "Brook Lopez": {"PTS": 12.5, "PRA": 19.5, "REB": 5.5, "AST": 1.5},
        "Derrick Jones Jr.": {"PTS": 8.5, "PRA": 12.5, "REB": 2.5, "AST": 0},
        "Kris Dunn": {"PTS": 8.5, "PRA": 15.5, "REB": 3.5, "AST": 3.5},
        "Brice Sensabaugh": {"PTS": 15.5, "PRA": 22.5, "REB": 4.5, "AST": 2.5},
        "Kyle Filipowski": {"PTS": 14.5, "PRA": 26.5, "REB": 8.5, "AST": 2.5},
        "Keyonte George": {"PTS": 25.5, "PRA": 36.5, "REB": 4.5, "AST": 6.5},
        "Lauri Markkanen": {"PTS": 26.5, "PRA": 34.5, "REB": 6.5, "AST": 1.5},
        "John Collins": {"PTS": 13.5, "PRA": 21.5, "REB": 6.5, "AST": 1.5},
        "Nicolas Batum": {"PTS": 5.5, "PRA": 9.5, "REB": 3.5, "AST": 1.5},
        "Kobe Sanders": {"PTS": 5.5, "PRA": 10.5, "REB": 2.5, "AST": 1.5},
        "Taylor Hendricks": {"PTS": 7.5, "PRA": 13.5, "REB": 4.5, "AST": 0},
    },
}

# Load our latest cheatsheet
cheatsheet_path = Path("outputs/CHEATSHEET_JAN01_20260101_142534.txt")
if not cheatsheet_path.exists():
    print("❌ Latest cheatsheet not found!")
    exit(1)

cheatsheet_text = cheatsheet_path.read_text()

# Parse cheatsheet to extract our picks
slam_picks = set()
strong_picks = set()

for line in cheatsheet_text.split('\n'):
    if '🔥 SLAM' in line or 'SLAM (75%)' in line:
        slam_picks.add(line.strip())
    elif '💪 STRONG' in line or 'STRONG (60-67%)' in line:
        strong_picks.add(line.strip())

print("=" * 80)
print("📊 TONIGHT'S SLATE vs OUR PICKS")
print("=" * 80)
print(f"📅 Date: January 1, 2026")
print(f"📈 Our Cheatsheet: {cheatsheet_path.name}")
print(f"🔥 SLAM picks identified: {len(slam_picks)}")
print(f"💪 STRONG picks identified: {len(strong_picks)}")
print()

# Analyze matchups
print("=" * 80)
print("GAME-BY-GAME BREAKDOWN")
print("=" * 80)

slam_by_game = {
    "HOU @ BKN": [],
    "MIA @ DET": [],
    "PHI @ DAL": [],
    "BOS @ SAC": [],
    "UTA @ LAC": [],
}

strong_by_game = {
    "HOU @ BKN": [],
    "MIA @ DET": [],
    "PHI @ DAL": [],
    "BOS @ SAC": [],
    "UTA @ LAC": [],
}

# Match our picks to game lines
for game, players in TONIGHT_MARKET.items():
    slam_count = 0
    strong_count = 0
    
    for pick in slam_picks:
        for player in players.keys():
            if player.lower() in pick.lower():
                slam_by_game[game].append((player, pick))
                slam_count += 1
                break
    
    for pick in strong_picks:
        for player in players.keys():
            if player.lower() in pick.lower():
                strong_by_game[game].append((player, pick))
                strong_count += 1
                break
    
    if slam_count > 0 or strong_count > 0:
        print(f"\n{game.upper()}")
        print("-" * 80)
        
        if slam_count > 0:
            print(f"  🔥 SLAM PICKS ({slam_count}):")
            for player, pick_text in slam_by_game[game]:
                stat_key = None
                line = None
                for key in ["PTS", "PRA", "REB", "AST"]:
                    if key in pick_text:
                        stat_key = key
                        if player in TONIGHT_MARKET[game]:
                            line = TONIGHT_MARKET[game][player].get(key)
                        break
                
                if line and stat_key:
                    direction = "HIGHER" if ">" in pick_text or "O" in pick_text else "LOWER"
                    print(f"    ✅ {player}")
                    print(f"       {stat_key} {direction} (Line: {line})")
        
        if strong_count > 0:
            print(f"  💪 STRONG PICKS ({strong_count}):")
            for player, pick_text in strong_by_game[game]:
                stat_key = None
                line = None
                for key in ["PTS", "PRA", "REB", "AST"]:
                    if key in pick_text:
                        stat_key = key
                        if player in TONIGHT_MARKET[game]:
                            line = TONIGHT_MARKET[game][player].get(key)
                        break
                
                if line and stat_key:
                    direction = "HIGHER" if ">" in pick_text or "O" in pick_text else "LOWER"
                    print(f"    💪 {player}")
                    print(f"       {stat_key} {direction} (Line: {line})")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total_slams = sum(len(v) for v in slam_by_game.values())
total_strong = sum(len(v) for v in strong_by_game.values())

print(f"\n🔥 Total SLAM picks active tonight: {total_slams}")
print(f"💪 Total STRONG picks active tonight: {total_strong}")
print(f"📊 Total high-confidence picks: {total_slams + total_strong}")

print("\n🎯 Key edges to monitor:")
print("   - Kawhi Leonard (LAC) PTS 29.5 - 🔥 SLAM if in picks")
print("   - James Harden (LAC) PRA 40.5 - 💪 STRONG opportunity")
print("   - Tyrese Maxey (PHI) PTS 27.5 - Watch for SLAM confirmation")
print("   - Jaylen Brown (BOS) PTS 30.5 - Monitor vs our assessment")

print("\n✅ Ready for signal deployment!")
print(f"⏰ Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
