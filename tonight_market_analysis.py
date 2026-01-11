"""
Match our current calibrated picks to tonight's ACTUAL market slate.
Shows which picks carry into tonight's games and identifies new edges.
"""

# Our current SLAM/STRONG picks (from latest cheatsheet)
OUR_PICKS = {
    "SLAM": {
        "OG Anunoby": {"stat": "PTS", "line": 16.5, "dir": "O", "conf": 75},
        "Jamal Shead": {"stat": "PTS", "line": 7.5, "dir": "O", "conf": 75},
        "Giannis Antetokounmpo": {"stat": "PTS", "line": 27.5, "dir": "O", "conf": 75},
        "Keyonte George": {"stat": "PTS", "line": 25.5, "dir": "O", "conf": 75},
        "Lauri Markkanen": {"stat": "PTS", "line": 26.5, "dir": "O", "conf": 72},
    },
    "STRONG": {
        "OG Anunoby": {"stat": "PRA", "line": 25.5, "dir": "O", "conf": 75},
        "Giannis Antetokounmpo": {"stat": "PRA", "line": 42.5, "dir": "O", "conf": 66},
        "Victor Wembanyama": {"stat": "REB", "line": 10.5, "dir": "O", "conf": 66},
        "Jordan Clarkson": {"stat": "PTS", "line": 8.5, "dir": "O", "conf": 65},
        "Jalen Duren": {"stat": "REB", "line": 10.5, "dir": "O", "conf": 65},
        "Bam Adebayo": {"stat": "PRA", "line": 28.5, "dir": "O", "conf": 65},
        "Myles Turner": {"stat": "PRA", "line": 18.5, "dir": "O", "conf": 65},
        "Alperen Sengun": {"stat": "PTS", "line": 20.5, "dir": "O", "conf": 65},
    }
}

# Tonight's actual market lines
TONIGHT_SLATE = {
    "HOU @ BKN (5:00 PM CST)": {
        "Kevin Durant": {"PTS": 26.5, "PRA": 36.5, "REB": 5.5, "AST": 4.5},
        "Alperen Sengun": {"PTS": 20.5, "PRA": 36.5, "REB": 9.5, "AST": 6.5},
    },
    "MIA @ DET (6:00 PM CST)": {
        "Bam Adebayo": {"PTS": 16.5, "PRA": 27.5, "REB": 8.5, "AST": 2.5},
        "Jalen Duren": {"PTS": 17.5, "PRA": 29.5, "REB": 10.5, "AST": 1.5},
    },
    "PHI @ DAL (7:30 PM CST)": {
        "Joel Embiid": {"PTS": 25.5, "PRA": 37.5, "REB": 8.5, "AST": 3.5},
    },
    "BOS @ SAC (9:00 PM CST)": {
        "Jaylen Brown": {"PTS": 30.5, "PRA": 43.5, "REB": 6.5, "AST": 5.5},
    },
    "UTA @ LAC (9:30 PM CST)": {
        "Keyonte George": {"PTS": 25.5, "PRA": 36.5, "REB": 4.5, "AST": 6.5},
        "Lauri Markkanen": {"PTS": 26.5, "PRA": 34.5, "REB": 6.5, "AST": 1.5},
    },
}

print("=" * 90)
print("🎯 TONIGHT'S SLATE - OUR PICKS vs MARKET LINES")
print("=" * 90)
print()

# Find matches
matched_slam = {}
matched_strong = {}
available_slate = {}

print("📊 OUR SLAM PICKS (75%+ Confidence)")
print("-" * 90)

