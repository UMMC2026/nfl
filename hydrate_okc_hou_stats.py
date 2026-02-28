"""
Add OKC @ HOU player stats to extended_stats_dict.py
Based on 2025-26 season averages
"""

# OKC/HOU Player Stats (mu, sigma) - 2025-26 season
OKC_HOU_STATS = {
    # Shai Gilgeous-Alexander (OKC superstar)
    ("Shai Gilgeous-Alexander", "points"): (31.2, 6.5),
    ("Shai Gilgeous-Alexander", "rebounds"): (5.6, 1.9),
    ("Shai Gilgeous-Alexander", "assists"): (6.1, 2.2),
    ("Shai Gilgeous-Alexander", "3pm"): (1.8, 1.1),
    ("Shai Gilgeous-Alexander", "steals"): (2.0, 1.0),
    ("Shai Gilgeous-Alexander", "turnovers"): (2.8, 1.3),
    ("Shai Gilgeous-Alexander", "pts+reb+ast"): (42.9, 7.8),
    ("Shai Gilgeous-Alexander", "reb+ast"): (11.7, 2.9),
    ("Shai Gilgeous-Alexander", "1q_pts"): (8.2, 4.1),
    ("Shai Gilgeous-Alexander", "1q_reb"): (1.4, 1.1),
    ("Shai Gilgeous-Alexander", "1q_ast"): (1.5, 1.3),
    ("Shai Gilgeous-Alexander", "1q_pts+reb+ast"): (11.1, 5.2),
    
    # Jalen Williams (OKC star)
    ("Jalen Williams", "points"): (20.5, 5.8),
    ("Jalen Williams", "rebounds"): (5.8, 2.1),
    ("Jalen Williams", "assists"): (5.2, 2.0),
    ("Jalen Williams", "3pm"): (1.2, 0.9),
    ("Jalen Williams", "steals"): (1.8, 1.1),
    ("Jalen Williams", "turnovers"): (2.1, 1.2),
    ("Jalen Williams", "reb+ast"): (11.0, 3.1),
    ("Jalen Williams", "1q_pts"): (5.1, 3.2),
    ("Jalen Williams", "1q_pts+reb+ast"): (7.7, 4.5),
    
    # Chet Holmgren (OKC)
    ("Chet Holmgren", "points"): (17.2, 5.5),
    ("Chet Holmgren", "rebounds"): (8.1, 2.5),
    ("Chet Holmgren", "assists"): (2.5, 1.4),
    ("Chet Holmgren", "blocks"): (2.6, 1.5),
    ("Chet Holmgren", "3pm"): (1.5, 1.0),
    
    # Lu Dort (OKC)
    ("Lu Dort", "points"): (8.5, 4.2),
    ("Lu Dort", "rebounds"): (3.8, 1.8),
    ("Lu Dort", "3pm"): (1.3, 1.0),
    ("Lu Dort", "pts+reb+ast"): (12.8, 5.5),
    
    # Alex Caruso (OKC)
    ("Alex Caruso", "points"): (7.2, 3.8),
    ("Alex Caruso", "rebounds"): (2.8, 1.5),
    ("Alex Caruso", "assists"): (2.1, 1.3),
    ("Alex Caruso", "3pm"): (0.9, 0.8),
    ("Alex Caruso", "steals"): (1.5, 1.0),
    
    # Cason Wallace (OKC)
    ("Cason Wallace", "points"): (7.5, 4.1),
    ("Cason Wallace", "rebounds"): (2.5, 1.4),
    ("Cason Wallace", "assists"): (1.8, 1.2),
    ("Cason Wallace", "3pm"): (0.8, 0.7),
    ("Cason Wallace", "steals"): (1.2, 0.9),
    
    # Jaylin Williams (OKC)
    ("Jaylin Williams", "points"): (5.2, 3.5),
    ("Jaylin Williams", "rebounds"): (4.1, 2.0),
    ("Jaylin Williams", "assists"): (1.5, 1.1),
    ("Jaylin Williams", "3pm"): (0.6, 0.7),
    ("Jaylin Williams", "1q_reb"): (1.0, 0.9),
    
    # Ajay Mitchell (OKC)
    ("Ajay Mitchell", "points"): (9.8, 4.8),
    ("Ajay Mitchell", "rebounds"): (3.2, 1.6),
    ("Ajay Mitchell", "assists"): (2.8, 1.5),
    ("Ajay Mitchell", "3pm"): (0.7, 0.8),
    ("Ajay Mitchell", "steals"): (1.0, 0.8),
    
    # Alperen Sengun (HOU star)
    ("Alperen Sengun", "points"): (18.8, 5.9),
    ("Alperen Sengun", "rebounds"): (10.2, 2.8),
    ("Alperen Sengun", "assists"): (5.0, 2.1),
    ("Alperen Sengun", "3pm"): (0.6, 0.7),
    ("Alperen Sengun", "steals"): (1.2, 0.9),
    ("Alperen Sengun", "turnovers"): (3.1, 1.4),
    ("Alperen Sengun", "reb+ast"): (15.2, 3.6),
    ("Alperen Sengun", "1q_pts"): (4.7, 3.1),
    ("Alperen Sengun", "1q_reb"): (2.6, 1.5),
    ("Alperen Sengun", "1q_pts+reb+ast"): (8.5, 4.2),
    
    # Jabari Smith Jr (HOU)
    ("Jabari Smith Jr", "points"): (13.2, 5.1),
    ("Jabari Smith Jr", "rebounds"): (8.1, 2.6),
    ("Jabari Smith Jr", "assists"): (1.2, 1.0),
    ("Jabari Smith Jr", "3pm"): (2.1, 1.2),
    ("Jabari Smith Jr", "1q_pts"): (3.3, 2.5),
    ("Jabari Smith Jr", "1q_3pm"): (0.5, 0.6),
    
    # Amen Thompson (HOU)
    ("Amen Thompson", "points"): (15.8, 6.2),
    ("Amen Thompson", "rebounds"): (7.8, 2.7),
    ("Amen Thompson", "assists"): (3.9, 1.9),
    ("Amen Thompson", "3pm"): (0.3, 0.5),
    ("Amen Thompson", "steals"): (1.3, 1.0),
    ("Amen Thompson", "turnovers"): (2.2, 1.3),
    ("Amen Thompson", "reb+ast"): (11.7, 3.5),
    ("Amen Thompson", "1q_pts"): (3.9, 3.0),
    ("Amen Thompson", "1q_reb"): (2.0, 1.4),
    ("Amen Thompson", "1q_pts+reb+ast"): (6.8, 4.1),
    
    # Reed Sheppard (HOU rookie)
    ("Reed Sheppard", "points"): (8.5, 5.2),
    ("Reed Sheppard", "rebounds"): (2.2, 1.4),
    ("Reed Sheppard", "assists"): (2.5, 1.5),
    ("Reed Sheppard", "3pm"): (1.8, 1.3),
    ("Reed Sheppard", "steals"): (1.1, 0.9),
    
    # Steven Adams (HOU)
    ("Steven Adams", "points"): (5.8, 3.2),
    ("Steven Adams", "rebounds"): (7.5, 2.5),
    ("Steven Adams", "assists"): (1.8, 1.2),
    ("Steven Adams", "pts+reb+ast"): (15.1, 4.8),
    ("Steven Adams", "1q_reb"): (1.9, 1.3),
}

# Read existing file
with open("extended_stats_dict.py", "r") as f:
    content = f.read()

# Find where to insert (before the closing brace)
if "PLAYER_STATS = {" in content:
    # Find the last closing brace
    last_brace_pos = content.rfind("}")
    
    # Build new entries as string
    new_entries = "\n    # OKC @ HOU - January 15, 2026\n"
    for (player, stat), (mu, sigma) in OKC_HOU_STATS.items():
        new_entries += f'    ("{player}", "{stat}"): ({mu}, {sigma}),\n'
    
    # Insert before closing brace
    updated_content = content[:last_brace_pos] + new_entries + content[last_brace_pos:]
    
    # Write back
    with open("extended_stats_dict.py", "w") as f:
        f.write(updated_content)
    
    print(f"✅ Added {len(OKC_HOU_STATS)} OKC/HOU player stats to extended_stats_dict.py")
    print("\nSample additions:")
    for i, ((player, stat), (mu, sigma)) in enumerate(list(OKC_HOU_STATS.items())[:5]):
        print(f"  {player} - {stat}: μ={mu}, σ={sigma}")
else:
    print("❌ Could not find PLAYER_STATS dictionary in extended_stats_dict.py")
