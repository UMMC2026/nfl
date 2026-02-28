# Auto-update NBA active player list using ESPN API (reliable, no blocking)
from engine.roster_gate import build_active_roster_map

def update_active_players_py():
    """Fetch active NBA players from ESPN API and write to nba_active_players.py"""
    print("[*] Fetching NBA rosters from ESPN API...")
    
    try:
        roster_map = build_active_roster_map("NBA")
        
        if not roster_map:
            print("[!] Failed to fetch rosters (returned empty map)")
            return
        
        names = sorted(set(roster_map.keys()))
        
        print(f"[OK] Fetched {len(names)} active players")
        
        with open('nba_active_players.py', 'w', encoding='utf-8') as f:
            f.write('# Auto-generated NBA active player list (via ESPN API)\n')
            f.write(f'# Generated: {len(names)} players\n')
            f.write('ACTIVE_NBA_PLAYERS = set([\n')
            for name in names:
                f.write(f'    "{name}",\n')
            f.write('])\n')
        
        print(f"[OK] Wrote {len(names)} players to nba_active_players.py")
        
    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    update_active_players_py()
