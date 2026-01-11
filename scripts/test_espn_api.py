"""Test ESPN API endpoints to find working stats sources."""
import httpx
import json

client = httpx.Client(timeout=30, follow_redirects=True)

# Get 2024 season leaders from core API
url = 'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2024/types/2/leaders'
resp = client.get(url)
data = resp.json()

print('Categories available:')
for cat in data.get('categories', []):
    print(f"  - {cat.get('name', 'unknown')}")
    # Look at structure
    leaders = cat.get('leaders', [])
    if leaders and isinstance(leaders, list):
        print(f"    Leaders is a list with {len(leaders)} items")
        if leaders:
            print(f"    First leader keys: {list(leaders[0].keys())[:5]}")

# Get rushing leaders
print('\n=== RUSHING LEADERS ===')
for cat in data.get('categories', []):
    if cat.get('name') == 'rushingYards':
        leaders = cat.get('leaders', [])
        for item in leaders[:5]:
            athlete_ref = item.get('athlete', {}).get('$ref', '')
            value = item.get('value', 0)
            if athlete_ref:
                resp3 = client.get(athlete_ref)
                athlete = resp3.json()
                team_ref = athlete.get('team', {}).get('$ref', '')
                team_abbr = ""
                if team_ref:
                    team_resp = client.get(team_ref)
                    team_abbr = team_resp.json().get('abbreviation', '')
                print(f"  {athlete.get('displayName')} ({team_abbr}) - {value} yards")

print('\n=== PASSING LEADERS ===')
for cat in data.get('categories', []):
    if cat.get('name') == 'passingYards':
        leaders = cat.get('leaders', [])
        for item in leaders[:5]:
            athlete_ref = item.get('athlete', {}).get('$ref', '')
            value = item.get('value', 0)
            if athlete_ref:
                resp3 = client.get(athlete_ref)
                athlete = resp3.json()
                team_ref = athlete.get('team', {}).get('$ref', '')
                team_abbr = ""
                if team_ref:
                    team_resp = client.get(team_ref)
                    team_abbr = team_resp.json().get('abbreviation', '')
                print(f"  {athlete.get('displayName')} ({team_abbr}) - {value} yards")

print('\n=== RECEIVING LEADERS ===')
for cat in data.get('categories', []):
    if cat.get('name') == 'receivingYards':
        leaders = cat.get('leaders', [])
        for item in leaders[:5]:
            athlete_ref = item.get('athlete', {}).get('$ref', '')
            value = item.get('value', 0)
            if athlete_ref:
                resp3 = client.get(athlete_ref)
                athlete = resp3.json()
                team_ref = athlete.get('team', {}).get('$ref', '')
                team_abbr = ""
                if team_ref:
                    team_resp = client.get(team_ref)
                    team_abbr = team_resp.json().get('abbreviation', '')
                print(f"  {athlete.get('displayName')} ({team_abbr}) - {value} yards")

client.close()
print('\n✓ Done!')
