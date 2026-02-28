"""
NHL PROFESSIONAL REPORT GENERATOR
==================================
Production-grade report with:
    - Top 5 Picks highlighted
    - Data-driven calibration integration
    - Telegram push capability
    - Comprehensive stats and governance

Author: Risk-First Quant Engine
Version: 2.0.0
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from dataclasses import asdict

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from sports.nhl.nhl_menu import NHLProp, NHLSlate
from sports.nhl.player_stats import get_player_stats, get_goalie_stats, SKATER_STATS_2026

# Output directories
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "nhl"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# TIER DISPLAY CONFIG
# ═══════════════════════════════════════════════════════════════

TIER_CONFIG = {
    "STRONG": {
        "icon": "[STRONG]",
        "emoji": "🟢",
        "color": "green",
        "priority": 1,
    },
    "LEAN": {
        "icon": "[LEAN]",
        "emoji": "🟡", 
        "color": "yellow",
        "priority": 2,
    },
    "NO_PLAY": {
        "icon": "[SKIP]",
        "emoji": "⚫",
        "color": "gray",
        "priority": 3,
    },
}


# ═══════════════════════════════════════════════════════════════
# DATA-DRIVEN CALIBRATION ADJUSTMENTS (NHL-SPECIFIC)
# ═══════════════════════════════════════════════════════════════

# NHL stat multipliers based on expected calibration performance
# Similar to NBA data_driven_penalties.py but hockey-specific
NHL_STAT_MULTIPLIERS = {
    # SOG props are generally reliable
    "SOG": 1.05,  # Slight boost - good hit rate
    "sog": 1.05,
    
    # Goals are volatile - penalize slightly
    "Goals": 0.90,
    "goals": 0.90,
    
    # Blocked shots for D-men are stable
    "Blocked Shots": 1.02,
    "blocks": 1.02,
    
    # Saves are goalie-dependent (risky)
    "Saves": 0.85,
    "saves": 0.85,
}

# Direction adjustments (based on line positioning)
NHL_DIRECTION_ADJUSTMENTS = {
    # Over/More props on low lines tend to hit
    ("SOG", "More", 1.5): 1.08,  # Over 1.5 SOG
    ("SOG", "More", 2.5): 1.02,  # Over 2.5 more balanced
    ("SOG", "Less", 2.5): 1.05,  # Under 2.5 for lower shooters
    
    # Goals are binary - treat carefully
    ("Goals", "More", 0.5): 0.95,  # Over 0.5 goals risky
    
    # Blocked shots for D-men under plays well
    ("Blocked Shots", "Less", 2.5): 1.06,
}


def apply_data_driven_adjustments(props: List[NHLProp]) -> List[NHLProp]:
    """Apply data-driven calibration adjustments to props."""
    adjusted = []
    
    for prop in props:
        if prop.model_prob is None:
            adjusted.append(prop)
            continue
        
        # Get base multiplier for stat
        multiplier = NHL_STAT_MULTIPLIERS.get(prop.stat, 1.0)
        
        # Check for direction-specific adjustment
        direction_key = (prop.stat, prop.direction, prop.line)
        if direction_key in NHL_DIRECTION_ADJUSTMENTS:
            multiplier *= NHL_DIRECTION_ADJUSTMENTS[direction_key]
        
        # Apply adjustment (cap at reasonable bounds)
        adjusted_prob = prop.model_prob * multiplier
        adjusted_prob = min(0.85, max(0.45, adjusted_prob))  # Cap bounds
        
        prop.model_prob = adjusted_prob
        prop.edge = adjusted_prob - prop.implied_prob
        
        # Recalculate tier if needed
        if adjusted_prob >= 0.62:
            prop.tier = "STRONG"
        elif adjusted_prob >= 0.58:
            prop.tier = "LEAN"
        else:
            prop.tier = "NO_PLAY"
            prop.pick_state = "REJECTED"
        
        adjusted.append(prop)
    
    return adjusted


# ═══════════════════════════════════════════════════════════════
# TOP 5 PICKS CALCULATOR
# ═══════════════════════════════════════════════════════════════

def get_top_5_picks(slate: NHLSlate) -> List[NHLProp]:
    """Get the top 5 picks from the slate based on confidence and edge."""
    playable = [p for p in slate.props if p.pick_state == "OPTIMIZABLE"]
    
    # Sort by model probability (descending)
    playable.sort(key=lambda x: (
        TIER_CONFIG.get(x.tier, {}).get("priority", 99),  # STRONG first
        -(x.model_prob or 0),  # Then by probability
    ))
    
    return playable[:5]


def format_top_5_ascii(top_5: List[NHLProp]) -> str:
    """Format top 5 picks as ASCII art for reports."""
    if not top_5:
        return "  No picks meet minimum thresholds.\n"
    
    lines = []
    lines.append("")
    lines.append("+" + "=" * 58 + "+")
    lines.append("|" + " " * 15 + "TOP 5 NHL PICKS" + " " * 28 + "|")
    lines.append("+" + "=" * 58 + "+")
    
    for i, pick in enumerate(top_5, 1):
        tier_icon = TIER_CONFIG.get(pick.tier, {}).get("icon", "[?]")
        prob_pct = (pick.model_prob or 0) * 100
        
        # Get season average for display
        stats = get_player_stats(pick.player)
        if stats and pick.stat == "SOG":
            avg_str = f"(Season: {stats.sog_avg:.1f})"
        elif stats and pick.stat == "Goals":
            avg_str = f"(Season: {stats.goals_avg:.2f})"
        else:
            avg_str = ""
        
        # Format line
        pick_line = f"  #{i} {tier_icon} {pick.player} ({pick.team})"
        lines.append("|" + pick_line.ljust(58) + "|")
        
        detail = f"     {pick.stat} {pick.direction.upper()} {pick.line} {avg_str}"
        lines.append("|" + detail.ljust(58) + "|")
        
        confidence = f"     Confidence: {prob_pct:.1f}% | Edge: {(pick.edge or 0)*100:.1f}%"
        lines.append("|" + confidence.ljust(58) + "|")
        
        if pick.risk_flags:
            flags = f"     Flags: {', '.join(pick.risk_flags)}"
            lines.append("|" + flags.ljust(58) + "|")
        
        if i < len(top_5):
            lines.append("|" + "-" * 58 + "|")
    
    lines.append("+" + "=" * 58 + "+")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# TELEGRAM PUSH
# ═══════════════════════════════════════════════════════════════

def _get_telegram_config() -> Tuple[str, List[str]]:
    """Get Telegram bot token and chat IDs."""
    import re
    token = os.getenv("SPORTS_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
    
    raw_ids = (
        os.getenv("TELEGRAM_CHAT_IDS") or
        os.getenv("TELEGRAM_BROADCAST_CHAT_IDS") or
        os.getenv("TELEGRAM_CHAT_ID") or ""
    ).strip()
    
    chat_ids = [c for c in re.split(r"[\s,]+", raw_ids) if c]
    
    return token, chat_ids


def can_send_telegram() -> bool:
    """Check if Telegram credentials are configured."""
    token, chat_ids = _get_telegram_config()
    return bool(token and chat_ids)


def format_telegram_message(top_5: List[NHLProp], slate: NHLSlate) -> str:
    """Format picks for Telegram message."""
    lines = []
    lines.append("🏒 *NHL PICKS* 🏒")
    lines.append(f"📅 {slate.date}")
    lines.append("")
    lines.append("*TOP 5 PICKS:*")
    lines.append("")
    
    for i, pick in enumerate(top_5, 1):
        tier_emoji = TIER_CONFIG.get(pick.tier, {}).get("emoji", "⚪")
        prob_pct = (pick.model_prob or 0) * 100
        direction = "OVER" if pick.direction.lower() in ("more", "higher", "over") else "UNDER"
        
        # Get season avg
        stats = get_player_stats(pick.player)
        avg_str = ""
        if stats and pick.stat == "SOG":
            avg_str = f" (Avg: {stats.sog_avg:.1f})"
        
        lines.append(f"{tier_emoji} *#{i}* {pick.player}")
        lines.append(f"   {pick.stat} {direction} {pick.line}{avg_str}")
        lines.append(f"   Edge: {prob_pct:.1f}% | {pick.tier}")
        lines.append("")
    
    # Summary
    lines.append("─" * 25)
    lines.append(f"📊 Total: {slate.total_props} props | {slate.playable_props} playable")
    lines.append(f"🟢 STRONG: {slate.strong_picks} | 🟡 LEAN: {slate.lean_picks}")
    lines.append("")
    lines.append("⚠️ _Goalie confirmation required for saves_")
    
    return "\n".join(lines)


def push_nhl_telegram(top_5: List[NHLProp], slate: NHLSlate) -> bool:
    """Push NHL picks to Telegram."""
    try:
        import requests
    except ImportError:
        print("  [!] requests library not installed")
        return False
    
    token, chat_ids = _get_telegram_config()
    if not token or not chat_ids:
        print("  [!] Telegram not configured (missing token or chat_ids)")
        return False
    
    message = format_telegram_message(top_5, slate)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    sent_any = False
    for chat_id in chat_ids:
        try:
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json() if resp.content else {}
            if data.get("ok"):
                sent_any = True
                print(f"  [OK] Sent to chat {chat_id}")
            else:
                print(f"  [!] Failed for chat {chat_id}: {data.get('description', 'unknown')}")
        except Exception as e:
            print(f"  [!] Error sending to {chat_id}: {e}")
    
    return sent_any


# ═══════════════════════════════════════════════════════════════
# PROFESSIONAL REPORT GENERATOR
# ═══════════════════════════════════════════════════════════════

def generate_professional_report(slate: NHLSlate, apply_sdg: bool = True) -> str:
    """Generate full professional report."""
    
    # Apply data-driven adjustments if requested
    if apply_sdg:
        slate.props = apply_data_driven_adjustments(slate.props)
        # Recalculate totals
        slate.playable_props = sum(1 for p in slate.props if p.pick_state == "OPTIMIZABLE")
        slate.strong_picks = sum(1 for p in slate.props if p.tier == "STRONG")
        slate.lean_picks = sum(1 for p in slate.props if p.tier == "LEAN")
    
    top_5 = get_top_5_picks(slate)
    
    lines = []
    
    # Header
    lines.append("=" * 60)
    lines.append("  NHL PROFESSIONAL REPORT")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"  Slate Date: {slate.date}")
    lines.append("=" * 60)
    
    # Summary Box
    lines.append("")
    lines.append("+" + "-" * 58 + "+")
    lines.append("|  SLATE SUMMARY" + " " * 43 + "|")
    lines.append("+" + "-" * 58 + "+")
    lines.append(f"|  Total Props Analyzed: {slate.total_props}".ljust(59) + "|")
    lines.append(f"|  Playable Picks:       {slate.playable_props}".ljust(59) + "|")
    lines.append(f"|  [STRONG]:             {slate.strong_picks}".ljust(59) + "|")
    lines.append(f"|  [LEAN]:               {slate.lean_picks}".ljust(59) + "|")
    lines.append(f"|  Players Covered:      {len(SKATER_STATS_2026)} skaters".ljust(59) + "|")
    lines.append("+" + "-" * 58 + "+")
    
    # TOP 5 Section
    lines.append(format_top_5_ascii(top_5))
    
    # Model Info
    lines.append("")
    lines.append("+" + "-" * 58 + "+")
    lines.append("|  MODEL & GOVERNANCE" + " " * 38 + "|")
    lines.append("+" + "-" * 58 + "+")
    lines.append("|  Model: Poisson Distribution with Real Season Stats".ljust(59) + "|")
    sdg_status = "ENABLED" if apply_sdg else "DISABLED"
    lines.append(f"|  Data-Driven Calibration (SDG): {sdg_status}".ljust(59) + "|")
    lines.append("|  SLAM Tier: DISABLED (hockey volatility)".ljust(59) + "|")
    lines.append("|  Minimum Edge: 2%".ljust(59) + "|")
    lines.append("|  Goalie Gate: MANDATORY for saves props".ljust(59) + "|")
    lines.append("+" + "-" * 58 + "+")
    
    # All STRONG Picks
    strong_picks = [p for p in slate.props if p.tier == "STRONG"]
    if strong_picks:
        strong_picks.sort(key=lambda x: x.model_prob or 0, reverse=True)
        lines.append("")
        lines.append("=" * 60)
        lines.append(f"  [STRONG] PICKS ({len(strong_picks)})")
        lines.append("=" * 60)
        
        for p in strong_picks:
            stats = get_player_stats(p.player)
            avg_str = ""
            if stats and p.stat == "SOG":
                avg_str = f" | Season Avg: {stats.sog_avg:.1f}"
            elif stats and p.stat == "Goals":
                avg_str = f" | Season Avg: {stats.goals_avg:.2f}"
            
            tag = f" [{p.tag}]" if p.tag else ""
            lines.append(f"  {p.player}{tag} ({p.team}) vs {p.opponent}")
            lines.append(f"    {p.stat} {p.direction.upper()} {p.line}{avg_str}")
            lines.append(f"    Confidence: {(p.model_prob or 0)*100:.1f}% | Edge: {(p.edge or 0)*100:.1f}%")
            if p.risk_flags:
                lines.append(f"    Flags: {', '.join(p.risk_flags)}")
            lines.append("")
    
    # All LEAN Picks
    lean_picks = [p for p in slate.props if p.tier == "LEAN"]
    if lean_picks:
        lean_picks.sort(key=lambda x: x.model_prob or 0, reverse=True)
        lines.append("")
        lines.append("=" * 60)
        lines.append(f"  [LEAN] PICKS ({len(lean_picks)})")
        lines.append("=" * 60)
        
        for p in lean_picks[:15]:  # Show top 15 LEAN
            stats = get_player_stats(p.player)
            avg_str = ""
            if stats and p.stat == "SOG":
                avg_str = f" | Avg: {stats.sog_avg:.1f}"
            
            tag = f" [{p.tag}]" if p.tag else ""
            lines.append(f"  {p.player}{tag} ({p.team}): {p.stat} {p.direction.upper()} {p.line}{avg_str}")
            lines.append(f"    {(p.model_prob or 0)*100:.1f}% confidence")
        
        if len(lean_picks) > 15:
            lines.append(f"  ... and {len(lean_picks) - 15} more LEAN picks")
    
    # Risk Warnings
    lines.append("")
    lines.append("=" * 60)
    lines.append("  RISK WARNINGS")
    lines.append("=" * 60)
    lines.append("  * NO SLAM TIER - Hockey has inherent volatility")
    lines.append("  * Goalie confirmation REQUIRED before playing saves")
    lines.append("  * Back-to-back games reduce goalie reliability")
    lines.append("  * High CV props flagged for caution")
    
    # Footer
    lines.append("")
    lines.append("=" * 60)
    lines.append("  Risk-First Quant Engine | NHL v2.0")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def save_report(report: str, slate: NHLSlate) -> Path:
    """Save report to file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"NHL_REPORT_{timestamp}.txt"
    filepath = OUTPUT_DIR / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)
    
    return filepath


