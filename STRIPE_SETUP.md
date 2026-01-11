"""
STRIPE MONETIZATION SETUP GUIDE
================================

This guide walks through integrating Stripe for the Underdog Fantasy Analyzer.

Current Status:
✅ stripe_config.py (credentials, products)
✅ stripe_db.py (subscription database)
✅ stripe_webhooks.py (webhook handler)
✅ stripe_analysis_routes.py (tier-gated endpoints)
✅ stripe_integration.py (FastAPI app)
⏳ Remaining: Stripe dashboard configuration + environment setup


STEP 1: UPDATE STRIPE CREDENTIALS
==================================

Location: stripe_config.py

Option A (DEVELOPMENT - Simple, for testing):
────────────────────────────────────────────
Already done! stripe_config.py has your API keys hardcoded.
STRIPE_PUBLIC_KEY = "pk_test_..."
STRIPE_SECRET_KEY = "sk_test_..."

⚠️  NEVER commit this to public repos!


Option B (PRODUCTION - Secure, recommended):
────────────────────────────────────────────
1. Create a .env file:

   STRIPE_PUBLIC_KEY=pk_test_...
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_test_...  (leave empty for now)
   TELEGRAM_BOT_TOKEN=  (optional)
   TELEGRAM_CHAT_ID=  (optional)

2. Update stripe_config.py:

   import os
   from dotenv import load_dotenv
   
   load_dotenv()
   
   STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
   STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
   ...

3. Add to .gitignore:
   .env
   *.db


STEP 2: GET PRICE IDs FROM STRIPE
==================================

Location: https://dashboard.stripe.com/test/products

For each product (Starter, PRO, Whale):
1. Click on product name
2. Go to "Pricing" section
3. Copy the Price ID (looks like: price_1Sk9CV...)
4. Update stripe_config.py:

    PRODUCTS = {
        "starter": {
            "price_id": "price_1Sk9CV...",  # FILL THIS IN
            "tier": "starter",
            "name": "Starter",
            "price": 1999,
            "access": ["cheatsheet"],
        },
        "pro": {
            "price_id": "price_1Sk9CV...",  # FILL THIS IN
            ...
        },
        "whale": {
            "price_id": "price_1Sk9CV...",  # FILL THIS IN
            ...
        },
    }


STEP 3: CREATE WEBHOOK ENDPOINT
================================

Location: https://dashboard.stripe.com/test/webhooks

1. Click "Add endpoint"

2. Enter endpoint URL:
   (Choose one based on where you'll host the API)
   
   Local/Development:
   http://localhost:8000/stripe/webhook
   
   Production/Cloud:
   https://your-domain.com/stripe/webhook
   https://your-api.herokuapp.com/stripe/webhook
   https://your-api.replit.com/stripe/webhook

3. Select events to listen for:
   ☑️ customer.subscription.created
   ☑️ customer.subscription.updated
   ☑️ customer.subscription.deleted
   ☑️ invoice.payment_succeeded

4. Click "Add endpoint"

5. Copy the Signing Secret (whsec_...) and update stripe_config.py:
   STRIPE_WEBHOOK_SECRET = "whsec_test_..."


STEP 4: INSTALL DEPENDENCIES
=============================

pip install fastapi uvicorn stripe aiohttp

Optional:
pip install python-dotenv  # for .env file support
pip install pytest  # for testing


STEP 5: TEST LOCALLY
====================

Terminal 1 - Start the API:
────────────────────────────
cd c:\Users\hiday\UNDERDOG ANANLYSIS
python -m uvicorn stripe_integration:app --reload

Expected output:
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
🚀 Starting Underdog Fantasy Analyzer API
💳 Stripe integration loaded


Terminal 2 - Test health check:
────────────────────────────────
curl http://localhost:8000/health

Expected response:
{"status":"ok","service":"Underdog Fantasy Analyzer"}


STEP 6: SIMULATE WEBHOOK (DEVELOPMENT)
=======================================

Using Stripe CLI (https://stripe.com/docs/stripe-cli):

1. Install Stripe CLI
   Windows: choco install stripe-cli
   Mac: brew install stripe/stripe-cli/stripe
   Linux: sudo apt-get install -y stripe

2. Login to your account:
   stripe login

3. Forward webhooks to local:
   stripe listen --forward-to localhost:8000/stripe/webhook

4. Trigger test event:
   stripe trigger customer.subscription.created

   You should see in the API logs:
   ✅ Subscription created: test@example.com (starter)


STEP 7: INTEGRATE WITH ANALYSIS ROUTES
=======================================

Option A: FastAPI app with authentication:
────────────────────────────────────────────

from fastapi import Request, HTTPException
from stripe_db import Subscription

@app.get("/analysis/cheatsheet")
async def get_cheatsheet(request: Request):
    user_id = request.headers.get("X-User-ID")
    tier = Subscription.get_tier(user_id)
    
    if tier not in ["starter", "pro", "whale"]:
        raise HTTPException(status_code=403, detail="No active subscription")
    
    # Serve cheatsheet file
    return FileResponse("outputs/cheatsheet.txt")


Option B: Modify your CLI to gate outputs:
────────────────────────────────────────────

from stripe_db import Subscription

# After generating daily analysis:
tier = Subscription.get_tier(user_id)

if tier == "starter":
    publish_file("outputs/cheatsheet_basic.txt", user_email)

elif tier == "pro":
    publish_file("outputs/cheatsheet_full.txt", user_email)
    publish_file("outputs/commentary_pro.txt", user_email)

elif tier == "whale":
    publish_file("outputs/cheatsheet_full.txt", user_email)
    publish_file("outputs/commentary_pro.txt", user_email)
    await notify_telegram(user_email, "Daily analysis ready!")


STEP 8: SEND DAILY ANALYSIS BY TIER
====================================

Example: Email service for daily cheatsheets

from stripe_db import User, Subscription

# After generating daily cheatsheet
for user in User.get_all_active_subscribers():
    tier = Subscription.get_tier(user.id)
    
    subject = f"Daily Analysis ({tier.upper()})"
    
    if tier == "starter":
        body = open("outputs/cheatsheet.txt").read()
    elif tier == "pro":
        body = open("outputs/cheatsheet.txt").read()
        body += "\n\n" + open("outputs/commentary.txt").read()
    elif tier == "whale":
        body = open("outputs/cheatsheet.txt").read()
        body += "\n\n" + open("outputs/commentary.txt").read()
        # Also send via Telegram
        from telegram_notifier import notify_daily_analysis
        await notify_daily_analysis(tier, {"date": "today", "game_count": 5})
    
    send_email(user.email, subject, body)


STEP 9: ENABLE TELEGRAM NOTIFICATIONS (OPTIONAL)
================================================

1. Create a Telegram bot:
   - Open Telegram, find @BotFather
   - /newbot
   - Name: "Underdog Analytics"
   - Handle: "underdog_analytics_bot" (or similar)
   - Copy the bot token

2. Get your chat ID:
   - Forward a message to your new bot
   - Visit: https://api.telegram.org/bot{TOKEN}/getUpdates
   - Copy the chat ID from the response

3. Update stripe_config.py:
   TELEGRAM_BOT_TOKEN = "123456:ABC..."
   TELEGRAM_CHAT_ID = "123456789"

4. Test:
   python
   >>> from telegram_notifier import send_telegram_message
   >>> import asyncio
   >>> asyncio.run(send_telegram_message("Test message"))
   ✅ Message sent


STEP 10: DEPLOY TO PRODUCTION
=============================

Option A: Heroku (Free tier available)
──────────────────────────────────────

1. Create Procfile:
   web: uvicorn stripe_integration:app --host 0.0.0.0 --port $PORT

2. Create requirements.txt:
   pip freeze > requirements.txt

3. Initialize git and push:
   git init
   git add .
   git commit -m "Initial commit"
   heroku create your-app-name
   git push heroku main

4. Set environment variables:
   heroku config:set STRIPE_SECRET_KEY=sk_test_...
   heroku config:set STRIPE_WEBHOOK_SECRET=whsec_test_...

5. Update Stripe webhook URL:
   https://your-app-name.herokuapp.com/stripe/webhook


Option B: Railway or Replit
────────────────────────────

Similar process. See their docs.


STEP 11: VERIFY EVERYTHING
===========================

Checklist:

☑️ stripe_config.py has API keys (test or env vars)
☑️ stripe_config.py has price IDs for all 3 products
☑️ stripe_db.py creates data/subscribers.db on import
☑️ stripe_webhooks.py can be imported without errors
☑️ Stripe webhook endpoint configured in dashboard
☑️ stripe_integration:app runs without errors
☑️ /health endpoint returns {"status": "ok"}
☑️ Webhook can verify signatures (test with Stripe CLI)
☑️ User can create test subscription via Stripe UI
☑️ Subscription appears in data/subscribers.db


TROUBLESHOOTING
===============

Issue: "ValueError: Invalid webhook signature"
Fix: Check STRIPE_WEBHOOK_SECRET matches dashboard

Issue: "sqlite3.IntegrityError: UNIQUE constraint failed"
Fix: User already exists, check User.get_by_email() before create

Issue: "FileNotFoundError: outputs/cheatsheet.txt"
Fix: Make sure daily analysis script runs before serving

Issue: Webhook not triggered
Fix: Use Stripe CLI to forward: stripe listen --forward-to localhost:8000/stripe/webhook

Issue: ModuleNotFoundError for stripe
Fix: pip install stripe


NEXT STEPS
==========

1. Fill in price IDs from Stripe dashboard (STEP 2)
2. Create webhook endpoint (STEP 3)
3. Test locally with Stripe CLI (STEP 6)
4. Deploy to production (STEP 10)
5. Gate your daily analysis files by tier (STEP 7-8)
6. Optional: Set up Telegram notifications (STEP 9)


FILES CREATED
=============

stripe_config.py ..................... Credentials and product definitions
stripe_db.py ......................... SQLite ORM for subscriptions
stripe_webhooks.py ................... Webhook event handler
stripe_analysis_routes.py ........... Tier-gated file serving
stripe_access_control.py ............ Access control utilities
stripe_integration.py ............... FastAPI app
telegram_notifier.py ................. Telegram notifications
STRIPE_SETUP.md (this file) ......... Setup guide


SUPPORT
=======

Documentation:
- Stripe: https://stripe.com/docs/payments/checkout
- FastAPI: https://fastapi.tiangolo.com/
- SQLite: https://www.sqlite.org/docs.html

Questions?
- Check the code comments in each file
- See stripe_integration.py for integration examples
- Review stripe_analysis_routes.py for tier gating patterns

"""
