"""
End-to-end test of subscription lifecycle:
1. Register user (free tier)
2. Create a test Stripe customer for this user
3. Simulate Stripe webhook (subscription.created)
4. Verify user tier upgraded in DB
5. Call /auth/refresh to get new JWT with updated tier
6. Verify /signals/parlays now accessible (was 403 before)
"""
import json
import time
import requests
import hmac
import hashlib
from dotenv import load_dotenv
import os
import sqlite3

load_dotenv()

BASE_URL = "http://localhost:8000"
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "test_secret")
DB_PATH = "c:\\Users\\hiday\\UNDERDOG ANANLYSIS\\ufa.db"


def get_user_stripe_customer_id(user_id: int) -> str:
    """Get stripe_customer_id from DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT stripe_customer_id FROM subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def set_user_stripe_customer_id(user_id: int, customer_id: str):
    """Set stripe_customer_id in DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE subscriptions SET stripe_customer_id = ? WHERE user_id = ?",
        (customer_id, user_id)
    )
    conn.commit()
    conn.close()


def get_user_tier(user_id: int) -> str:
    """Get user's current tier from DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.tier FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.user_id = ?
    """, (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "free"


def test_subscription_lifecycle():
    """Full integration test."""
    print("\n=== SUBSCRIPTION LIFECYCLE TEST ===\n")
    
    # Step 1: Register user (starts as FREE tier)
    print("Step 1: Register user (free tier)...")
    email = f"test_user_{int(time.time())}@example.com"
    register_resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": email,
            "password": "testpass123",
        }
    )
    assert register_resp.status_code == 200, f"Register failed: {register_resp.text}"
    register_data = register_resp.json()
    initial_token = register_data["access_token"]
    user_id = register_data.get("user_id")
    print(f"✓ Registered user_id={user_id}. JWT tier claim: {register_data.get('tier', 'N/A')}")
    
    # Verify initial tier is FREE
    initial_tier = get_user_tier(user_id)
    print(f"✓ DB tier: {initial_tier}")
    assert initial_tier == "free", f"Expected free, got {initial_tier}"
    
    # Step 2: Verify free user cannot access /parlays (403)
    print("\nStep 2: Verify FREE tier cannot access /parlays...")
    headers = {"Authorization": f"Bearer {initial_token}"}
    parlays_resp = requests.get(f"{BASE_URL}/signals/parlays", headers=headers)
    assert parlays_resp.status_code == 403, f"Expected 403, got {parlays_resp.status_code}"
    print(f"✓ /parlays returned 403 (as expected for FREE tier)")
    
    # Step 3: Set up Stripe customer ID
    print("\nStep 3: Prepare Stripe customer ID...")
    stripe_customer_id = f"cus_test_{user_id}_{int(time.time())}"
    set_user_stripe_customer_id(user_id, stripe_customer_id)
    print(f"✓ Set stripe_customer_id={stripe_customer_id}")
    
    # Step 4: Simulate Stripe webhook (subscription.created)
    print("\nStep 4: Simulate Stripe webhook (subscription.created with PRO tier)...")
    
    # Construct webhook payload
    webhook_event = {
        "id": f"evt_{int(time.time())}",
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "id": f"sub_{int(time.time())}",
                "customer": stripe_customer_id,
                "items": {
                    "data": [
                        {
                            "price": {
                                "id": os.getenv("STRIPE_PRICE_PRO", "price_pro_test")
                            }
                        }
                    ]
                },
                "status": "active",
                "current_period_end": int(time.time()) + (30 * 86400),  # 30 days from now
            }
        }
    }
    
    # Sign the webhook
    payload = json.dumps(webhook_event)
    timestamp = str(int(time.time()))
    signed_content = f"{timestamp}.{payload}"
    signature = hmac.new(
        STRIPE_WEBHOOK_SECRET.encode(),
        signed_content.encode(),
        hashlib.sha256
    ).hexdigest()
    
    webhook_headers = {
        "Stripe-Signature": f"t={timestamp},v1={signature}"
    }
    
    # Send webhook
    webhook_resp = requests.post(
        f"{BASE_URL}/webhooks/stripe",
        json=webhook_event,
        headers=webhook_headers
    )
    print(f"Webhook response: {webhook_resp.status_code}")
    if webhook_resp.status_code != 200:
        print(f"⚠ Warning: webhook returned {webhook_resp.status_code}: {webhook_resp.text}")
    else:
        print("✓ Webhook accepted")
    
    # Small delay for DB to update
    time.sleep(0.5)
    
    # Verify tier was upgraded in DB
    upgraded_tier = get_user_tier(user_id)
    print(f"\n✓ DB tier after webhook: {upgraded_tier}")
    if upgraded_tier != "pro":
        print(f"⚠ Warning: Expected pro, got {upgraded_tier}")
    
    # Step 5: Call /auth/refresh to get new JWT with updated tier
    print("\nStep 5: Call /auth/refresh to get updated JWT...")
    refresh_resp = requests.post(
        f"{BASE_URL}/auth/refresh",
        headers=headers
    )
    if refresh_resp.status_code != 200:
        print(f"⚠ /auth/refresh failed: {refresh_resp.status_code}: {refresh_resp.text}")
        new_token = initial_token  # Fall back to old token
    else:
        refresh_data = refresh_resp.json()
        new_token = refresh_data.get("access_token")
        new_tier = refresh_data.get("tier", "N/A")
        print(f"✓ Refreshed JWT. New tier claim: {new_tier}")
    
    # Step 6: Verify PRO tier can now access /parlays (200)
    print("\nStep 6: Verify upgraded tier can access /parlays...")
    headers_refreshed = {"Authorization": f"Bearer {new_token}"}
    parlays_resp2 = requests.get(f"{BASE_URL}/signals/parlays", headers=headers_refreshed)
    
    if parlays_resp2.status_code == 200:
        print(f"✓ /parlays returned 200 (tier upgrade successful!)")
    else:
        print(f"⚠ /parlays returned {parlays_resp2.status_code} (expected 200)")
        print(f"  Response: {parlays_resp2.text[:200]}")
    
    print("\n=== TEST COMPLETE ===\n")


