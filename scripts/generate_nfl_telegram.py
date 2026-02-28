"""
Generate NFL Top 10 Picks for Telegram
Shows example format using available markets
"""
import sys
from pathlib import Path

# Direct import to avoid package initialization issues
nfl_markets_path = Path(__file__).parent.parent / "engines" / "nfl"
sys.path.insert(0, str(nfl_markets_path))

from nfl_markets import NFLMarket, MARKET_DISPLAY_NAMES

# Example top 10 picks (demonstrating format)
# In production, these would come from your simulation engine
demo_picks = [
    {
        "player": "Patrick Mahomes",
        "team": "KC",
        "market": NFLMarket.PASS_YARDS,
        "line": 275.5,
        "direction": "OVER",
        "probability": 68.5,
        "tier": "STRONG"
    },
    {
        "player": "Christian McCaffrey",
        "team": "SF",
        "market": NFLMarket.RUSH_REC_YARDS,
        "line": 125.5,
        "direction": "OVER",
        "probability": 72.3,
        "tier": "STRONG"
    },
    {
        "player": "Travis Kelce",
        "team": "KC",
        "market": NFLMarket.REC_YARDS,
        "line": 65.5,
        "direction": "OVER",
        "probability": 65.8,
        "tier": "STRONG"
    },
    {
        "player": "Lamar Jackson",
        "team": "BAL",
        "market": NFLMarket.PASS_RUSH_YARDS,
        "line": 285.5,
        "direction": "OVER",
        "probability": 70.2,
        "tier": "STRONG"
    },
    {
        "player": "Josh Allen",
        "team": "BUF",
        "market": NFLMarket.PASS_TDS,
        "line": 2.5,
        "direction": "OVER",
        "probability": 64.1,
        "tier": "STRONG"
    },
    {
        "player": "Tyreek Hill",
        "team": "MIA",
        "market": NFLMarket.REC_YARDS,
        "line": 85.5,
        "direction": "OVER",
        "probability": 66.7,
        "tier": "STRONG"
    },
    {
        "player": "Derrick Henry",
        "team": "BAL",
        "market": NFLMarket.RUSH_YARDS,
        "line": 75.5,
        "direction": "OVER",
        "probability": 63.9,
        "tier": "LEAN"
    },
    {
        "player": "CeeDee Lamb",
        "team": "DAL",
        "market": NFLMarket.RECEPTIONS,
        "line": 6.5,
        "direction": "OVER",
        "probability": 62.4,
        "tier": "LEAN"
    },
    {
        "player": "Brock Purdy",
        "team": "SF",
        "market": NFLMarket.PASS_COMPLETIONS,
        "line": 22.5,
        "direction": "OVER",
        "probability": 61.8,
        "tier": "LEAN"
    },
    {
        "player": "Justin Tucker",
        "team": "BAL",
        "market": NFLMarket.FG_MADE,
        "line": 1.5,
        "direction": "OVER",
        "probability": 60.5,
        "tier": "LEAN"
    }
]

def generate_telegram_message(picks, sport="NFL"):
    """Generate Telegram-formatted message for top picks."""
    
    # Header
    message = f"🏈 *{sport} TOP 10 PICKS*\n"
    message += f"{'='*40}\n\n"
    
    # Group by tier
    strong_picks = [p for p in picks if p['tier'] == 'STRONG']
    lean_picks = [p for p in picks if p['tier'] == 'LEAN']
    
    if strong_picks:
        message += "💪 *STRONG PLAYS*\n"
        for pick in strong_picks:
            market_name = MARKET_DISPLAY_NAMES.get(pick['market'], pick['market'].value.replace('_', ' ').title())
            emoji = "📈" if pick['direction'] == "OVER" else "📉"
            message += (
                f"{emoji} *{pick['player']}* ({pick['team']})\n"
                f"   {market_name} {pick['direction']} {pick['line']}\n"
                f"   Edge: {pick['probability']:.1f}%\n\n"
            )
    
    if lean_picks:
        message += "⚡ *LEAN PLAYS*\n"
        for pick in lean_picks:
            market_name = MARKET_DISPLAY_NAMES.get(pick['market'], pick['market'].value.replace('_', ' ').title())
            emoji = "📈" if pick['direction'] == "OVER" else "📉"
            message += (
                f"{emoji} *{pick['player']}* ({pick['team']})\n"
                f"   {market_name} {pick['direction']} {pick['line']}\n"
                f"   Edge: {pick['probability']:.1f}%\n\n"
            )
    
    message += f"{'='*40}\n"
    message += "🎯 Risk-First Analysis | Drive-Level MC\n"
    
    return message

if __name__ == "__main__":
    # Generate message
    telegram_msg = generate_telegram_message(demo_picks)
    
    # Print to console
    print("\n" + "="*60)
    print("TELEGRAM MESSAGE (Copy & Send)")
    print("="*60 + "\n")
    print(telegram_msg)
    print("\n" + "="*60 + "\n")
    
    # Optionally send via Telegram
    try:
        from telegram_push import _send as telegram_send
        
        user_input = input("Send to Telegram? (y/n): ").lower()
        if user_input == 'y':
            if telegram_send(telegram_msg):
                print("✅ Message sent to Telegram!")
            else:
                print("⚠️  Telegram send failed (check bot token/chat ID)")
    except ImportError:
        print("ℹ️  Telegram module not available for auto-send")
    except KeyboardInterrupt:
        print("\n\nCancelled.")
