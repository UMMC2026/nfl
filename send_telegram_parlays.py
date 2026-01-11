"""
Send parlays to Telegram with multiple format options.

Supports:
- SEPARATE: Each parlay in its own message
- COMBINED: All parlays in one message
- HYDRATED: Include hydration data (avg, std dev, sample size)

Usage:
    python send_telegram_parlays.py --format separate --with-hydration
    python send_telegram_parlays.py --format combined
    python send_telegram_parlays.py --chat-id <ID>
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


def load_parlays_from_pipeline() -> list[dict]:
    """Load generated parlays from the daily pipeline."""
    # Generate parlays on the fly using the optimizer
    from ufa.daily_pipeline import DailyPipeline
    import json
    from itertools import combinations
    
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
    
    # Filter to SLAM/STRONG for better parlays
    good_picks = [p for p in calibrated if p.get("tier") in ["SLAM", "STRONG"]]
    
    parlays = []
    
    # Generate parlays for 3, 4, 5 legs
    for legs in [3, 4, 5]:
        payout = 6 if legs == 3 else (10 if legs == 4 else 20)
        breakeven = 1.0 / payout
        
        # Generate combinations
        for combo in combinations(good_picks, legs):
            # Check team diversity
            teams = set(p.get("team") for p in combo)
            if len(teams) < 2:
                continue
            
            # Check no duplicate players
            players = [p.get("player") for p in combo]
            if len(players) != len(set(players)):
                continue
            
            # Calculate combined probability
            combined_prob = 1.0
            for p in combo:
                prob = p.get("display_prob", 0.5)
                combined_prob *= prob
            
            # Edge
            edge = ((combined_prob - breakeven) / breakeven * 100) if breakeven > 0 else 0
            
            parlays.append({
                "format": "power",
                "legs": legs,
                "rank": len([x for x in parlays if x["legs"] == legs]) + 1,
                "picks": list(combo),
                "ev": edge,
                "base_prob": combined_prob,
                "adjusted_prob": combined_prob,
            })
    
    # Sort by EV and limit
    parlays.sort(key=lambda x: x["ev"], reverse=True)
    return parlays[:20]


def format_parlay_separate(parlay: dict, with_hydration: bool = False) -> str:
    """Format a single parlay for separate message."""
    fmt = parlay["format"].upper()
    legs = parlay["legs"]
    rank = parlay["rank"]
    
    lines = [
        f"🎲 **{fmt} {legs}-LEG PARLAY #{rank}**",
        "━" * 40,
    ]
    
    for i, pick in enumerate(parlay.get("picks", [])[:legs], 1):
        dir_sym = "⬆️" if pick.get("direction") == "higher" else "⬇️"
        prob = pick.get("display_prob", pick.get("probability", 0.5)) * 100
        player = pick.get("player", "Unknown")
        line = pick.get("line", 0)
        stat = pick.get("stat", "")
        
        lines.append(f"{i}. {player} {dir_sym} {line} {stat}")
        lines.append(f"   {prob:.0f}% confidence")
        
        # Add hydration if requested
        if with_hydration:
            avg = pick.get("avg")
            std = pick.get("std")
            n = pick.get("n")
            if avg is not None:
                lines.append(f"   📊 Avg: {avg:.1f} | SD: {std:.1f} | N: {n}")
    
    # Add probability and EV
    combined_prob = parlay.get("base_prob", 0)
    adjusted_prob = parlay.get("adjusted_prob", 0)
    ev = parlay.get("ev", 0)
    
    lines.append("")
    lines.append(f"📊 Base Prob: {combined_prob*100:.1f}%")
    lines.append(f"📊 Adjusted (corr): {adjusted_prob*100:.1f}%")
    
    # Calculate payout and edge
    if legs == 3:
        payout = 6
    elif legs == 4:
        payout = 10
    elif legs == 5:
        payout = 20
    else:
        payout = 2 ** legs
    
    breakeven = 1.0 / payout
    edge = ((adjusted_prob - breakeven) / breakeven * 100) if breakeven > 0 else 0
    
    lines.append(f"💰 Payout: {payout}x | Edge: **{'+' if edge > 0 else ''}{edge:.1f}%**")
    
    return "\n".join(lines)


def format_parlays_combined(parlays: list[dict], with_hydration: bool = False) -> list[str]:
    """Format all parlays for combined messages (one per legs count)."""
    messages = []
    
    # Group by legs
    by_legs = {}
    for p in parlays:
        legs = p["legs"]
        if legs not in by_legs:
            by_legs[legs] = []
        by_legs[legs].append(p)
    
    # Create message per legs count
    for legs in sorted(by_legs.keys()):
        lines = [
            f"🎲 **{legs}-LEG PARLAYS**",
            "━" * 40,
        ]
        
        for parlay in by_legs[legs][:3]:  # Top 3 per legs
            rank = parlay["rank"]
            fmt = parlay["format"].upper()
            
            lines.append(f"\n#{rank} {fmt}")
            
            for i, pick in enumerate(parlay.get("picks", [])[:legs], 1):
                dir_sym = "⬆️" if pick.get("direction") == "higher" else "⬇️"
                prob = pick.get("display_prob", pick.get("probability", 0.5)) * 100
                player = pick.get("player", "Unknown")
                line = pick.get("line", 0)
                stat = pick.get("stat", "")
                
                lines.append(f"  {i}. {player} {dir_sym} {line} {stat} ({prob:.0f}%)")
                
                if with_hydration:
                    avg = pick.get("avg")
                    if avg is not None:
                        lines.append(f"     📊 μ={avg:.1f} σ={pick.get('std', 0):.1f}")
            
            # Stats
            combined_prob = parlay.get("base_prob", 0)
            adjusted_prob = parlay.get("adjusted_prob", 0)
            
            if legs == 3:
                payout = 6
            elif legs == 4:
                payout = 10
            elif legs == 5:
                payout = 20
            else:
                payout = 2 ** legs
            
            breakeven = 1.0 / payout
            edge = ((adjusted_prob - breakeven) / breakeven * 100) if breakeven > 0 else 0
            
            lines.append(f"  📊 {adjusted_prob*100:.1f}% | 💰 {payout}x | Edge: {edge:+.0f}%")
        
        messages.append("\n".join(lines))
    
    return messages


async def send_parlays_separate(chat_id: str, parlays: list[dict], with_hydration: bool = False):
    """Send each parlay separately."""
    if not parlays:
        print("❌ No parlays to send")
        return
    
    print(f"📤 Sending {len(parlays)} parlays separately...")
    
    for parlay in parlays[:10]:  # Limit to 10 to avoid spam
        msg = format_parlay_separate(parlay, with_hydration)
        await send_message(chat_id, msg)
        await asyncio.sleep(0.5)
    
    print(f"✅ Sent {len(parlays[:10])} parlays to Telegram")


async def send_parlays_combined(chat_id: str, parlays: list[dict], with_hydration: bool = False):
    """Send all parlays in grouped messages."""
    if not parlays:
        print("❌ No parlays to send")
        return
    
    messages = format_parlays_combined(parlays, with_hydration)
    
    print(f"📤 Sending {len(messages)} grouped parlay messages...")
    
    # Send header
    header = f"""
