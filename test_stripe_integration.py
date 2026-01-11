"""Test Stripe integration components."""

import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test all modules can be imported."""
    print("Testing imports...")
    
    try:
        from stripe_config import STRIPE_SECRET_KEY, PRODUCTS
        print("  ✅ stripe_config")
    except Exception as e:
        print(f"  ❌ stripe_config: {e}")
        return False
    
    try:
        from stripe_db import User, Subscription, AccessLog
        print("  ✅ stripe_db")
    except Exception as e:
        print(f"  ❌ stripe_db: {e}")
        return False
    
    try:
        from stripe_webhooks import router as stripe_router
        print("  ✅ stripe_webhooks")
    except Exception as e:
        print(f"  ❌ stripe_webhooks: {e}")
        return False
    
    try:
        from stripe_analysis_routes import router as analysis_router
        print("  ✅ stripe_analysis_routes")
    except Exception as e:
        print(f"  ❌ stripe_analysis_routes: {e}")
        return False
    
    try:
        from stripe_access_control import check_tier_access, get_available_features
        print("  ✅ stripe_access_control")
    except Exception as e:
        print(f"  ❌ stripe_access_control: {e}")
        return False
    
    try:
        from stripe_integration import app
        print("  ✅ stripe_integration")
    except Exception as e:
        print(f"  ❌ stripe_integration: {e}")
        return False
    
    return True


def test_database():
    """Test database operations."""
    print("\nTesting database...")
    
    try:
        from stripe_db import User, Subscription, AccessLog
        
        # Create test user
        user_id = User.create("test@example.com", "cus_test_123")
        print(f"  ✅ Created user: {user_id}")
        
        # Retrieve user
        user = User.get_by_email("test@example.com")
        print(f"  ✅ Retrieved user: {user['email']}")
        
        # Create subscription
        sub_id = Subscription.create(
            user_id=user_id,
            stripe_subscription_id="sub_test_123",
            tier="pro",
            current_period_start="2024-01-05 00:00:00",
            current_period_end="2024-02-05 00:00:00",
        )
        print(f"  ✅ Created subscription: {sub_id}")
        
        # Check tier
        tier = Subscription.get_tier(user_id)
        print(f"  ✅ User tier: {tier}")
        
        # Log access
        AccessLog.record(user_id, "cheatsheet")
        print(f"  ✅ Logged access: cheatsheet")
        
        return True
    except Exception as e:
        print(f"  ❌ Database error: {e}")
        return False


def test_tier_access():
    """Test access control logic."""
    print("\nTesting tier access control...")
    
    try:
        from stripe_access_control import check_tier_access, get_available_features
        
        # Test each tier
        tiers = {
            "starter": ["cheatsheet"],
            "pro": ["cheatsheet", "commentary", "correlations"],
            "whale": ["cheatsheet", "commentary", "correlations", "telegram_alerts", "live_updates"],
        }
        
        for tier, expected_features in tiers.items():
            features = get_available_features(tier)
            if features == expected_features:
                print(f"  ✅ {tier}: {features}")
            else:
                print(f"  ❌ {tier}: expected {expected_features}, got {features}")
                return False
        
        # Test access checks
        assert check_tier_access("starter", "cheatsheet") == True
        assert check_tier_access("starter", "commentary") == False
        assert check_tier_access("pro", "commentary") == True
        assert check_tier_access("whale", "telegram_alerts") == True
        print(f"  ✅ Access checks working")
        
        return True
    except Exception as e:
        print(f"  ❌ Access control error: {e}")
        return False


def test_fastapi():
    """Test FastAPI app loads."""
    print("\nTesting FastAPI app...")
    
    try:
        from stripe_integration import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        print(f"  ✅ Health check: {response.json()}")
        
        # Test analysis endpoint (should fail without user ID)
        response = client.get("/analysis/dashboard")
        assert response.status_code == 401
        print(f"  ✅ Dashboard auth check: returns 401 without user ID")
        
        return True
    except Exception as e:
        print(f"  ❌ FastAPI error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("STRIPE INTEGRATION TEST SUITE")
    print("=" * 60)
    
    all_passed = True
    
    if not test_imports():
        all_passed = False
    
    if not test_database():
        all_passed = False
    
    if not test_tier_access():
        all_passed = False
    
    if not test_fastapi():
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Fill in price IDs from Stripe dashboard")
        print("2. Create webhook endpoint in Stripe")
        print("3. Start API: python -m uvicorn stripe_integration:app --reload")
        print("4. Test webhook with Stripe CLI")
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
