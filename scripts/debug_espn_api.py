"""Debug ESPN API response structure to fix parsing logic"""

import requests
import json

# Test with LAL (Lakers) - ESPN team ID 13
team_id = 13
team_abbr = "LAL"

url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"

print(f"Fetching {team_abbr} roster from ESPN...")
print(f"URL: {url}")
print()

try:
    response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    data = response.json()
    
    print("=" * 70)
    print("RESPONSE STRUCTURE")
    print("=" * 70)
    print()
    
    # Print top-level keys
    print("Top-level keys:")
    for key in data.keys():
        value_type = type(data[key]).__name__
        if isinstance(data[key], list):
            print(f"  {key}: {value_type} (length={len(data[key])})")
        elif isinstance(data[key], dict):
            print(f"  {key}: {value_type} (keys={list(data[key].keys())})")
        else:
            print(f"  {key}: {value_type}")
    print()
    
    # Focus on 'athletes' key (expected to contain roster)
    if "athletes" in data:
        athletes = data["athletes"]
        print(f"'athletes' structure: {type(athletes).__name__}")
        
        if isinstance(athletes, list):
            print(f"  Length: {len(athletes)}")
            print()
            
            if len(athletes) > 0:
                print("First element structure:")
                first = athletes[0]
                print(f"  Type: {type(first).__name__}")
                if isinstance(first, dict):
                    print(f"  Keys: {list(first.keys())}")
                    print()
                    
                    # Check for nested 'items'
                    if "items" in first:
                        items = first["items"]
                        print(f"  'items' structure: {type(items).__name__}")
                        if isinstance(items, list) and len(items) > 0:
                            print(f"    Length: {len(items)}")
                            print()
                            print("    First item keys:")
                            print(f"      {list(items[0].keys())}")
                            print()
                            print("    First item sample:")
                            print(f"      fullName: {items[0].get('fullName')}")
                            print(f"      displayName: {items[0].get('displayName')}")
                            print(f"      position: {items[0].get('position')}")
                    else:
                        print("  No 'items' key found")
                        print()
                        print("  Full first element:")
                        print(json.dumps(first, indent=2)[:500])
        
        print()
        print("=" * 70)
        print("FULL RESPONSE (first 2000 chars)")
        print("=" * 70)
        print(json.dumps(data, indent=2)[:2000])
    
    else:
        print("❌ No 'athletes' key in response!")
        print()
        print("Full response:")
        print(json.dumps(data, indent=2))

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
