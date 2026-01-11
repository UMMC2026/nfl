"""Stripe configuration and constants."""

STRIPE_PUBLIC_KEY = "pk_test_51Sk9CVAmdkLb1k5vxoFjfMBZ6XRmEGDm0FbA7jn4tDEYbbYwu7qjKvFrm8vsHI8q1HPZYlRjEXGvlhdC5azjfcKX00qk4YuV8U"
STRIPE_SECRET_KEY = "sk_test_51Sk9CVAmdkLb1k5vK9pMB2R4scVZlVHa8UhCNKiZE3e2BOBoy13fTTth8PmjSUKHQduB0DsbcIgp3WO3DqK0lgBw00YTq6VD58"
STRIPE_WEBHOOK_SECRET = "whsec_test_"  # Get from Developers > Webhooks after creating endpoint

# Product IDs from your Stripe account (need to fetch these from dashboard)
PRODUCTS = {
    "starter": {
        "price_id": "price_1Sk9CV...",  # Fill in from Stripe
        "tier": "starter",
        "name": "Starter",
        "price": 1999,  # in cents
        "access": ["cheatsheet"],
    },
    "pro": {
        "price_id": "price_1Sk9CV...",
        "tier": "pro",
        "name": "PRO",
        "price": 4900,
        "access": ["cheatsheet", "commentary", "correlations"],
    },
    "whale": {
        "price_id": "price_1Sk9CV...",
        "tier": "whale",
        "name": "Whale",
        "price": 19900,
        "access": ["cheatsheet", "commentary", "correlations", "telegram_alerts", "live_updates"],
    },
}

# Telegram configuration
TELEGRAM_BOT_TOKEN = ""  # Set this when you create a Telegram bot
TELEGRAM_CHAT_ID = ""  # Your chat ID for notifications
