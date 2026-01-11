#!/usr/bin/env python3
"""Test SerpApi for game stats"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('SERPAPI_API_KEY')
print(f"API Key: {api_key[:20]}...")

params = {
    'engine': 'google',
    'q': 'Giannis Antetokounmpo points January 6 2026',
    'api_key': api_key,
    'num': 5
}

r = requests.get('https://serpapi.com/search', params=params, timeout=15)
print(f"\nStatus: {r.status_code}")

data = r.json()
print(f"Response keys: {list(data.keys())}")

if 'sports_results' in data:
    print("\n✅ Sports Results Found!")
    print(data['sports_results'])

if 'organic_results' in data:
    print(f"\n📄 Organic Results ({len(data['organic_results'])} found):")
    for i, res in enumerate(data['organic_results'][:3], 1):
        print(f"\n{i}. {res.get('title')}")
        print(f"   {res.get('snippet', '')[:200]}")
