"""Direct ESPN API test - no imports from ufa."""
import json
import ssl
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return json.loads(r.read())

print("=" * 50)
print("ESPN API DIRECT TEST")
print("=" * 50)

# Leaders
print("\n[1] NFL Leaders API...")
data = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/leaders")
for cat in data.get("leaders", [])[:2]:
    print(f"\n{cat['name']}:")
    for l in cat.get("leaders", [])[:3]:
        a = l.get("athlete", {})
        print(f"  {a.get('displayName')} ({a.get('team',{}).get('abbreviation')}): {l.get('displayValue')}")

# Schedule
print("\n[2] Week 17 Schedule...")
data = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week=17")
for e in data.get("events", [])[:5]:
    print(f"  {e.get('shortName')}")

# IND Roster
print("\n[3] IND Roster (skill)...")
data = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/11/roster")
for g in data.get("athletes", []):
    for a in g.get("items", [])[:8]:
        pos = a.get("position", {}).get("abbreviation", "")
        if pos in ["QB", "RB", "WR", "TE"]:
            print(f"  {a.get('fullName')} ({pos})")

print("\n" + "=" * 50)
print("SUCCESS - ESPN API WORKING")
print("=" * 50)
