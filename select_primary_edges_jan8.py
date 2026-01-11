# -*- coding: utf-8 -*-
"""
PRIMARY EDGE SELECTION - ONE PER PLAYER
Select the single best edge for each player from qualified picks
"""

import json
from pathlib import Path

def main():
    print("\n" + "="*80)
    print("PRIMARY EDGE SELECTION - ONE PER PLAYER")
    print("="*80 + "\n")
    
    # Load enhanced data
    enhanced_file = Path("outputs/jan8_complete_enhanced.json")
    with open(enhanced_file) as f:
        data = json.load(f)
    
    # Filter qualified picks
    qualified = [p for p in data["picks"] if p["qualified"]]
    
    print(f"Total qualified picks: {len(qualified)}\n")
    
    # Group by player
    by_player = {}
    for pick in qualified:
        player = pick["player"]
        if player not in by_player:
            by_player[player] = []
        by_player[player].append(pick)
    
    # Select best edge per player
    primary_edges = []
    
    for player, picks in sorted(by_player.items()):
        # Sort by probability DESC
        picks.sort(key=lambda x: -x["final_prob"])
        best = picks[0]
        
        primary_edges.append(best)
        
        print(f"{player:20} -> {best['stat']:10} {best['line']:5}+ [{best['final_prob']:.0%}]")
        if best['matchup_reason']:
            print(f"{'':23} {best['matchup_reason']}")
        
        # Show alternatives
        if len(picks) > 1:
            print(f"{'':23} Alternatives: ", end="")
            alts = [f"{p['stat']} {p['line']}+ [{p['final_prob']:.0%}]" for p in picks[1:]]
            print(", ".join(alts))
        print()
    
    # Save primary edges
    output = {
        "date": data["date"],
        "games": data["games"],
        "primary_edges": primary_edges,
        "total_players": len(by_player)
    }
    
    output_path = Path("outputs/jan8_primary_edges_complete.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print("="*80)
    print(f"PRIMARY EDGES SELECTED!")
    print(f"Total players: {len(by_player)}")
    print(f"Total primary edges: {len(primary_edges)}")
    print(f"Saved to: {output_path}")
    
    # Game breakdown
    print(f"\n{'='*80}")
    print("BREAKDOWN BY GAME\n")
    
    by_game = {}
    for edge in primary_edges:
        game = edge["game"]
        if game not in by_game:
            by_game[game] = []
        by_game[game].append(edge)
    
    for game, edges in sorted(by_game.items()):
        print(f"\n{game} ({len(edges)} players)")
        for edge in sorted(edges, key=lambda x: -x["final_prob"]):
            print(f"   {edge['player']:20} {edge['stat']:10} {edge['line']:5}+ [{edge['final_prob']:.0%}]")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
