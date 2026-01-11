#!/usr/bin/env python3
"""
Persistent Telegram bot runner with restart on failure.

Keeps the bot running, auto-restarts if it crashes.
"""
import subprocess
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

BOT_SCRIPT = Path("start_bot.py")
MAX_RESTARTS = 10
RESTART_DELAY = 5  # seconds

def run_bot_persistent():
    """Run bot with auto-restart on failure."""
    restarts = 0
    
    while restarts < MAX_RESTARTS:
        try:
            logger.info("Starting Telegram bot...")
            result = subprocess.run([
                "python",
                str(BOT_SCRIPT)
            ])
            
            if result.returncode == 0:
                logger.info("Bot stopped normally")
                break
            else:
                logger.warning(f"Bot crashed with code {result.returncode}")
                restarts += 1
                
                if restarts < MAX_RESTARTS:
                    logger.info(f"Restarting in {RESTART_DELAY}s... (attempt {restarts}/{MAX_RESTARTS})")
                    time.sleep(RESTART_DELAY)
        
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            restarts += 1
            time.sleep(RESTART_DELAY)
    
    logger.info("Bot runner stopped")

if __name__ == "__main__":
    run_bot_persistent()
