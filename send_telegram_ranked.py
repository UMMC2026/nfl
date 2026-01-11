"""
Send ranked picks to Telegram with detailed stats and context.

Supports:
- TIER-BASED: Group by confidence tier (SLAM, STRONG, LEAN)
- TOP-N: Show top 10, 20, 30 picks
- WITH-CONTEXT: Include minutes, rest, usage, matchup data

Usage:
    python send_telegram_ranked.py --format tier --top 20
    python send_telegram_ranked.py --format top --top 10 --with-context
    python send_telegram_ranked.py --chat-id <ID>
"""

import os
import json
import asyncio
import argparse
import sys
import io
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx
from dotenv import load_dotenv

# Fix UTF-8 encoding on Windows
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")[0])


async def send_message(chat_id: str, text: str, parse_mode: str = "Markdown"):
    """Send a message to Telegram using httpx."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            print(f"⚠️ Telegram API error: {resp.text}")
        return resp.json()


def load_ranked_picks() -> list[dict]:
    """Load and calibrate picks from pipeline."""
    from ufa.daily_pipeline import DailyPipeline
    import json
    
    picks_file = Path("picks_hydrated.json")
    if not picks_file.exists():
        print("❌ picks_hydrated.json not found. Run hydration first.")
        return []
    
    with open(picks_file) as f:
        picks = json.load(f)
    
    # Process through pipeline to get calibrated data
    pipeline = DailyPipeline()
    pipeline.picks = picks
    calibrated = pipeline.process_picks()
    
    # Sort by tier then probability
    tier_order = {"SLAM": 0, "STRONG": 1, "LEAN": 2, "FLIP": 3, "FADE": 4}
    calibrated.sort(
        key=lambda x: (tier_order.get(x.get("tier", "FADE"), 5), -x.get("display_prob", 0))
    )
    
    return calibrated


def format_tier_based(picks: list[dict], top_n: int = 100, with_context: bool = False) -> list[str]:
    """Format picks grouped by tier."""
    messages = []
    
    # Group by tier
    by_tier = {}
    for p in picks:
        tier = p.get("tier", "FADE")
        if tier not in by_tier:
            by_tier[tier] = []
        by_tier[tier].append(p)
    
    tier_order = ["SLAM", "STRONG", "LEAN", "FLIP", "FADE"]
    
    for tier in tier_order:
        if tier not in by_tier or not by_tier[tier]:
            continue
        
        tier_picks = by_tier[tier][:10]  # Limit to 10 per tier per message
        
        # Determine emoji
        emoji = {"SLAM": "🔥", "STRONG": "💪", "LEAN": "📊", "FLIP": "🔄", "FADE": "📉"}.get(tier, "❓")
        
        lines = [
            f"{emoji} **{tier.upper()} PLAYS**",
            "━" * 45,
        ]
        
        for i, pick in enumerate(tier_picks, 1):
            dir_sym = "⬆️" if pick.get("direction") == "higher" else "⬇️"
            prob = pick.get("display_prob", 0.5) * 100
            player = pick.get("player", "Unknown")
            team = pick.get("team", "")
            line = pick.get("line", 0)
            stat = pick.get("stat", "")
            
            lines.append(f"\n{i}. **{player}** ({team}) {dir_sym} {line} {stat}")
            lines.append(f"   📊 **{prob:.0f}%** confidence")
            
            # Add context if requested
            if with_context:
                context = pick.get("context", {}).get("formatted", "")
                if context:
                    # Truncate long context
                    ctx_short = context[:80]
                    lines.append(f"   📋 {ctx_short}")
                
                # Add adjustments
                adjustments = pick.get("adjustments", [])
                if adjustments:
                    adj_str = " + ".join(adjustments[:2])
                    lines.append(f"   ⚙️ _{adj_str}_")
        
        messages.append("\n".join(lines))
    
    return messages


def format_top_n(picks: list[dict], top_n: int = 20, with_context: bool = False) -> list[str]:
    """Format top N picks in messages."""
    messages = []
    
    # Take top N
    top_picks = picks[:top_n]
    
    # Split into chunks of 10 per message
    for chunk_idx in range(0, len(top_picks), 10):
        chunk = top_picks[chunk_idx:chunk_idx + 10]
        
        lines = [
            f"🏆 **TOP PICKS #{chunk_idx + 1}-{min(chunk_idx + 10, len(top_picks))}**",
            "━" * 45,
        ]
        
        for i, pick in enumerate(chunk, chunk_idx + 1):
            dir_sym = "⬆️" if pick.get("direction") == "higher" else "⬇️"
            prob = pick.get("display_prob", 0.5) * 100
            tier_emoji = {"SLAM": "🔥", "STRONG": "💪", "LEAN": "📊"}.get(pick.get("tier"), "❓")
            player = pick.get("player", "Unknown")
            team = pick.get("team", "")
            line = pick.get("line", 0)
            stat = pick.get("stat", "")
            
            lines.append(f"\n{i}. {tier_emoji} **{player}** ({team}) {dir_sym} {line} {stat}")
            lines.append(f"   {prob:.0f}% | {pick.get('tier', 'N/A')}")
            
            # Add context if requested
            if with_context:
                context = pick.get("context", {}).get("formatted", "")
                if context:
                    ctx_short = context[:70]
                    lines.append(f"   📋 {ctx_short}")
        
        messages.append("\n".join(lines))
    
    return messages


async def send_ranked_picks_tier(chat_id: str, picks: list[dict], top_n: int = 100, with_context: bool = False):
    """Send picks grouped by tier."""
    if not picks:
        print("❌ No picks to send")
        return
    
    messages = format_tier_based(picks, top_n, with_context)
    
    print(f"📤 Sending {len(messages)} tier-based pick messages...")
    
    # Send header
    header = f"""
