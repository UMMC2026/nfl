"""Stripe configuration and constants."""

import os
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "pk_test_REPLACE_ME")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_REPLACE_ME")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_REPLACE_ME")  # Set in your .env file

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
