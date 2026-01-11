"""Test ESPN player search."""
from ufa.ingest.espn import ESPNFetcher

fetcher = ESPNFetcher(season=2024)

# Test players
for name in ['Saquon Barkley', 'Jonathan Taylor', 'Brian Thomas', 'Nick Chubb']:
    result = fetcher.search_player(name)
    if result:
        print(f"{result['name']} ({result['team']}) - ID: {result['id']}")
    else:
        print(f'{name}: NOT FOUND')

fetcher.close()
