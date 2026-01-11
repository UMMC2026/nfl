#!/usr/bin/env python3
"""
BOS @ SAC Game Analysis for Telegram
Analyzes extended slate with unrated stars (no official picks on this game)
Sends 6-message breakdown to subscribers
"""

import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

# Telegram config
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7545848251")

async def send_message(text: str) -> bool:
    """Send message to Telegram and return success status"""
    if not BOT_TOKEN:
        print("[!] TELEGRAM_BOT_TOKEN not set")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
        except Exception as e:
            print(f"[!] Error: {e}")
            return False

async def send_game_analysis():
    """Send 6-message BOS @ SAC breakdown to Telegram"""
    messages = [
        # Message 1: Game header
        "🏀 **BOS @ SAC (9:00 PM CST)**\n\n"
        "NO OFFICIAL PICKS on this game 👀\n"
        "But extended slate has value opportunities\n"
        "Full analysis below ↓",

        # Message 2: Why no official picks
        "❌ **NO RATED PICKS** (Unrated Stars Only)\n\n"
        "**Why This Game?**\n"
        "  • Early season (2 days rest, neutral condition)\n"
        "  • Insufficient recent sample for Jaylen Brown\n"
        "  • SAC roster transitions (Murray, Schroder variance)\n"
        "  • Bench roles still settling\n\n"
        "**Our Strategy:**\n"
        "  ✅ Conservative tier system works here\n"
        "  ✅ Wait for 3+ game sample before rating\n"
        "  ✅ Recommend extended slate plays only\n\n"
        "**Best Approach:**\n"
        "  Skip official picks | Monitor props for value | Build parlay edges",

        # Message 3: Extended slate analysis - Boston
        "[*] **BOSTON CELTICS** - Extended Slate\n\n"
        "**Jaylen Brown** (Top option)\n"
        "  • PTS O 30.5 (no edge, sharp line)\n"
        "  • BUT: AST O 5.5 (1.04x) - SLIGHT VALUE\n"
        "  • AND: 1Q PTS O 8.5 (1.06x) - SLIGHT VALUE\n"
        "  • Recommendation: Skip PTS | Monitor AST\n\n"
        "**Derrick White** (3&D Role)\n"
        "  • PTS O 19.5 (no edge marked)\n"
        "  • AST O 5.5 (1.07x) - SLIGHT VALUE ✅\n"
        "  • REB+AST O 9.5 (0.94x) - FADE\n"
        "  • Recommendation: Monitor AST O 5.5\n\n"
        "**Sam Hauser** (Bench)\n"
        "  • 3PA O 5.5 (1.08x) - VALUE ✅\n"
        "  • REB O 3.5 (1.08x) - VALUE ✅\n"
        "  • Recommendation: Volume plays, not traditional stats\n\n"
        "**Neemias Queta** (Deep bench)\n"
        "  • REB+AST O 9.5 (1.06x) - SLIGHT VALUE\n"
        "  • Blocks O 1.5 (1.12x) - VALUE ✅\n"
        "  • Recommendation: Deep contrarian play",

        # Message 4: Extended slate analysis - Sacramento
        "⭐ **SACRAMENTO KINGS** - Extended Slate\n\n"
        "**Maxime Raynaud** (Emerging star)\n"
        "  • PTS O 13.5 (1.02x) - SLIGHT VALUE\n"
        "  • REB O 8.5 (1.05x) - SLIGHT VALUE\n"
        "  • AST O 1.5 (1.13x) - VALUE ✅\n"
        "  • 3P O 0.5 (1.34x) - HIGH VALUE ⚡\n"
        "  • Recommendation: **Raynaud 3P best bet here**\n\n"
        "**Keegan Murray** (Wing)\n"
        "  • PTS O 15.5 (no edge)\n"
        "  • AST O 1.5 (1.11x) - SLIGHT VALUE\n"
        "  • 1Q PTS O 4.5 (1.07x) - VALUE\n"
        "  • Recommendation: Early game plays (1Q)\n\n"
        "**Dennis Schroder** (Bench PG)\n"
        "  • PTS O 11.5 (no edge)\n"
        "  • REB+AST O 7.5 (1.05x) - SLIGHT VALUE\n"
        "  • 3P O 1.5 (1.07x) - SLIGHT VALUE\n"
        "  • Recommendation: Even money - monitor early",

        # Message 5: Parlay strategies & best bets
        "🎲 **VALUE PARLAY COMBOS** (Extended Slate Focus)\n\n"
        "**Option 1: Volume Focus**\n"
        "  • Maxime Raynaud 3P O 0.5 (1.34x)\n"
        "  • Sam Hauser 3PA O 5.5 (1.08x)\n"
        "  • Derrick White AST O 5.5 (1.07x)\n"
        "  Combined: ~35% | Payout: 4.0x | Edge: +65%\n"
        "  Risk: Extended slate variance\n\n"
        "**Option 2: Raynaud-Led**\n"
        "  • Maxime Raynaud 3P O 0.5 (1.34x - HIGH VALUE)\n"
        "  • Maxime Raynaud REB O 8.5 (1.05x)\n"
        "  • Maxime Raynaud AST O 1.5 (1.13x)\n"
        "  Combined: ~20% | Payout: 3.5x | Edge: +55%\n"
        "  Risk: Single-player stack (high correlation)\n\n"
        "**Option 3: Contrarian (Highest Risk)**\n"
        "  • Neemias Queta BLK O 1.5 (1.12x)\n"
        "  • Sam Hauser REB O 3.5 (1.08x)\n"
        "  • Keegan Murray 1Q PTS O 4.5 (1.07x)\n"
        "  Combined: ~25% | Payout: 4.2x | Edge: +58%\n\n"
        "⚠️ **Best Single Pick:** Raynaud 3P O 0.5 (1.34x edge)",

        # Message 6: Game strategy & final notes
        "📋 **GAME STRATEGY & MONITORING**\n\n"
        "**Matchup Context:**\n"
        "  • BOS (16-11 pace, +4 PT diff) - Slight favorite\n"
        "  • SAC (14-13 pace, +1 PT diff) - Competitive\n"
        "  • Expected: Medium pace, tight game\n"
        "  • Travel: BOS on road (normal fatigue)\n\n"
        "**Game Flow Notes:**\n"
        "  ✓ Early 1Q: Keegan Murray value (1.07x 1Q PTS)\n"
        "  ✓ Bench depth: Raynaud & Queta emerge in 2-3Q\n"
        "  ✓ If BOS controls: Hauser 3PA increases\n"
        "  ✓ If SAC stays close: More Schroder minutes\n\n"
        "**Our Recommendation:**\n"
        "  ❌ Skip official picks (insufficient data)\n"
        "  ✅ Play Raynaud 3P O 0.5 (1.34x - HIGH VALUE)\n"
        "  ✅ Monitor Derrick White AST O 5.5 (1.07x)\n"
        "  ✅ Build if edges align mid-game\n\n"
        "🚨 **Bottom Line:** No full confidence picks here.\n"
        "Extended slate plays only. Raynaud 3P is the outlier (1.34x)."
    ]

    print("[*] Sending BOS @ SAC game analysis to Telegram...")
    for i, msg in enumerate(messages, 1):
        success = await send_message(msg)
        if success:
            print(f"  [+] Message {i}/{len(messages)} sent")
        else:
            print(f"  [-] Message {i}/{len(messages)} failed")
            return False
        await asyncio.sleep(0.5)  # Rate limit

    print("[+] BOS @ SAC analysis sent to Telegram!")
    return True

if __name__ == "__main__":
    asyncio.run(send_game_analysis())