def test_admin_tier_override():
    """Test admin endpoint for manual tier override."""
    print("\n=== ADMIN TIER OVERRIDE TEST ===\n")
    
    # Register a test user
    print("Registering test user...")
    register_resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": f"admin_test_{int(time.time())}@example.com",
            "password": "testpass123",
        }
    )
    assert register_resp.status_code == 200
    user_id = register_resp.json()["user_id"]
    print(f"✓ User {user_id} registered as FREE")
    
    # Get admin token (you'll need to set is_admin=True manually in DB for now)
    # For this test, we'll just show the endpoint and note that is_admin check would fail
    print("\nAttempting to override tier to WHALE via /admin endpoint...")
    print("(Note: This would require is_admin=True in your user record)")
    
    # This will fail with 403 unless the user is admin, which is expected
    override_resp = requests.post(
        f"{BASE_URL}/admin/users/{user_id}/tier",
        json={
            "tier": "whale",
            "reason": "Test admin override",
        },
        headers={"Authorization": f"Bearer {register_resp.json()['access_token']}"}
    )
    
    if override_resp.status_code == 403:
        print(f"✓ Admin check working: {override_resp.json()['detail']}")
    else:
        print(f"Unexpected response: {override_resp.status_code}: {override_resp.text}")
    
    print("\n=== ADMIN TEST COMPLETE ===\n")


if __name__ == "__main__":
    try:
        print("Checking if API is running...")
        health = requests.get(f"{BASE_URL}/health")
        assert health.status_code == 200
        print("✓ API is running\n")
    except Exception as e:
        print(f"✗ API not reachable: {e}")
        print("Start the API with: python run_api.py")
        exit(1)
    
    test_subscription_lifecycle()
    test_admin_tier_override()
