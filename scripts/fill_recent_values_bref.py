import json
import requests
import time
from bs4 import BeautifulSoup
import re

PICKS_FILE = "scripts/props_orl_tor_cle_sas_lar_atl.json"
OUTPUT_FILE = "scripts/props_orl_tor_cle_sas_lar_atl_filled.json"
NUM_GAMES = 8

# Helper to get Basketball Reference player URL slug
# e.g., 'LeBron James' -> 'j/jamesle01'
def clean_name(name):
    # Remove suffixes and extra spaces
    suffixes = ["Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV", "V"]
    for suf in suffixes:
        if name.endswith(" " + suf):
            name = name[:-(len(suf)+1)]
    return name.strip()

def get_bref_slug(player_name):
    name = clean_name(player_name)
    search_url = f"https://www.basketball-reference.com/search/search.fcgi?search={name.replace(' ', '+')}"
    print(f"Searching: {search_url}")
    resp = requests.get(search_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    # Try to find the first player link in the search results table
    player_link = None
    results = soup.find('div', id='players')
    if results:
        table = results.find('table')
        if table:
            first_row = table.find('tr')
            if first_row:
                link = first_row.find('a', href=re.compile(r'/players/[a-z]/[a-z]+[a-z]{2}[0-9]{2}\.html'))
                if link:
                    player_link = link['href']
    if not player_link:
        # Fallback: first matching <a> anywhere
        link = soup.find('a', href=re.compile(r'/players/[a-z]/[a-z]+[a-z]{2}[0-9]{2}\.html'))
        if link:
            player_link = link['href']
    if player_link:
        return player_link.split('/players/')[1].replace('.html', '')
    # Try first/last only
    parts = name.split()
    if len(parts) > 1:
        alt_name = f"{parts[0][0]}. {parts[-1]}"
        alt_url = f"https://www.basketball-reference.com/search/search.fcgi?search={alt_name.replace(' ', '+')}"
        print(f"Retrying: {alt_url}")
        resp = requests.get(alt_url)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.find('div', id='players')
        if results:
            table = results.find('table')
            if table:
                first_row = table.find('tr')
                if first_row:
                    link = first_row.find('a', href=re.compile(r'/players/[a-z]/[a-z]+[a-z]{2}[0-9]{2}\.html'))
                    if link:
                        player_link = link['href']
        if not player_link:
            link = soup.find('a', href=re.compile(r'/players/[a-z]/[a-z]+[a-z]{2}[0-9]{2}\.html'))
            if link:
                player_link = link['href']
        if player_link:
            return player_link.split('/players/')[1].replace('.html', '')
    # Debug: print HTML structure if not found
    print("--- DEBUG: No player found, printing search HTML structure ---")
    print(soup.prettify()[:2000])
    return None

def get_recent_stat_bref(slug, stat, num_games=8):
    url = f"https://www.basketball-reference.com/players/{slug}.html"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find('table', id='per_game')
    if not table:
        return []
    rows = table.tbody.find_all('tr', class_=lambda x: x != 'thead')
    # Get most recent games (from bottom up)
    rows = [r for r in rows if r.get('id', '').startswith('per_game.')]
    rows = rows[-num_games:]
    stat_map = {
        "Points": "pts",
        "Rebounds": "trb",
        "Assists": "ast",
        "Pts+Rebs+Asts": None,  # Special
    }
    vals = []
    for r in rows:
        if stat == "Pts+Rebs+Asts":
            try:
                pts = float(r.find('td', {'data-stat': 'pts'}).text)
                trb = float(r.find('td', {'data-stat': 'trb'}).text)
                ast = float(r.find('td', {'data-stat': 'ast'}).text)
                vals.append(pts + trb + ast)
            except Exception:
                continue
        else:
            key = stat_map.get(stat)
            try:
                val = float(r.find('td', {'data-stat': key}).text)
                vals.append(val)
            except Exception:
                continue
    return vals

def main():
    with open(PICKS_FILE, "r") as f:
        picks = json.load(f)
    for pick in picks:
        league = pick.get("league", "NBA")
        if league != "NBA":
            continue
        player = pick["player"]
        stat = pick["stat"]
        slug = get_bref_slug(player)
        if not slug:
            print(f"Player not found on Basketball Reference: {player}")
            continue
        vals = get_recent_stat_bref(slug, stat, NUM_GAMES)
        if vals:
            pick["recent_values"] = vals
            print(f"Filled {player} {stat}: {vals}")
        else:
            print(f"No recent values for {player} {stat}")
        time.sleep(1)  # Be nice to the site
    with open(OUTPUT_FILE, "w") as f:
        json.dump(picks, f, indent=2)
    print(f"Filled picks saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
