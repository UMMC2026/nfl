#!/usr/bin/env python3
"""Test improved SerpApi stat parsing"""

import requests
import os
import re
from dotenv import load_dotenv

load_dotenv()

def test_stat_parsing(player, stat, date):
    api_key = os.getenv('SERPAPI_API_KEY')
    
    query = f"{player} {stat} {date}"
    params = {
        'engine': 'google',
        'q': query,
        'api_key': api_key,
        'num': 5
    }
    
    print(f"\n{'='*60}")
    print(f"🔍 Query: {query}")
    print(f"{'='*60}")
    
    r = requests.get('https://serpapi.com/search', params=params, timeout=15)
    data = r.json()
    
    stat_patterns = {
        'points': r'(\d+)\s*(?:PTS|points?)',
        'rebounds': r'(\d+)\s*(?:REB|rebounds?)',
        'assists': r'(\d+)\s*(?:AST|assists?)',
    }
    
    if "organic_results" in data:
        for i, result in enumerate(data["organic_results"][:3], 1):
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            combined = f"{title} {snippet}"
            
            print(f"\n{i}. {title}")
            print(f"   {snippet[:150]}")
            
            # Try to find the stat
            if stat in stat_patterns:
                pattern = stat_patterns[stat]
                match = re.search(pattern, combined, re.IGNORECASE)
                if match:
                    value = float(match.group(1))
                    print(f"   ✅ FOUND: {stat} = {value}")
                    return value
    
    print(f"\n❌ Could not parse {stat}")
    return None

# Test with recent game
result = test_stat_parsing("Giannis Antetokounmpo", "points", "January 6 2026")
if result:
    print(f"\n✅ SUCCESS: Giannis points = {result}")
