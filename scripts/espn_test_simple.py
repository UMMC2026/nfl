"""Simple ESPN data fetch test using urllib."""
import json
import urllib.request
import ssl

# Disable SSL verification for Python 3.14 compatibility
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

def fetch_json(url):
    """Fetch JSON from URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read())

def main():
    print("=" * 60)
    print("ESPN NFL DATA TEST - WEEK 17 2024")
    print("=" * 60)
    
    # Test 1: Get stat leaders
    print("\n🏈 TOP 2024 NFL STAT LEADERS")
    print("-" * 40)
    
    data = fetch_json(f"{ESPN_BASE}/leaders")
    for cat in data.get("leaders", [])[:5]:
        print(f"\n{cat.get('name', 'Unknown')}:")
        for i, leader in enumerate(cat.get("leaders", [])[:3], 1):
            athlete = leader.get("athlete", {})
            name = athlete.get("displayName", "?")
            team = athlete.get("team", {}).get("abbreviation", "?")
            value = leader.get("displayValue", "?")
            print(f"  {i}. {name} ({team}): {value}")
    
    # Test 2: Get team rosters for Week 17 games
    print("\n\n👥 TEAM ROSTERS (Skill Positions)")
    print("-" * 40)
    
    teams = {"PIT": 23, "CLE": 5, "JAX": 30, "IND": 11}
    key_positions = {"QB", "RB", "WR", "TE"}
    
    for team, team_id in teams.items():
        print(f"\n{team} ROSTER:")
        url = f"{ESPN_BASE}/teams/{team_id}/roster"
        data = fetch_json(url)
        
        found = []
        for group in data.get("athletes", []):
            for athlete in group.get("items", []):
                pos = athlete.get("position", {}).get("abbreviation", "")
                if pos not in key_positions:
                    continue
                
                name = athlete.get("fullName", "?")
                jersey = athlete.get("jersey", "?")
                status = athlete.get("status", {}).get("name", "Active")
                
                # Injury
                injuries = athlete.get("injuries", [])
                injury = ""
                if injuries:
                    injury = f" [{injuries[0].get('status', '')}]"
                
                found.append((pos, jersey, name, status, injury))
        
        # Sort by position
        pos_order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}
        found.sort(key=lambda x: (pos_order.get(x[0], 99), x[1]))
        
        for pos, jersey, name, status, injury in found[:12]:
            status_icon = "✓" if status == "Active" else "⚠" if "Out" not in status else "✗"
            print(f"  {status_icon} #{jersey} {name} ({pos}) - {status}{injury}")
    
    # Test 3: Get scoreboard
    print("\n\n📅 WEEK 17 SCOREBOARD")
    print("-" * 40)
    
    data = fetch_json(f"{ESPN_BASE}/scoreboard")
    for event in data.get("events", []):
        name = event.get("shortName", "?")
        status = event.get("status", {}).get("type", {}).get("description", "?")
        
        # Scores
        comps = event.get("competitions", [{}])[0].get("competitors", [])
        if len(comps) >= 2:
            home = comps[0]
            away = comps[1]
            score = f"{away.get('score', '0')}-{home.get('score', '0')}"
            print(f"  {name}: {score} ({status})")
    
    print("\n" + "=" * 60)
    print("✓ ESPN DATA FETCH COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