def save_picks_json(slate: NHLSlate) -> Path:
    """Save picks to JSON for calibration tracking."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"NHL_PICKS_{timestamp}.json"
    filepath = OUTPUT_DIR / filename
    
    playable = [p for p in slate.props if p.pick_state == "OPTIMIZABLE"]
    
    output = {
        "sport": "NHL",
        "date": slate.date,
        "generated": datetime.now().isoformat(),
        "summary": {
            "total_props": slate.total_props,
            "playable": slate.playable_props,
            "strong": slate.strong_picks,
            "lean": slate.lean_picks,
        },
        "picks": [
            {
                "player": p.player,
                "team": p.team,
                "opponent": p.opponent,
                "stat": p.stat,
                "line": p.line,
                "direction": p.direction,
                "probability": p.model_prob,
                "edge": p.edge,
                "tier": p.tier,
                "risk_flags": p.risk_flags,
            }
            for p in playable
        ]
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    return filepath


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def run_full_report(slate: NHLSlate, send_telegram: bool = False) -> Dict:
    """Run full reporting pipeline."""
    results = {
        "success": False,
        "report_path": None,
        "json_path": None,
        "telegram_sent": False,
        "top_5": [],
    }
    
    try:
        # Generate report
        report = generate_professional_report(slate, apply_sdg=True)
        
        # Get top 5
        top_5 = get_top_5_picks(slate)
        results["top_5"] = [p.player for p in top_5]
        
        # Save files
        report_path = save_report(report, slate)
        json_path = save_picks_json(slate)
        
        results["report_path"] = str(report_path)
        results["json_path"] = str(json_path)
        
        # Print report
        print(report)
        
        print(f"\n  [FILE] Report saved: {report_path}")
        print(f"  [FILE] JSON saved: {json_path}")
        
        # Telegram
        if send_telegram:
            if can_send_telegram():
                print("\n  Sending to Telegram...")
                results["telegram_sent"] = push_nhl_telegram(top_5, slate)
            else:
                print("\n  [!] Telegram not configured - skipping push")
        
        results["success"] = True
        
    except Exception as e:
        print(f"\n  [ERROR] Report generation failed: {e}")
        import traceback
        traceback.print_exc()
    
    return results


# ═══════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NHL Professional Report Generator")
    parser.add_argument("--telegram", "-t", action="store_true", help="Send to Telegram")
    parser.add_argument("--no-sdg", action="store_true", help="Disable data-driven adjustments")
    args = parser.parse_args()
    
    # Test with the embedded slate from process_slate.py
    from sports.nhl.process_slate import SLATE_TEXT
    from sports.nhl.nhl_menu import parse_underdog_paste, deduplicate_props, analyze_slate
    
    print("\n" + "=" * 60)
    print("  NHL PROFESSIONAL REPORT GENERATOR")
    print("=" * 60)
    
    # Parse and analyze
    props = parse_underdog_paste(SLATE_TEXT)
    props = deduplicate_props(props)
    
    slate = NHLSlate(
        date=date.today().strftime("%Y-%m-%d"),
        props=props,
        games={},
    )
    
    slate = analyze_slate(slate)
    
    # Apply SDG adjustments unless disabled
    if not args.no_sdg:
        slate.props = apply_data_driven_adjustments(slate.props)
        slate.playable_props = sum(1 for p in slate.props if p.pick_state == "OPTIMIZABLE")
        slate.strong_picks = sum(1 for p in slate.props if p.tier == "STRONG")
        slate.lean_picks = sum(1 for p in slate.props if p.tier == "LEAN")
    
    # Run full report
    run_full_report(slate, send_telegram=args.telegram)
