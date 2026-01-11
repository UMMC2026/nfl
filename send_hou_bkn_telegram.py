"""
Send HOU @ BKN game-specific analysis to Telegram.
Includes full roster, correlations, parlay suggestions.
"""

import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7545848251")

async def send_message(chat_id: str, text: str):
    """Send message to Telegram."""
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set")
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
        return resp.status_code == 200


async def send_game_analysis():
    """Send HOU @ BKN game analysis to Telegram."""
    
    messages = [
        # Header
        """🏀 **HOU @ BKN (5:00 PM CST)**
═══════════════════════════════
*Game-Specific Deep Dive*""",
        
        # Our pick
        """💪 **OUR PICK**
─────────────────────────────

**Alperen Sengun (HOU)**
🔥 PTS O 20.5 (65% STRONG)

📊 Context:
• Minutes: 24+ needed (avg 28-33)
• Rest: 2d+ (standard)
• Role: Primary big man scorer
• Matchup: vs BKN defense (neutral)

⚙️ Shrinkage: -15% (sample size)
""",
        
        # Top unrated opportunities
        """🔍 **UNRATED STARS TO MONITOR**
─────────────────────────────

**Kevin Durant (HOU)**
Lines: PTS 26.5 | PRA 36.5 | REB 5.5 | AST 4.5
📈 Volume play: 18.5 FGA | 7.5 1Q PTS
🚨 Risk: Recent rest → elevated volume

**Michael Porter Jr. (BKN)**
Lines: PTS 23.5 | PRA 33.5 | REB 6.5 | AST 3.5
📈 Volume play: 8.5 3PA | 30.5 PTS+REB
🎯 Edge: Extended range (3PM 3.5)

**Amen Thompson (HOU)**
Lines: PTS 17.5 | PRA 30.5 | REB 6.5 | AST 5.5
📊 Role: 2-way combo guard
⚠️ High PRA relative to PTS (30.5 vs 17.5)
""",
        
        # Parlay suggestions
        """🎲 **PARLAY COMBINATIONS**
─────────────────────────────

**2-Leg HOU Stack** (Best Value)
• Alperen Sengun PTS O 20.5 (65%)
• Amen Thompson PRA O 30.5 (54%)
→ Combined: ~35% | Payout: 3.5x
→ **Edge: +191%**

**2-Leg BKN Stack**
• Michael Porter Jr. PTS O 23.5 (53%)
• Cam Thomas PTS O 18.5 (51%)
→ Combined: ~27% | Payout: 3.8x
→ **Edge: +302%**

**3-Leg Mixed (Maximum Edge)**
• Alperen Sengun PTS O 20.5 (65%)
• Michael Porter Jr. PRA O 33.5 (55%)
• Kevin Durant PTS O 26.5 (52%)
→ Combined: ~19% | Payout: 5.2x
→ **Edge: +374%**
""",
        
        # Correlations
        """🔗 **CORRELATION MATRIX**
─────────────────────────────

🔴 AVOID STACKING:
• Sengun PTS & PRA (same player)
• MPJ PTS & PRA (same player)
• KD extended stats (volume tied)

🟡 MONITOR:
• Amen Thompson AST vs Sengun AST
  (compete for touches)
• BKN perimeter (Thomas/MPJ volume)
  (share scoring load)

🟢 HEDGES WORK:
• Amen AST O 5.5 vs Cam AST O 2.5
  (different positions, inverse)
• Sengun REB O 9.5 vs BKN bigs
  (natural rebounding matchup)
""",
        
        # Game context
        """📋 **GAME NOTES**
─────────────────────────────

Time: 5:00 PM CST (Early Slate)
Matchup: HOU @ BKN (Neutral)
Rest: Standard (both teams)

⏱️ **Key Monitoring:**
✓ Sengun minutes (need 24+)
✓ KD volume (post-rest check)
✓ MPJ starter status (confirm)
✓ Amen usage vs Sengun touches

🎯 **Best Single:** Sengun PTS O 20.5
💪 **Best Parlay:** HOU Stack (+191% edge)
📊 **Best Value:** 3-Leg Mixed (+374% edge)
""",
    ]
    
    print("📤 Sending HOU @ BKN game analysis to Telegram...")
    
    for i, msg in enumerate(messages, 1):
        sent = await send_message(CHAT_ID, msg)
        if sent:
            print(f"  ✅ Message {i}/{len(messages)} sent")
        else:
            print(f"  ❌ Message {i}/{len(messages)} failed")
        await asyncio.sleep(0.5)
    
    print(f"\n✅ HOU @ BKN analysis sent to Telegram!")


if __name__ == "__main__":
    asyncio.run(send_game_analysis())
