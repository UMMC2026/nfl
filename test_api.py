"""Quick API test script"""
import requests

BASE = "http://localhost:8000"

# Test health
print("Testing /health...")
try:
    r = requests.get(f"{BASE}/health")
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.json()}")
except Exception as e:
    print(f"  Error: {e}")

# Test registration
print("\nTesting /auth/register...")
try:
    r = requests.post(f"{BASE}/auth/register", json={
        "email": "test2@example.com",
        "password": "testpass123",
        "display_name": "TestUser2"
    })
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.json()}")
except Exception as e:
    print(f"  Error: {e}")

# Test plans
print("\nTesting /payments/plans...")
try:
    r = requests.get(f"{BASE}/payments/plans")
    print(f"  Status: {r.status_code}")
    for plan in r.json():
        print(f"  - {plan['name']}: ${plan['price']}/mo")
except Exception as e:
    print(f"  Error: {e}")