🎲 **PARLAY BUILDER - {datetime.now().strftime('%B %d, %Y %I:%M %p')}**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total parlays generated: {len(parlays)}
    """.strip()
    
    await send_message(chat_id, header)
    await asyncio.sleep(0.5)
    
    # Send grouped messages
    for msg in messages:
        await send_message(chat_id, msg)
        await asyncio.sleep(0.5)
    
    print(f"✅ Sent {len(messages)} parlay summaries to Telegram")


async def main():
    parser = argparse.ArgumentParser(description="Send parlays to Telegram")
    parser.add_argument("--chat-id", default=DEFAULT_CHAT_ID, help="Telegram chat ID")
    parser.add_argument("--format", choices=["separate", "combined"], default="combined",
                        help="Parlay format: separate messages or combined")
    parser.add_argument("--with-hydration", action="store_true",
                        help="Include hydration data (avg, std dev)")
    
    args = parser.parse_args()
    
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        return
    
    if not args.chat_id:
        print("❌ No chat ID provided. Set TELEGRAM_CHAT_ID or use --chat-id")
        return
    
    print("🔄 Loading parlays...")
    parlays = load_parlays_from_pipeline()
    
    if not parlays:
        print("❌ No parlays generated")
        return
    
    print(f"✅ Loaded {len(parlays)} parlays")
    
    if args.format == "separate":
        await send_parlays_separate(args.chat_id, parlays, args.with_hydration)
    else:
        await send_parlays_combined(args.chat_id, parlays, args.with_hydration)


if __name__ == "__main__":
    asyncio.run(main())
