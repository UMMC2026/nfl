"""
Test SerpApi connection
"""
import os
from dotenv import load_dotenv
from ufa.analysis.learning_integration import SerpApiClient

# Load environment variables
load_dotenv()

api_key = os.getenv('SERPAPI_API_KEY')

if not api_key or api_key == 'your_serpapi_api_key_here':
    print("❌ SERPAPI_API_KEY not set in .env file")
    exit(1)

print(f"🔑 Using API key: {api_key[:10]}...")

# Test connection
try:
    client = SerpApiClient(api_key)
    
    # Try a simple search
    print("📡 Testing SerpApi connection...")
    results = client.search_game_context("LeBron James", "2026-01-05")
    
    if "error" in results:
        print(f"❌ API Error: {results['error']}")
        exit(1)
    
    print(f"✅ SerpApi Connected Successfully!")
    
    # Extract and show snippets
    snippets = client.extract_context_snippets(results)
    
    if snippets:
        print(f"📰 Found {len(snippets)} relevant results")
        print(f"\nSample snippet:")
        print(f"  {snippets[0][:150]}...")
    else:
        print("ℹ️  No snippets found (search may have returned no results)")
    
    # Show search info
    if "search_parameters" in results:
        print(f"\nSearch query: {results['search_parameters'].get('q', 'N/A')}")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    import traceback
    traceback.print_exc()