🏀 **RANKED PICKS - {datetime.now().strftime('%B %d, %Y %I:%M %p')}**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total picks: {len(picks)}
🔥 SLAM: {len([p for p in picks if p.get('tier') == 'SLAM'])}
💪 STRONG: {len([p for p in picks if p.get('tier') == 'STRONG'])}
📊 LEAN: {len([p for p in picks if p.get('tier') == 'LEAN'])}
    """.strip()
    
    await send_message(chat_id, header)
    await asyncio.sleep(0.5)
    
    # Send each tier
    for msg in messages[:15]:  # Limit to 15 messages
        await send_message(chat_id, msg)
        await asyncio.sleep(0.3)
    
    print(f"✅ Sent {len(messages[:15])} messages to Telegram")


async def send_ranked_picks_top(chat_id: str, picks: list[dict], top_n: int = 20, with_context: bool = False):
    """Send top N picks."""
    if not picks:
        print("❌ No picks to send")
        return
    
    messages = format_top_n(picks, top_n, with_context)
    
    print(f"📤 Sending top {top_n} picks...")
    
    # Send header
    slam_count = len([p for p in picks[:top_n] if p.get("tier") == "SLAM"])
    header = f"""
🏆 **TOP {top_n} PICKS - {datetime.now().strftime('%B %d, %Y %I:%M %p')}**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 SLAM Picks: {slam_count}
📊 Avg Confidence: {sum(p.get('display_prob', 0.5) for p in picks[:top_n]) / top_n * 100:.0f}%
    """.strip()
    
    await send_message(chat_id, header)
    await asyncio.sleep(0.5)
    
    # Send messages
    for msg in messages:
        await send_message(chat_id, msg)
        await asyncio.sleep(0.3)
    
    print(f"✅ Sent {len(messages)} pick messages to Telegram")


async def main():
    parser = argparse.ArgumentParser(description="Send ranked picks to Telegram")
    parser.add_argument("--chat-id", default=DEFAULT_CHAT_ID, help="Telegram chat ID")
    parser.add_argument("--format", choices=["tier", "top"], default="tier",
                        help="Format: tier-based or top-n")
    parser.add_argument("--top", type=int, default=20,
                        help="Number of top picks to show (for top format)")
    parser.add_argument("--with-context", action="store_true",
                        help="Include context (minutes, rest, usage)")
    
    args = parser.parse_args()
    
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        return
    
    if not args.chat_id:
        print("❌ No chat ID provided. Set TELEGRAM_CHAT_ID or use --chat-id")
        return
    
    print("🔄 Loading ranked picks...")
    picks = load_ranked_picks()
    
    if not picks:
        print("❌ No picks to send")
        return
    
    print(f"✅ Loaded {len(picks)} ranked picks")
    
    if args.format == "tier":
        await send_ranked_picks_tier(args.chat_id, picks, args.top, args.with_context)
    else:
        await send_ranked_picks_top(args.chat_id, picks, args.top, args.with_context)


if __name__ == "__main__":
    asyncio.run(main())
