"""Prop analysis powered by Pro-Football-Reference (PFR).

This script fetches NFL player game logs from PFR, computes per-game averages
for key stats, and evaluates props similarly to scripts/prop_analysis.py but
without relying on ESPN JSON. It includes a lightweight PFR ID resolver that
tries common ID patterns and caches successful resolutions to avoid repeated
lookups.

Usage:
  python scripts/pfr_prop_analysis.py --season 2025 --debug

Dependencies:
  - beautifulsoup4, lxml (added to requirements-extras.txt)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import urllib.request
import time
from bs4 import BeautifulSoup, Comment

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

CACHE_PATH = os.path.join(os.path.dirname(__file__), 'pfr_ids_cache.json')


def http_get(url: str, timeout: int = 20, retries: int = 3, backoff: float = 1.5) -> Optional[str]:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.pro-football-reference.com/'
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                if 200 <= resp.status < 300:
                    return resp.read().decode('utf-8', errors='ignore')
                elif resp.status == 429:
                    # Too many requests - backoff
                    time.sleep(backoff * (attempt + 1))
                    continue
                else:
                    return None
        except Exception:
            time.sleep(backoff * (attempt + 1))
    return None


def load_cache() -> Dict[str, str]:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: Dict[str, str]) -> None:
    try:
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def name_to_candidates(full_name: str) -> Tuple[str, list[str]]:
    """Generate candidate PFR IDs for a player name.

    PFR pattern (most cases): last4 + first2 + 2-digit index, e.g. RodgAa00, TaylJo02.
    We'll ignore suffixes like Jr./Sr./III for ID generation.
    """
    # Strip suffixes and punctuation
    n = re.sub(r"[,.'-]", "", full_name).strip()
    parts = n.split()
    if len(parts) < 2:
        return 'A', []
    # Handle suffixes
    suffixes = {"jr", "sr", "ii", "iii", "iv", "v"}
    if parts[-1].lower() in suffixes:
        parts = parts[:-1]
    first, last = parts[0], parts[-1]
    last4 = last[:4].title()  # first 4 letters of last name
    first2 = first[:2].title()
    letter = last[0].upper()
    candidates = [f"{last4}{first2}{i:02d}" for i in range(0, 10)]
    return letter, candidates


def resolve_pfr_id(full_name: str, *, season: int, debug: bool = False) -> Optional[str]:
    cache = load_cache()
    if full_name in cache:
        return cache[full_name]

    letter, candidates = name_to_candidates(full_name)
    for cid in candidates:
        url = f"https://www.pro-football-reference.com/players/{letter}/{cid}/gamelog/{season}/"
        html = http_get(url)
        if not html:
            continue
        # quick presence check for stats table marker
        if 'id="stats"' in html or 'id=\"stats\"' in html:
            cache[full_name] = cid
            save_cache(cache)
            if debug:
                print(f"[DEBUG] Resolved PFR ID for {full_name}: {cid}")
            return cid
        # polite delay between attempts
        time.sleep(1.2)
    if debug:
        print(f"[DEBUG] Failed to resolve PFR ID for {full_name}")
    return None


def parse_pfr_gamelog(html: str) -> Dict[str, float]:
    """Parse PFR gamelog page HTML and return season totals with game count.

    PFR puts the table inside HTML comments. We find the comment containing id='stats'.
    We'll sum numeric values for relevant data-stat attributes.
    """
    soup = BeautifulSoup(html, 'html.parser')
    table_html = None
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        if 'table' in c and 'id="stats"' in c:
            table_html = str(c)
            break
    if not table_html:
        # sometimes already in DOM
        table_tag = soup.find('table', id='stats')
        if table_tag:
            table_html = str(table_tag)
    if not table_html:
        return {'games': 0}

    tsoup = BeautifulSoup(table_html, 'html.parser')
    table = tsoup.find('table', id='stats')
    if not table:
        return {'games': 0}

    totals = {
        'games': 0,
        'rushing_YDS': 0.0, 'rushing_TD': 0.0, 'rushing_CAR': 0.0,
        'receiving_YDS': 0.0, 'receiving_TD': 0.0, 'receiving_REC': 0.0, 'receiving_TGTS': 0.0,
        'passing_YDS': 0.0, 'passing_TD': 0.0, 'passing_CMP': 0.0, 'passing_ATT': 0.0, 'passing_INT': 0.0,
    }

    def to_float(x: str) -> float:
        try:
            x = (x or '').strip()
            if x in ('', 'NA', '—', '—/—'):
                return 0.0
            return float(x.replace(',', ''))
        except Exception:
            return 0.0

    tbody = table.find('tbody') or table
    for tr in tbody.find_all('tr'):
        if 'class' in tr.attrs and 'thead' in tr.get('class', []):
            continue
        # skip playoff break rows or blank rows
        wk = tr.find('th', attrs={'data-stat': 'week_num'})
        if not wk:
            continue
        wk_txt = (wk.get_text(strip=True) or '')
        if not wk_txt.isdigit():
            continue

        totals['games'] += 1

        def get(ds: str) -> str:
            td = tr.find(['td', 'th'], attrs={'data-stat': ds})
            return td.get_text(strip=True) if td else ''

        # rushing
        totals['rushing_YDS'] += to_float(get('rush_yds'))
        totals['rushing_TD'] += to_float(get('rush_td'))
        totals['rushing_CAR'] += to_float(get('rush_att'))
        # receiving
        totals['receiving_YDS'] += to_float(get('rec_yds'))
        totals['receiving_TD'] += to_float(get('rec_td'))
        totals['receiving_REC'] += to_float(get('rec'))
        totals['receiving_TGTS'] += to_float(get('targets'))
        # passing
        totals['passing_YDS'] += to_float(get('pass_yds'))
        totals['passing_TD'] += to_float(get('pass_td'))
        totals['passing_CMP'] += to_float(get('pass_cmp'))
        totals['passing_ATT'] += to_float(get('pass_att'))
        totals['passing_INT'] += to_float(get('pass_int'))

    return totals


def get_pfr_stats(name: str, *, season: int, debug: bool = False) -> Dict[str, float]:
    cid = resolve_pfr_id(name, season=season, debug=debug)
    if not cid:
        return {'name': name, 'games': 0}
    last_letter = re.sub(r"[,.'-]", "", name).split()[-1][0].upper()
    url = f"https://www.pro-football-reference.com/players/{last_letter}/{cid}/gamelog/{season}/"
    html = http_get(url)
    if not html:
        return {'name': name, 'games': 0}
    totals = parse_pfr_gamelog(html)
    totals['name'] = name
    return totals


# Props definitions – copied from ESPN script for parity
props_data = {
    'Jonathan Taylor': [
        ('Rush + Rec TDs', 0.5, 0.73, 1.15),
        ('Rush Yards', 73.5, 1.0, 1.0),
        ('Receiving Yards', 18.5, 1.0, 1.0),
        ('Receptions', 3.5, 1.05, 0.78),
        ('Rush Attempts', 18.5, 1.0, 1.0),
        ('Rush + Rec Yards', 97.5, 1.0, 1.0),
        ('Targets', 3.5, 1.09, 0.76),
    ],
    'Travis Etienne Jr.': [
        ('Rush + Rec TDs', 0.5, 0.74, 1.13),
        ('Rush Yards', 66.5, 1.0, 1.0),
        ('Receiving Yards', 17.5, 1.0, 1.0),
        ('Receptions', 2.5, 0.82, 1.03),
        ('Rush Attempts', 17.5, 1.03, 0.79),
        ('Rush + Rec Yards', 88.5, 1.0, 1.0),
    ],
    'Tyler Warren': [
        ('Rush + Rec TDs', 0.5, 1.32, 0.66),
        ('Receiving Yards', 48.5, 1.0, 1.0),
        ('Receptions', 5.5, 1.08, 0.79),
        ('Targets', 6.5, 0.85, 1.05),
    ],
    'Michael Pittman Jr.': [
        ('Rush + Rec TDs', 0.5, 1.52, 0.64),
        ('Receiving Yards', 44.5, 1.0, 1.0),
        ('Receptions', 4.5, 1.0, 1.0),
        ('Targets', 7.5, 1.07, 0.8),
    ],
    'Trevor Lawrence': [
        ('Rush + Rec TDs', 0.5, 1.39, 0.66),
        ('Pass Yards', 246.5, 1.0, 1.0),
        ('Pass TDs', 1.5, 0.81, 1.04),
        ('Rush Yards', 18.5, 1.0, 1.0),
        ('Rush Attempts', 4.5, 0.82, 1.04),
        ('Pass Attempts', 32.5, 0.84, 1.06),
        ('Completions', 20.5, 0.81, 1.06),
        ('INTs Thrown', 0.5, 1.0, 1.0),
    ],
    'Brian Thomas': [
        ('Rush + Rec TDs', 0.5, 1.3, 0.69),
        ('Receiving Yards', 48.5, 1.0, 1.0),
        ('Receptions', 3.5, 1.09, 0.8),
    ],
    'Jakobi Meyers': [
        ('Rush + Rec TDs', 0.5, 1.08, 0.76),
        ('Receiving Yards', 59.5, 1.0, 1.0),
        ('Receptions', 5.5, 1.03, 0.82),
        ('Targets', 7.5, 1.07, 0.84),
    ],
    'Josh Downs': [
        ('Rush + Rec TDs', 0.5, 1.79, 0.61),
        ('Receiving Yards', 35.5, 1.0, 1.0),
        ('Receptions', 3.5, 0.81, 1.06),
    ],
    'Alec Pierce': [
        ('Rush + Rec TDs', 0.5, 1.76, 0.61),
        ('Receiving Yards', 31.5, 1.0, 1.0),
        ('Receptions', 2.5, 1.03, 0.82),
        ('Targets', 4.5, 1.0, 1.0),
    ],
    'Aaron Rodgers': [
        ('Pass Yards', 187.5, 1.0, 1.0),
        ('Pass TDs', 1.5, 1.17, 0.73),
        ('Rush Yards', 0.5, 1.05, 0.81),
        ('Rush Attempts', 1.5, 1.05, 0.94),
        ('Completions', 18.5, 1.0, 1.0),
        ('Pass Attempts', 28.5, 0.87, 1.05),
        ('INTs Thrown', 0.5, 1.03, 0.82),
    ],
    'Shedeur Sanders': [
        ('Rush + Rec TDs', 0.5, 2.41, 1.0),
        ('Pass Yards', 178.5, 1.0, 1.0),
        ('Pass TDs', 0.5, 0.8, 1.06),
        ('Rush Yards', 13.5, 1.0, 1.0),
    ],
    'Kenneth Gainwell': [
        ('Rush + Rec TDs', 0.5, 1.09, 0.76),
        ('Rush Yards', 37.5, 1.0, 1.0),
        ('Receiving Yards', 30.5, 1.0, 1.0),
        ('Receptions', 4.5, 1.03, 0.88),
        ('Rush Attempts', 8.5, 0.83, 1.08),
        ('Rush + Rec Yards', 71.5, 1.0, 1.0),
    ],
    'Jaylen Warren': [
        ('Rush + Rec TDs', 0.5, 1.19, 0.73),
        ('Rush Yards', 54.5, 1.0, 1.0),
        ('Receiving Yards', 12.5, 1.0, 1.0),
        ('Receptions', 2.5, 1.09, 0.79),
        ('Rush Attempts', 13.5, 0.94, 1.05),
        ('Rush + Rec Yards', 71.5, 1.0, 1.0),
    ],
    'Dylan Sampson': [
        ('Rush + Rec TDs', 0.5, 1.28, 0.68),
        ('Rush Yards', 42.5, 1.0, 1.0),
        ('Receiving Yards', 17.5, 1.0, 1.0),
        ('Receptions', 2.5, 0.81, 1.06),
        ('Rush Attempts', 12.5, 0.86, 1.05),
        ('Rush + Rec Yards', 64.5, 1.0, 1.0),
        ('Targets', 3.5, 0.86, 1.06),
    ],
    'Jerry Jeudy': [
        ('Rush + Rec TDs', 0.5, 2.7, 1.0),
        ('Receiving Yards', 29.5, 1.0, 1.0),
        ('Receptions', 2.5, 1.04, 1.0),
        ('Targets', 4.5, 1.09, 0.83),
    ],
    'Harold Fannin': [
        ('Rush + Rec TDs', 0.5, 1.78, 0.61),
        ('Receiving Yards', 49.5, 1.0, 1.0),
        ('Receptions', 5.5, 1.09, 0.83),
    ],
    'Pat Freiermuth': [
        ('Rush + Rec TDs', 0.5, 2.72, 1.0),
        ('Receiving Yards', 22.5, 1.0, 1.0),
        ('Receptions', 2.5, 1.05, 0.84),
    ],
    'Adam Thielen': [
        ('Rush + Rec TDs', 0.5, 2.3, 1.0),
        ('Receiving Yards', 19.5, 1.0, 1.0),
        ('Receptions', 2.5, 1.07, 0.76),
    ],
    'Darnell Washington': [
        ('Rush + Rec TDs', 0.5, 2.58, 1.0),
        ('Receiving Yards', 25.5, 1.0, 1.0),
        ('Receptions', 2.5, 0.88, 1.02),
    ],
}


MIN_GAMES_REQUIRED = 5


def analyze_rb(name: str, stats: Dict[str, float], props):
    games = int(stats.get('games') or 0)
    if games == 0:
        return []
    picks = []
    avg_rush = (stats.get('rushing_YDS', 0.0) / games) if games else 0
    avg_rec = (stats.get('receiving_YDS', 0.0) / games) if games else 0
    avg_recs = (stats.get('receiving_REC', 0.0) / games) if games else 0
    avg_att = (stats.get('rushing_CAR', 0.0) / games) if games else 0
    avg_td = ((stats.get('rushing_TD', 0.0) + stats.get('receiving_TD', 0.0)) / games) if games else 0

    for prop, line, higher_odds, lower_odds in props:
        edge = None; pick = None; confidence = 0
        if prop == 'Rush Yards':
            diff = avg_rush - line
            pct = (diff / line) * 100 if line else 0
            if abs(pct) > 10:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(pct), 30)
                edge = f"Avg {avg_rush:.1f} vs line {line}"
        elif prop == 'Receiving Yards':
            diff = avg_rec - line
            pct = (diff / line) * 100 if line else 0
            if abs(pct) > 15:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(pct), 30)
                edge = f"Avg {avg_rec:.1f} vs line {line}"
        elif prop == 'Receptions':
            diff = avg_recs - line
            if abs(diff) > 0.5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(diff) * 20, 30)
                edge = f"Avg {avg_recs:.1f} vs line {line}"
        elif prop == 'Rush Attempts':
            diff = avg_att - line
            if abs(diff) > 1:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(diff) * 10, 30)
                edge = f"Avg {avg_att:.1f} vs line {line}"
        elif prop == 'Rush + Rec Yards':
            avg_total = avg_rush + avg_rec
            diff = avg_total - line
            pct = (diff / line) * 100 if line else 0
            if abs(pct) > 8:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(pct), 30)
                edge = f"Avg {avg_total:.1f} vs line {line}"
        elif prop == 'Rush + Rec TDs':
            if avg_td > 0.7 and line == 0.5:
                pick = 'HIGHER'; confidence = min((avg_td - 0.5) * 40, 25)
                edge = f"Avg {avg_td:.2f} TDs/game"
        if pick and confidence > 15:
            picks.append({'player': name, 'prop': prop, 'line': line, 'pick': pick,
                          'confidence': confidence, 'edge': edge,
                          'higher_odds': higher_odds, 'lower_odds': lower_odds})
    return picks


def analyze_wr_te(name: str, stats: Dict[str, float], props):
    games = int(stats.get('games') or 0)
    if games == 0:
        return []
    picks = []
    avg_rec_yds = (stats.get('receiving_YDS', 0.0) / games) if games else 0
    avg_recs = (stats.get('receiving_REC', 0.0) / games) if games else 0
    avg_tgts = (stats.get('receiving_TGTS', 0.0) / games) if games else 0
    avg_td = (stats.get('receiving_TD', 0.0) / games) if games else 0

    for prop, line, higher_odds, lower_odds in props:
        edge = None; pick = None; confidence = 0
        if prop == 'Receiving Yards':
            diff = avg_rec_yds - line
            pct = (diff / line) * 100 if line else 0
            if abs(pct) > 10:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(pct), 35)
                edge = f"Avg {avg_rec_yds:.1f} vs line {line}"
        elif prop == 'Receptions':
            diff = avg_recs - line
            if abs(diff) > 0.4:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(diff) * 25, 35)
                edge = f"Avg {avg_recs:.1f} vs line {line}"
        elif prop == 'Targets':
            diff = avg_tgts - line
            if abs(diff) > 0.5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(diff) * 20, 30)
                edge = f"Avg {avg_tgts:.1f} vs line {line}"
        elif prop == 'Rush + Rec TDs':
            if avg_td > 0.5 and line == 0.5:
                pick = 'HIGHER'; confidence = min(avg_td * 30, 25)
                edge = f"Avg {avg_td:.2f} TDs/game"
        if pick and confidence > 12:
            picks.append({'player': name, 'prop': prop, 'line': line, 'pick': pick,
                          'confidence': confidence, 'edge': edge,
                          'higher_odds': higher_odds, 'lower_odds': lower_odds})
    return picks


def analyze_qb(name: str, stats: Dict[str, float], props):
    games = int(stats.get('games') or 0)
    if games == 0:
        return []
    picks = []
    avg_pass = (stats.get('passing_YDS', 0.0) / games) if games else 0
    avg_pass_td = (stats.get('passing_TD', 0.0) / games) if games else 0
    avg_cmp = (stats.get('passing_CMP', 0.0) / games) if games else 0
    avg_att = (stats.get('passing_ATT', 0.0) / games) if games else 0
    avg_rush = (stats.get('rushing_YDS', 0.0) / games) if games else 0
    avg_int = (stats.get('passing_INT', 0.0) / games) if games else 0

    for prop, line, higher_odds, lower_odds in props:
        edge = None; pick = None; confidence = 0
        if prop == 'Pass Yards':
            diff = avg_pass - line
            pct = (diff / line) * 100 if line else 0
            if abs(pct) > 8:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(pct), 35)
                edge = f"Avg {avg_pass:.1f} vs line {line}"
        elif prop == 'Pass TDs':
            diff = avg_pass_td - line
            if abs(diff) > 0.3:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(diff) * 30, 30)
                edge = f"Avg {avg_pass_td:.2f} vs line {line}"
        elif prop == 'Completions':
            diff = avg_cmp - line
            if abs(diff) > 1.5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(diff) * 10, 30)
                edge = f"Avg {avg_cmp:.1f} vs line {line}"
        elif prop == 'Pass Attempts':
            diff = avg_att - line
            if abs(diff) > 2:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(diff) * 8, 30)
                edge = f"Avg {avg_att:.1f} vs line {line}"
        elif prop == 'Rush Yards':
            diff = avg_rush - line
            pct = (diff / line) * 100 if line else 0
            if abs(pct) > 15:
                pick = 'HIGHER' if diff > 0 else 'LOWER'; confidence = min(abs(pct), 30)
                edge = f"Avg {avg_rush:.1f} vs line {line}"
        elif prop == 'INTs Thrown':
            if line == 0.5 and avg_int < 0.6:
                pick = 'LOWER'; confidence = 20; edge = f"Avg {avg_int:.2f} INTs/game"
        if pick and confidence > 12:
            picks.append({'player': name, 'prop': prop, 'line': line, 'pick': pick,
                          'confidence': confidence, 'edge': edge,
                          'higher_odds': higher_odds, 'lower_odds': lower_odds})
    return picks


players = [
    # JAX @ IND core list
    'Jonathan Taylor', 'Travis Etienne Jr.', 'Trevor Lawrence', 'Michael Pittman Jr.',
    'Brian Thomas', 'Jakobi Meyers', 'Josh Downs', 'Alec Pierce', 'Tyler Warren',
    # PIT @ CLE core list
    'Aaron Rodgers', 'Shedeur Sanders', 'Kenneth Gainwell', 'Jaylen Warren',
    'Dylan Sampson', 'Jerry Jeudy', 'Harold Fannin', 'Pat Freiermuth',
    'Myles Garrett', 'Adam Thielen', 'Darnell Washington',
]


def main():
    parser = argparse.ArgumentParser(description='PFR-based prop analysis')
    parser.add_argument('--season', type=int, default=2025)
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--fail-on-missing-data', action='store_true')
    args = parser.parse_args()

    print('=' * 80)
    print('FETCHING PFR STATS...')
    print('=' * 80)

    all_stats: Dict[str, Dict[str, float]] = {}
    missing = []
    for name in players:
        s = get_pfr_stats(name, season=args.season, debug=args.debug)
        all_stats[name] = s
        g = int(s.get('games') or 0)
        print(f"\n{name} ({g} games):")
        if s.get('rushing_YDS', 0) or s.get('rushing_CAR', 0):
            per_g = (s.get('rushing_YDS', 0) / g) if g else 0
            print(f"  Rush: {s.get('rushing_YDS', 0):.0f} yds, {s.get('rushing_TD', 0):.0f} TD, {s.get('rushing_CAR', 0):.0f} att ({per_g:.1f}/g)")
        if s.get('receiving_YDS', 0) or s.get('receiving_REC', 0):
            per_g_yd = (s.get('receiving_YDS', 0) / g) if g else 0
            per_g_rec = (s.get('receiving_REC', 0) / g) if g else 0
            print(f"  Rec: {s.get('receiving_YDS', 0):.0f} yds, {s.get('receiving_TD', 0):.0f} TD, {s.get('receiving_REC', 0):.0f} rec ({per_g_yd:.1f}/g, {per_g_rec:.1f} rec/g)")
        if s.get('passing_YDS', 0) or s.get('passing_TD', 0):
            per_g = (s.get('passing_YDS', 0) / g) if g else 0
            print(f"  Pass: {s.get('passing_YDS', 0):.0f} yds, {s.get('passing_TD', 0):.0f} TD ({per_g:.1f}/g)")
        if g < MIN_GAMES_REQUIRED:
            missing.append((name, g))

    if missing:
        print("\n[WARN] Insufficient data for players (games < MIN_GAMES_REQUIRED):")
        for n, g in missing:
            print(f"  - {n}: {g} games")
        if args.fail_on_missing_data:
            print("\nABORTING due to --fail-on-missing-data")
            sys.exit(1)

    # Evaluate props
    all_picks = []

    def has_enough(n: str) -> bool:
        return int(all_stats.get(n, {}).get('games') or 0) >= MIN_GAMES_REQUIRED

    for n in ['Jonathan Taylor', 'Travis Etienne Jr.', 'Kenneth Gainwell', 'Jaylen Warren', 'Dylan Sampson']:
        if has_enough(n) and n in props_data:
            all_picks += analyze_rb(n, all_stats[n], props_data[n])
    for n in ['Tyler Warren', 'Michael Pittman Jr.', 'Brian Thomas', 'Jakobi Meyers', 'Josh Downs', 'Alec Pierce',
              'Jerry Jeudy', 'Harold Fannin', 'Pat Freiermuth', 'Adam Thielen', 'Darnell Washington']:
        if has_enough(n) and n in props_data:
            all_picks += analyze_wr_te(n, all_stats[n], props_data[n])
    for n in ['Trevor Lawrence', 'Aaron Rodgers', 'Shedeur Sanders']:
        if has_enough(n) and n in props_data:
            all_picks += analyze_qb(n, all_stats[n], props_data[n])

    all_picks.sort(key=lambda x: x['confidence'], reverse=True)

    print("\n" + "=" * 80)
    print("🎯 TOP PROP PICKS (PFR) ")
    print("=" * 80)
    for i, pick in enumerate(all_picks[:15], 1):
        odds = pick['higher_odds'] if pick['pick'] == 'HIGHER' else pick['lower_odds']
        odds_str = f" ({odds}x)" if odds and odds != 1.0 else ""
        print(f"\n{i}. {pick['player']} - {pick['prop']}")
        print(f"   📊 Line: {pick['line']} → {pick['pick']}{odds_str}")
        print(f"   📈 Edge: {pick['edge']}")
        print(f"   ⭐ Confidence: {pick['confidence']:.0f}%")


if __name__ == '__main__':
    main()
