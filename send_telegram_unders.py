#!/usr/bin/env python3
"""
Send only UNDER picks grouped by opponent matchup to Telegram.
Perfect for focused under/fade strategies.
"""

import json
import asyncio
import os
import sys
import io
from pathlib import Path
from collections import defaultdict

# UTF-8 encoding fix for Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import httpx
from dotenv import load_dotenv

load_dotenv()

# Known matchups for this week
MATCHUPS = {
    "HOU": "BKN",
    "BKN": "HOU",
    "DET": "MIA",
    "MIA": "DET",
    "PHI": "DAL",
    "DAL": "PHI",
}

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")[0] if os.getenv("ADMIN_TELEGRAM_IDS") else None

async def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send message to Telegram."""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing TELEGRAM_BOT_TOKEN or ADMIN_TELEGRAM_IDS")
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json={
                    "chat_id": CHAT_ID,
                    "text": text,
                    "parse_mode": parse_mode,
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            else:
                print(f"❌ Telegram error: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error sending to Telegram: {e}")
            return False

def get_confidence_tier(prob):
    """Return confidence tier and emoji."""
    if prob is None:
        return "?%", "❓"
    if prob >= 0.68:
        return f"{prob*100:.0f}%", "🔒"
    elif prob >= 0.60:
        return f"{prob*100:.0f}%", "✅"
    elif prob >= 0.52:
        return f"{prob*100:.0f}%", "⚠️"
    elif prob >= 0.48:
        return f"{prob*100:.0f}%", "🔄"
    else:
        return f"{prob*100:.0f}%", "❌"

def format_matchup_message(matchup, teams_picks):
    """Format a single matchup for Telegram (unders only)."""
    team1, team2 = matchup
    
    # Build message
    lines = [
        f"<b>⚔️ {team1} vs {team2} (UNDERS)</b>",
        ""
    ]
    
    # Display each team's picks
    for team in sorted(teams_picks.keys()):
        picks = teams_picks[team]
        
        # Filter to unders only
        under_picks = [p for p in picks if p.get("direction") == "lower"]
        
        if under_picks:
            lines.append(f"<b>{team} ({len(under_picks)} unders):</b>")
            
            # Sort by player name
            for pick in sorted(under_picks, key=lambda p: p.get("player", "")):
                player = pick.get("player", "Unknown")
                line = pick.get("line", "?")
                stat = pick.get("stat", "?")
                
                # Get hydration data
                mu = pick.get("mu")
                sigma = pick.get("sigma")
                
                # Calculate probability
                prob = pick.get("prob_hit")
                prob_str, tier_emoji = get_confidence_tier(prob)
                
                # Build line
                if mu is not None and sigma is not None:
                    pick_line = f"  • {player} U{line} ({stat}) [{prob_str} {tier_emoji}] μ={mu:.1f}"
                else:
                    pick_line = f"  • {player} U{line} ({stat}) [{prob_str} {tier_emoji}]"
                
                lines.append(pick_line)
            
            lines.append("")
    
    # Return only if there are unders in this matchup
    if len(lines) > 2:  # More than just header and blank line
        return "\n".join(lines)
    else:
        return None

def group_picks_by_team(hydrated_data):
    """Group picks by team (for all unders)."""
    teams = defaultdict(list)
    
    for pick in hydrated_data:
        team = pick.get("team", "UNK")
        teams[team].append(pick)
    
    return teams

async def main():
    """Send all under picks grouped by team to Telegram."""
    
    hydrated_file = Path("picks_hydrated.json")
    if not hydrated_file.exists():
        print("❌ picks_hydrated.json not found")
        return
    
    print("📤 Loading picks...")
    with open(hydrated_file) as f:
        hydrated_data = json.load(f)
    
    print(f"📊 Found {len(hydrated_data)} picks")
    
    # Filter to unders
    under_picks = [p for p in hydrated_data if p.get("direction") == "lower"]
    print(f"📉 Filtered to {len(under_picks)} UNDER picks")
    
    # Group by team
    teams = group_picks_by_team(under_picks)
    
    if not teams:
        print("❌ No unders found")
        return
    
    print(f"🎮 Found unders from {len(teams)} teams\n")
    
    # Send each team's unders
    sent = 0
    for team in sorted(teams.keys()):
        picks = teams[team]
        
        if not picks:
            continue
        
        # Build message
        lines = [f"<b>📉 {team} UNDERS ({len(picks)} picks)</b>", ""]
        
        for pick in sorted(picks, key=lambda p: p.get("player", "")):
            player = pick.get("player", "Unknown")
            line = pick.get("line", "?")
            stat = pick.get("stat", "?")
            
            mu = pick.get("mu")
            sigma = pick.get("sigma")
            prob = pick.get("prob_hit")
            prob_str, tier_emoji = get_confidence_tier(prob)
            
            if mu is not None and sigma is not None:
                pick_line = f"  • {player} U{line} ({stat}) [{prob_str} {tier_emoji}] μ={mu:.1f}"
            else:
                pick_line = f"  • {player} U{line} ({stat}) [{prob_str} {tier_emoji}]"
            
            lines.append(pick_line)
        
        message = "\n".join(lines)
        
        print(f"📤 Sending {team} unders...")
        
        if await send_message(message):
            sent += 1
            print(f"   ✅ Sent")
        else:
            print(f"   ❌ Failed")
        
        await asyncio.sleep(0.5)
    
    # Summary
    summary = f"\n✅ Under picks sent! ({sent} teams)"
    print(summary)
    await send_message(summary)

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)
    
    if not CHAT_ID:
        print("❌ ADMIN_TELEGRAM_IDS not set in .env")
        sys.exit(1)
    
    asyncio.run(main())
