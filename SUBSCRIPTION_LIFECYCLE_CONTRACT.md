"""
SUBSCRIPTION LIFECYCLE BEHAVIORAL CONTRACT
============================================

This document specifies the guaranteed behavior of the Stripe → tier upgrade flow.

---

## 1. TIER UPGRADE TIMING

**Rule**: Tier upgrades are visible on the NEXT login or JWT refresh, NOT mid-session.

**Why?**
- JWTs are issued at login/token creation and cached by the client
- Stripe webhooks are asynchronous and may arrive out-of-order
- The database is the source of truth; JWT claims are computed from it
- This pattern is industry-standard and acceptable to users

**Behavior Timeline**:

1. User registers → FREE tier, gets JWT with tier="free"
2. User pays → Stripe creates subscription → webhook fires
3. Webhook updates DB: user.subscription.plan_id = PRO plan
4. User is STILL on old JWT with tier="free" claim
5. User calls `/auth/refresh` (or logs in again) → new JWT with tier="pro"
6. User can now access `/signals/parlays` and other PRO features

---

## 2. WEBHOOK GUARANTEE

**Guarantee**: If a user has `stripe_customer_id` set, the webhook WILL update their tier.

**Precondition**: `stripe_customer_id` is set BEFORE the webhook fires.

**Flow**:
1. At checkout session creation → `stripe.Customer.create(email=user.email)`
2. Store `customer.id` in `user.stripe_customer_id`
3. Pass `customer_id` to Stripe Checkout session
4. User completes payment
5. Stripe sends `customer.subscription.created` webhook
6. Webhook looks up user by `customer_id` and updates tier

**If stripe_customer_id is not set**:
- Webhook logs a warning and returns `{"ok": True}` (safe)
- User is NOT created or updated
- No tier change occurs (expected behavior)

---

## 3. IDEMPOTENCY

**Guarantee**: Webhooks are idempotent.

If Stripe retries the same webhook event:
- The lookup by `stripe_customer_id` returns the same user
- `update_user_subscription()` atomically updates the tier
- Multiple calls produce the same result (no double-counting)

---

## 4. PRICE ID MAPPING

**Truth Source**: `STRIPE_PRICE_*` environment variables

**Mapping**:
- `STRIPE_PRICE_STARTER` → `PlanTier.STARTER`
- `STRIPE_PRICE_PRO` → `PlanTier.PRO`
- `STRIPE_PRICE_WHALE` → `PlanTier.WHALE`
- Any other price ID → `PlanTier.FREE` (default)

If a price ID is not recognized, the user defaults to FREE.

---

## 5. ENDPOINTS AFFECTED BY TIER

**Free Tier**:
- `/signals` (SLAM picks only)
- `/auth/register`, `/auth/login`, `/auth/refresh`
- `/health`

**Starter+ Tiers**:
- `/signals` (all pick confidence levels)
- `/signals/parlays` (multi-leg combinations)
- `/admin/*` (if is_admin=True)

**Enforcement**: Via `require_tier()` dependency in FastAPI routes.

---

## 6. TESTING

**Deterministic Test** (`test_subscription_lifecycle.py`):

1. Register user (FREE)
2. Set `stripe_customer_id` in DB
3. POST webhook payload (no real Stripe)
4. Verify tier updated in DB
5. Call `/auth/refresh`
6. Verify new JWT has updated tier
7. Verify `/signals/parlays` now returns 200

**Why no real Stripe?**
- Tests should not depend on external services
- Webhook payload can be simulated with correct signature
- CI/CD is reliable and fast

---

## 7. PRODUCTION DEPLOYMENT CHECKLIST

Before going live:

- [ ] `STRIPE_WEBHOOK_SECRET` is configured (from Stripe Dashboard → Webhooks)
- [ ] `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_WHALE` are set to real Stripe price IDs
- [ ] Webhook endpoint (`/webhooks/stripe`) is registered in Stripe Dashboard
- [ ] `stripe.Customer.create()` is called **before** issuing Stripe Checkout session
- [ ] User's `stripe_customer_id` is persisted **immediately** after customer creation
- [ ] All 8 validation checks pass (`validate_subscription_lifecycle.py`)
- [ ] Integration test passes with simulated webhooks

---

## 8. SUPPORT OPERATIONS

**Manual Tier Override** (for refunds, promos, etc.):

```
POST /admin/users/{user_id}/tier
{
  "tier": "pro",
  "reason": "Refund approved for user"
}
```

Requires: `user.is_admin=True`

---

## 9. KNOWN LIMITATIONS

1. **Tier change is NOT instant**: User must refresh token or re-login (see section 1)
2. **No grace period after cancellation**: User downgrades to FREE immediately (see `handle_subscription_deleted`)
3. **No dunning for past_due**: `past_due` subscriptions are treated as `active` (future improvement)

---

## 10. REFERENCES

- Stripe webhook security: https://stripe.com/docs/webhooks/signatures
- Idempotency in Stripe: https://stripe.com/docs/webhooks#idempotency
- Best practices: https://stripe.com/docs/subscriptions
"""

# This document is referenced by:
# - ufa/api/auth.py (refresh endpoint)
# - ufa/api/webhooks.py (webhook handlers)
# - ufa/billing/subscriptions.py (update_user_subscription)
# - test_subscription_lifecycle.py (integration test)