for player, pick_data in OUR_PICKS["SLAM"].items():
    found = False
    for game, players in TONIGHT_SLATE.items():
        if player in players:
            market_line = players[player].get(pick_data["stat"])
            if market_line:
                matched_slam[player] = {
                    "game": game,
                    "stat": pick_data["stat"],
                    "our_line": pick_data["line"],
                    "market_line": market_line,
                    "conf": pick_data["conf"],
                }
                print(f"  ✅ {player}")
                print(f"     Game: {game}")
                print(f"     Stat: {pick_data['stat']} OVER {pick_data['line']} (our assessment)")
                print(f"     Market: {pick_data['stat']} OVER {market_line}")
                diff = market_line - pick_data["line"]
                if diff < 0:
                    print(f"     📈 EDGE: Line moved DOWN by {abs(diff):.1f} pts → BULLISH")
                elif diff > 0:
                    print(f"     📉 EDGE: Line moved UP by {diff:.1f} pts → CAUTIOUS")
                else:
                    print(f"     ➡️  EDGE: Line unchanged")
                print(f"     Confidence: {pick_data['conf']}%")
                print()
                found = True
                break
    
    if not found:
        print(f"  ⭐ {player} - NOT ON TONIGHT'S SLATE (different game)")
        print()

print("\n💪 OUR STRONG PICKS (60-67% Confidence)")
print("-" * 90)

for player, pick_data in OUR_PICKS["STRONG"].items():
    found = False
    for game, players in TONIGHT_SLATE.items():
        if player in players:
            market_line = players[player].get(pick_data["stat"])
            if market_line:
                matched_strong[player] = {
                    "game": game,
                    "stat": pick_data["stat"],
                    "our_line": pick_data["line"],
                    "market_line": market_line,
                    "conf": pick_data["conf"],
                }
                print(f"  💪 {player}")
                print(f"     Game: {game}")
                print(f"     Stat: {pick_data['stat']} OVER {pick_data['line']} (our assessment)")
                print(f"     Market: {pick_data['stat']} OVER {market_line}")
                diff = market_line - pick_data["line"]
                if diff < 0:
                    print(f"     📈 EDGE: Line moved DOWN by {abs(diff):.1f} pts → BULLISH")
                elif diff > 0:
                    print(f"     📉 EDGE: Line moved UP by {diff:.1f} pts → CAUTIOUS")
                else:
                    print(f"     ➡️  EDGE: Line unchanged")
                print(f"     Confidence: {pick_data['conf']}%")
                print()
                found = True
                break
    
    if not found:
        print(f"  ⭐ {player} - NOT ON TONIGHT'S SLATE (different game)")
        print()

print("\n" + "=" * 90)
print("📋 TONIGHT'S AVAILABLE PLAYS NOT YET RATED")
print("=" * 90)
print()

# Show all available picks that we haven't rated yet
all_slate_players = set()
for game, players in TONIGHT_SLATE.items():
    for player in players.keys():
        all_slate_players.add(player)

our_rated_players = set(OUR_PICKS["SLAM"].keys()) | set(OUR_PICKS["STRONG"].keys())

for player in sorted(all_slate_players - our_rated_players):
    for game, players in TONIGHT_SLATE.items():
        if player in players:
            lines = players[player]
            print(f"🔍 {player} ({game})")
            print(f"   PTS: {lines['PTS']} | PRA: {lines['PRA']} | REB: {lines['REB']} | AST: {lines['AST']}")
            print()
            break

print("\n" + "=" * 90)
print("📊 SUMMARY")
print("=" * 90)

print(f"\n🔥 SLAM picks active tonight: {len(matched_slam)}")
for player, data in matched_slam.items():
    print(f"   ✅ {player} - {data['stat']} O {data['market_line']}")

print(f"\n💪 STRONG picks active tonight: {len(matched_strong)}")
for player, data in matched_strong.items():
    print(f"   💪 {player} - {data['stat']} O {data['market_line']}")

print(f"\n⭐ Total picks on tonight's slate: {len(matched_slam) + len(matched_strong)}")
print(f"🎮 Total available slate players: {len(all_slate_players)}")
print(f"📈 Unrated players available: {len(all_slate_players - our_rated_players)}")

print("\n🚀 STATUS: Ready for tonight's deployment!")
print("   Most recent calibration: CHEATSHEET_JAN01_20260101_142534.txt (75% SLAMs active)")
