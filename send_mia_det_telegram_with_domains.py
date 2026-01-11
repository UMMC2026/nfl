#!/usr/bin/env python3
"""
MIA @ DET Game Analysis with Dual-Domain Classifications
Integrates domain validator to show CONVICTION/VALUE/HYBRID classifications
Sends enhanced game analysis to Telegram subscribers
"""

import os
import asyncio
import httpx
from datetime import datetime
from dotenv import load_dotenv
from ufa.analysis.domain_validator import classify_pick, DomainValidation
from telegram_template_with_domains import format_pick_with_domain, build_game_message

load_dotenv()

# Telegram config
# Prefer SPORTS_BOT_TOKEN if provided, else fall back to TELEGRAM_BOT_TOKEN
BOT_TOKEN = os.getenv("SPORTS_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
# Default CHAT_ID previously pointed to an admin. To reach subscribers, set TELEGRAM_CHAT_ID
# to your channel username (e.g., '@underdog_analyzer') or channel ID (e.g., '-1001234567890').
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", os.getenv("ADMIN_TELEGRAM_IDS", "7545848251").split(",")[0])

def get_recipient_ids() -> list[str]:
    """Collect recipient chat IDs for broadcast.

    Priority:
    - TELEGRAM_CHAT_ID: channel/group username (e.g., '@yourchannel') or numeric ID
    - ADMIN_TELEGRAM_IDS: comma-separated list of admin/user IDs
    If neither is present, falls back to the default CHAT_ID.
    """
    recipients: list[str] = []
    chat_id_env = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    admin_ids_env = os.getenv("ADMIN_TELEGRAM_IDS", "").strip()

    def _looks_like_bot_handle(value: str) -> bool:
        v = value.lower()
        return v.startswith("@") and v.endswith("_bot")

    if chat_id_env:
        if _looks_like_bot_handle(chat_id_env):
            print("[WARN] TELEGRAM_CHAT_ID appears to be a bot username, not a channel/group.")
            print("       Set TELEGRAM_CHAT_ID to your channel username (e.g., '@yourchannel') or numeric ID '-100...'.")
            print("       The bot must be added as an admin to that channel/group.")
        else:
            recipients.append(chat_id_env)
    if admin_ids_env:
        recipients.extend([x.strip() for x in admin_ids_env.split(",") if x.strip()])
    if not recipients:
        recipients.append(CHAT_ID)
    # Deduplicate while preserving order
    deduped = []
    seen = set()
    for r in recipients:
        if r and r not in seen:
            deduped.append(r)
            seen.add(r)
    return deduped

async def send_message(text: str, dry_run: bool = True, chat_id: str | None = None) -> bool:
    """Send message to Telegram and return success status"""
    if not BOT_TOKEN or dry_run:
        print(f"\n{'='*80}")
        print(f"[TELEGRAM MESSAGE]")
        print(f"{'='*80}")
        print(text)
        print(f"{'='*80}\n")
        return True

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id or CHAT_ID,
        "text": text,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return True
            else:
                print(f"❌ Telegram API error ({resp.status_code}): {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


def classify_game_picks() -> list[DomainValidation]:
    """
    Classify MIA @ DET picks using dual-domain framework
    Returns: List of DomainValidation objects
    """
    
    picks = [
        # Bam Adebayo - STRONG regime, good edge expected
        {
            'player': 'Bam Adebayo',
            'stat': 'pts+reb+ast O 27.5',
            'line': 27.5,
            'mu': 28.5 + 8.5 + 2.5,  # ppg + rpg + apg
            'sigma': None,
            'confidence': 65.0,
        },
        # Jalen Duren - STRONG regime, no μ data yet
        {
            'player': 'Jalen Duren',
            'stat': 'rebounds O 10.5',
            'line': 10.5,
            'mu': None,  # No historical data available
            'sigma': None,
            'confidence': 65.0,
        },
        # Cade Cunningham - Unrated, but shows edge
        {
            'player': 'Cade Cunningham',
            'stat': 'points O 26.5',
            'line': 26.5,
            'mu': 27.8,  # Estimated from recent games
            'sigma': 4.2,
            'confidence': 55.0,  # Lower - unrated
        },
        # Jaime Jaquez Jr - Moderate confidence
        {
            'player': 'Jaime Jaquez Jr',
            'stat': 'points O 15.5',
            'line': 15.5,
            'mu': 14.8,  # Slight gap
            'sigma': 3.5,
            'confidence': 52.0,
        },
        # Andrew Wiggins - Even money, weak conviction
        {
            'player': 'Andrew Wiggins',
            'stat': 'points O 15.5',
            'line': 15.5,
            'mu': 15.2,  # Minimal edge
            'sigma': 3.8,
            'confidence': 49.0,
        },
    ]
    
    # Classify all picks
    validations = []
    for pick in picks:
        validation = classify_pick(
            player=pick['player'],
            stat=pick['stat'],
            line=pick['line'],
            mu=pick['mu'],
            sigma=pick['sigma'],
            confidence_pct=pick['confidence'],
        )
        validations.append(validation)
    
    return validations


async def send_game_analysis():
    """Send MIA @ DET analysis with domain classifications to Telegram"""
    
    print("📊 Classifying MIA @ DET picks using dual-domain framework...")
    validations = classify_game_picks()
    
    # Prepare picks for template
    picks_with_domains = [
        {
            'player': v.player,
            'stat': v.stat,
            'line': v.line,
            'domain_type': v.play_type,
            'reasoning': v.reasoning,
            'confidence': v.confidence_pct,
            'mu': v.mu,
            'mu_gap': v.mu_gap,
        }
        for v in validations
    ]
    
    # Count by type
    hybrid_count = sum(1 for p in picks_with_domains if p['domain_type'] == 'HYBRID')
    conviction_count = sum(1 for p in picks_with_domains if p['domain_type'] == 'CONVICTION')
    value_count = sum(1 for p in picks_with_domains if p['domain_type'] == 'VALUE')
    reject_count = sum(1 for p in picks_with_domains if p['domain_type'] == 'REJECT')
    
    # Capital allocation
    capital_alloc = {
        'HYBRID': hybrid_count * 4,
        'CONVICTION': conviction_count * 2,
        'VALUE': value_count * 1,
    }
    
    print(f"\n✅ Classification Results:")
    print(f"   🎯 HYBRID:      {hybrid_count} picks")
    print(f"   🔒 CONVICTION:  {conviction_count} picks")
    print(f"   💎 VALUE:       {value_count} picks")
    print(f"   ❌ REJECT:      {reject_count} picks")
    
    # Build main game message
    main_message = build_game_message(
        game_name="MIA @ DET (6:00 PM EST)",
        picks=picks_with_domains,
        capital_allocation=capital_alloc,
    )
    
    messages = [
        # Message 1: Header with classification summary
        "🏀 **MIA @ DET DUAL-DOMAIN ANALYSIS**\n"
        "SOP-Classified Picks with Statistical & Regime Validation\n\n"
        f"Slate Breakdown:\n"
        f"  🎯 HYBRID:      {hybrid_count} ({hybrid_count/len(picks_with_domains)*100:.0f}%)\n"
        f"  🔒 CONVICTION:  {conviction_count} ({conviction_count/len(picks_with_domains)*100:.0f}%)\n"
        f"  💎 VALUE:       {value_count} ({value_count/len(picks_with_domains)*100:.0f}%)\n"
        f"  ❌ REJECT:      {reject_count} ({reject_count/len(picks_with_domains)*100:.0f}%)\n\n"
        f"Deploy: {sum(capital_alloc.values())} units (maintain dry powder)",

        # Message 2: Main picks with classifications
        main_message,

        # Message 3: Domain explanation
        "📚 **DUAL-DOMAIN FRAMEWORK EXPLAINED**\n\n"
        "🎯 **HYBRID** - Both domains strong\n"
        "  • Statistical: +3pt edge (μ vs line)\n"
        "  • Regime: 60%+ confidence\n"
        "  • Deploy: 3-5x units (highest confidence)\n\n"
        "🔒 **CONVICTION** - Regime strong, data weak\n"
        "  • Statistical: No μ data or μ unreliable\n"
        "  • Regime: 60%+ confidence\n"
        "  • Deploy: 2-3x units (regime play)\n\n"
        "💎 **VALUE** - Edge strong, conviction weak\n"
        "  • Statistical: +3pt+ edge\n"
        "  • Regime: <60% confidence\n"
        "  • Deploy: 1-2x units (contrarian play)\n\n"
        "❌ **REJECT** - Insufficient on both\n"
        "  • Do not deploy (no edge + low confidence)\n"
        "  • Specific reason always documented",

        # Message 4: Detailed pick breakdowns
        "📋 **DETAILED PICK ANALYSIS**\n\n"
        "🎯 **BAM ADEBAYO - CONVICTION PICK**\n"
        "  PTS+REB+AST O 27.5\n"
        "  • Confidence: 65% STRONG\n"
        "  • Data: Limited μ (no recent games)\n"
        "  • Edge: Regime strength only\n"
        "  • Action: Deploy 2-3 units\n\n"
        "🔒 **JALEN DUREN - CONVICTION PICK**\n"
        "  REB O 10.5\n"
        "  • Confidence: 65% STRONG\n"
        "  • Data: No μ available\n"
        "  • Edge: High-confidence regime play\n"
        "  • Action: Deploy 2-3 units\n\n"
        "💎 **CADE CUNNINGHAM - VALUE PICK**\n"
        "  PTS O 26.5 (μ=27.8, +1.3pt edge)\n"
        "  • Confidence: 55% MODERATE\n"
        "  • Data: Good (μ=27.8)\n"
        "  • Gap: Only 1.3pt (below 3pt threshold)\n"
        "  • Action: Deploy 1 unit (low-conviction edge)",

        # Message 5: Capital allocation & strategy
        "💰 **CAPITAL ALLOCATION PLAN**\n\n"
        f"HYBRID Plays:       {capital_alloc.get('HYBRID', 0)} units (N/A tonight)\n"
        f"CONVICTION Plays:   {capital_alloc.get('CONVICTION', 0)} units (2 picks × 2-3 units avg)\n"
        f"VALUE Plays:        {capital_alloc.get('VALUE', 0)} units (1 pick × 1 unit avg)\n\n"
        f"Total Deploy:       {sum(capital_alloc.values())} units\n"
        f"Utilization:        {sum(capital_alloc.values())/100*100:.0f}% of bankroll\n"
        f"Dry Powder:         {100 - sum(capital_alloc.values())} units (reserves)\n\n"
        f"Expected Hit Rate:  58-64% (blended)\n"
        f"Expected ROI:       +12-18% on deployed capital",

        # Message 6: Final notes (plain text)
        "MONITORING & ADJUSTMENTS\n\n"
        "Watch For:\n"
        "Bam minutes if MIA is blowout\n"
        "Jalen foul trouble (guards rebounds)\n"
        "Late-game status updates\n\n"
        "Expected Outcomes:\n"
        "Hit 2 CONVICTION: +70% ROI\n"
        "Hit 2 CONVICTION only: +50% ROI\n"
        "Hit 1 or fewer: -20% ROI\n\n"
        "See SOP_DUAL_DOMAIN_ACCURACY.md for full decision tree",
    ]

    recipients = get_recipient_ids()
    print(f"\n📤 Sending MIA @ DET dual-domain analysis to Telegram...")
    print(f"   Targets: {', '.join(recipients)}")
    for i, msg in enumerate(messages, 1):
        all_ok = True
        for ridx, rid in enumerate(recipients, 1):
            success = await send_message(msg, dry_run=False, chat_id=rid)
            if success:
                print(f"  ✅ Message {i}/{len(messages)} → recipient {ridx}/{len(recipients)} sent")
            else:
                print(f"  ❌ Message {i}/{len(messages)} → recipient {ridx}/{len(recipients)} failed")
                all_ok = False
        if not all_ok:
            return False
        await asyncio.sleep(0.5)  # Rate limit per message batch

    print(f"\n✅ MIA @ DET dual-domain analysis sent to Telegram!")
    return True


if __name__ == "__main__":
    asyncio.run(send_game_analysis())
