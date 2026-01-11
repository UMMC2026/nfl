#!/usr/bin/env python3
"""Simple API test to verify endpoints work."""
import sys
import time
import subprocess
import requests
from pathlib import Path

def test_api():
    """Test API registration and signal retrieval."""
    
    # Start API
    print("Starting API...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ufa.api.main:app", "--port", "8000"],
        cwd=Path(__file__).parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for startup
    time.sleep(4)
    
    try:
        # Test 1: Register user
        print("\n[1] Registering user...")
        r = requests.post("http://127.0.0.1:8000/auth/register", json={
            "email": "test@example.com",
            "password": "test123",
            "display_name": "Test User"
        }, timeout=5)
        
        if r.status_code != 200:
            print(f"❌ Registration failed: {r.status_code}")
            print(r.text[:500])
            return False
        
        data = r.json()
        print(f"✅ User registered: tier={data.get('tier')}")
        token = data.get("access_token")
        
        # Test 2: Get signals
        print("\n[2] Fetching signals...")
        r = requests.get("http://127.0.0.1:8000/signals", 
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=5)
        
        if r.status_code != 200:
            print(f"❌ Signals request failed: {r.status_code}")
            print(r.text[:500])
            return False
        
        signals = r.json()
        print(f"✅ Got {len(signals)} signals")
        
        if signals:
            sig = signals[0]
            fields = list(sig.keys())
            print(f"   Fields: {', '.join(fields)}")
            print(f"   Sample: {sig}")
        
        print("\n✅ ALL TESTS PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False
    
    finally:
        proc.terminate()
        proc.wait(timeout=5)

if __name__ == "__main__":
    success = test_api()
    sys.exit(0 if success else 1)
