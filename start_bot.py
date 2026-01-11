#!/usr/bin/env python3
"""Start Telegram bot (LOCKED SOP)."""
import sys
import os
import logging

# LOAD ENV FIRST - BEFORE ANY OTHER IMPORTS
from dotenv import load_dotenv
load_dotenv()

# VERIFY ENVIRONMENT
token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    print("❌ TELEGRAM_BOT_TOKEN not set in .env")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

print("="*60)
print("TELEGRAM BOT (SOP LOCKED)")
print("="*60)
print(f"Python: {sys.executable}")
print(f"Token: {len(token)} chars")
print()

# START BOT
logger.info("Starting bot...")
try:
    from ufa.services.telegram_bot import main
    main()
except KeyboardInterrupt:
    print("\n👋 Bot stopped")
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    sys.exit(1)
