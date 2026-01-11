"""Direct ESPN API test."""
import httpx
from urllib.parse import quote

client = httpx.Client(timeout=30, follow_redirects=True)

# Try different search endpoints
name = 'Jonathan Taylor'

# Method 1: Common search
url1 = f'https://site.api.espn.com/apis/common/v3/search?query={quote(name)}&limit=5'
print(f'\n[1] Common search: {url1}')
resp = client.get(url1)
print(f'    Status: {resp.status_code}')
data = resp.json()
groups = [g.get("displayName") for g in data.get("groups", [])]
print(f'    Groups: {groups}')

# Method 2: NFL-specific athlete search
url2 = f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/athletes?limit=10'
print(f'\n[2] Athletes endpoint: {url2}')
resp = client.get(url2)
print(f'    Status: {resp.status_code}')
data = resp.json()
print(f'    Keys: {list(data.keys())[:5]}')

# Method 3: ESPN's autocomplete
url3 = f'https://site.api.espn.com/apis/search/v1/typeahead?query={quote(name)}'
print(f'\n[3] Typeahead: {url3}')
resp = client.get(url3)
print(f'    Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    print(f'    Keys: {list(data.keys())[:5]}')

# Method 4: Get player directly by known ID
# Jonathan Taylor's ESPN ID is 4242335
url4 = f'https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/4242335'
print(f'\n[4] Direct athlete by ID: {url4}')
resp = client.get(url4)
print(f'    Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    athlete = data.get('athlete', {})
    print(f'    Name: {athlete.get("displayName")}')
    print(f'    Team: {athlete.get("team", {}).get("abbreviation")}')
    print(f'    Position: {athlete.get("position", {}).get("abbreviation")}')

client.close()
