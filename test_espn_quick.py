"""Quick ESPN test using urllib only."""
import json
import ssl
import urllib.request

# SSL context for Python 3.14
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return json.loads(resp.read())

print("Testing ESPN API...")

# Test 1: Leaders
url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/leaders"
data = fetch(url)
print(f"\n2024 NFL STAT LEADERS:")
for cat in data.get("leaders", [])[:3]:
    print(f"\n{cat.get('name')}:")
    for leader in cat.get("leaders", [])[:3]:
        athlete = leader.get("athlete", {})
        print(f"  {athlete.get('displayName')} ({athlete.get('team', {}).get('abbreviation')}): {leader.get('displayValue')}")

# Test 2: Week schedule
url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week=17"
data = fetch(url)
print(f"\n\nWEEK 17 GAMES ({len(data.get('events', []))} total):")
for event in data.get("events", [])[:6]:
    print(f"  {event.get('shortName')}: {event.get('status', {}).get('type', {}).get('description')}")

# Test 3: Team roster
url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/11/roster"  # IND
data = fetch(url)
print(f"\n\nIND ROSTER (skill positions):")
for group in data.get("athletes", []):
    for a in group.get("items", []):
        pos = a.get("position", {}).get("abbreviation", "")
        if pos in ["QB", "RB", "WR", "TE"]:
            print(f"  {a.get('fullName')} ({pos}) - {a.get('status', {}).get('name', 'Active')}")

print("\n✓ ESPN API working!")
