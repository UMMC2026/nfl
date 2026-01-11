"""FastAPI app integration guide for Stripe monetization.

Quick Start:
    1. Update stripe_config.py with price IDs and webhook secret
    2. Include routers in your FastAPI app
    3. Add authentication middleware to extract user ID from JWT/session
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from stripe_webhooks import router as stripe_router
from stripe_analysis_routes import router as analysis_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("🚀 Starting Underdog Fantasy Analyzer API")
    logger.info("💳 Stripe integration loaded")
    logger.info("📊 Analysis routes available at /analysis/")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="Underdog Fantasy Analyzer API",
        description="Monetized betting analysis with Stripe integration",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict this
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(stripe_router)
    app.include_router(analysis_router)
    
    # Health check
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "Underdog Fantasy Analyzer"}
    
    return app


# Create app instance
app = create_app()


# ============================================================================
# INTEGRATION INSTRUCTIONS
# ============================================================================
"""
To integrate this with your existing API or CLI:

1. ENVIRONMENT VARIABLES (instead of hardcoding in stripe_config.py):
   
   .env file:
   ────────────────────────────────────────────
   STRIPE_PUBLIC_KEY=pk_test_...
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_test_...
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ────────────────────────────────────────────
   
   Then in stripe_config.py:
   ────────────────────────────────────────────
   import os
   from dotenv import load_dotenv
   
   load_dotenv()
   STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
   ────────────────────────────────────────────

2. USER AUTHENTICATION:
   
   Add middleware to extract user ID from JWT or session:
   
   ────────────────────────────────────────────
   from fastapi import Request, HTTPException
   from fastapi.middleware.base import BaseHTTPMiddleware
   
   class UserIDMiddleware(BaseHTTPMiddleware):
       async def dispatch(self, request: Request, call_next):
           # Extract from JWT
           auth_header = request.headers.get("Authorization")
           if auth_header:
               token = auth_header.split(" ")[1]
               user_id = decode_jwt(token)  # Your JWT decoder
               request.state.user_id = user_id
           
           response = await call_next(request)
           return response
   
   app.add_middleware(UserIDMiddleware)
   ────────────────────────────────────────────

3. STRIPE WEBHOOK URL:
   
   In Stripe Dashboard (Developers → Webhooks):
   
   Endpoint URL: https://your-domain.com/stripe/webhook
   
   Select events:
   - customer.subscription.created
   - customer.subscription.updated
   - customer.subscription.deleted
   - invoice.payment_succeeded
   
   Copy the signing secret and update stripe_config.py:
   STRIPE_WEBHOOK_SECRET = "whsec_..."

4. PRICE IDs:
   
   In Stripe Dashboard (Products):
   
   For each product, get the Price ID:
   - Starter → price_1Sk9CV...
   - PRO → price_1Sk9CV...
   - Whale → price_1Sk9CV...
   
   Update stripe_config.py PRODUCTS dict

5. SERVE CHEATSHEET BY TIER:
   
   Your daily analysis script:
   ────────────────────────────────────────────
   # After generating cheatsheet.txt
   from stripe_db import Subscription
   
   for user in get_active_subscribers():
       tier = Subscription.get_tier(user.id)
       
       # Serve based on tier
       if tier == "starter":
           serve_basic_cheatsheet(user)
       elif tier == "pro":
           serve_cheatsheet_with_commentary(user)
       elif tier == "whale":
           serve_full_analysis_with_alerts(user)
   ────────────────────────────────────────────

6. RUN THE API:
   
   uvicorn stripe_integration:app --reload
   
   Then test:
   - POST http://localhost:8000/stripe/webhook (with X-Stripe-Signature)
   - GET http://localhost:8000/analysis/dashboard (with X-User-ID header)

"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
