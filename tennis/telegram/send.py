"""
Tennis Telegram Sender
======================
Delivers validated plays to Telegram channel.
Environment variables only. No secrets in code.

Required env vars (tennis-specific override → generic fallback):
    TENNIS_BOT_TOKEN   (or TELEGRAM_BOT_TOKEN)
    TENNIS_CHAT_ID     (or TELEGRAM_CHAT_ID)
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import List, Dict

# Load .env file from project root
try:
    from dotenv import load_dotenv
    # Find project root (where .env lives)
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, rely on system env vars

# Optional: use requests if available, else urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.parse
    HAS_REQUESTS = False


BOT_TOKEN = os.getenv("TENNIS_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TENNIS_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")


def _norm_direction(direction: str) -> str:
    """Normalize direction across sources.

    Supports:
      - Engine: HIGHER/LOWER
      - Canonical signals: higher/lower
      - Odds-style: over/under
    """
    d = str(direction or "").strip().lower()
    if d in {"higher", "over", "more", "hi", "up"} or d.startswith("hi"):
        return "HIGHER"
    if d in {"lower", "under", "less", "lo", "down"} or d.startswith("lo"):
        return "LOWER"
    return str(direction or "").strip().upper() or "HIGHER"


def format_message(plays: List[Dict]) -> str:
    """Format plays into Telegram message - BASIC format."""
    
    if not plays:
        return "🎾 TENNIS — No plays today (validation passed, no edges met threshold)"
    
    lines = []
    lines.append("🎾 TENNIS PLAYS (VALIDATED)")
    lines.append(f"📅 {plays[0].get('generated_at', '')[:10] if plays else ''}")
    lines.append("")
    
    for i, p in enumerate(plays, 1):
        engine = p.get("engine", "?").replace("_ENGINE", "")
        tier = p.get("tier", "?")
        tier_emoji = "🔥" if tier == "SLAM" else "💪" if tier == "STRONG" else "📈" if tier == "LEAN" else "❓"
        
        # Players
        if "players" in p:
            match = " vs ".join(p["players"])
        elif "player" in p:
            match = f"{p['player']} vs {p.get('opponent', '?')}"
        else:
            match = "?"
        
        direction = p.get("direction", "?")
        line = p.get("line", "?")
        prob = p.get("probability")
        prob_str = f"{prob:.0%}" if prob else "?"
        
        lines.append(f"{tier_emoji} #{i} | {engine}")
        lines.append(f"   {match}")
        lines.append(f"   {direction} {line} | {prob_str} | {tier}")
        lines.append("")
    
    lines.append("—")
    lines.append("Gates: ✅ | Max: 5 | Corr: Clean")
    
    return "\n".join(lines)


def format_enhanced_message(plays: List[Dict], surface: str = "Hard") -> str:
    """
    Format plays with FULL math breakdown and AI commentary.
    NBA-style detailed output.
    """
    from datetime import datetime
    
    if not plays:
        return "🎾 TENNIS — No plays today (all props below 55% threshold)"
    
    lines = []
    
    # Header
    lines.append("━" * 45)
    lines.append("🎾 TENNIS PROPS — CALIBRATED ANALYSIS")
    lines.append(f"📅 {datetime.now().strftime('%B %d, %Y %I:%M %p')}")
    lines.append(f"🏟️ Surface: {surface}")
    lines.append("━" * 45)
    
    # Summary counts
    slam_count = len([p for p in plays if p.get('tier') == 'SLAM'])
    strong_count = len([p for p in plays if p.get('tier') == 'STRONG'])
    lean_count = len([p for p in plays if p.get('tier') == 'LEAN'])
    
    lines.append(f"🔥 SLAM: {slam_count} | 💪 STRONG: {strong_count} | 📈 LEAN: {lean_count}")
    lines.append("")
    
    # Group by tier
    tiers = {'SLAM': [], 'STRONG': [], 'LEAN': []}
    for p in plays:
        tier = p.get('tier', 'LEAN')
        if tier in tiers:
            tiers[tier].append(p)
    
    tier_emojis = {'SLAM': '🔥', 'STRONG': '💪', 'LEAN': '📈'}
    
    for tier_name in ['SLAM', 'STRONG', 'LEAN']:
        tier_plays = tiers[tier_name]
        if not tier_plays:
            continue
        
        lines.append(f"\n{tier_emojis[tier_name]} {tier_name} PLAYS ({len(tier_plays)})")
        lines.append("─" * 40)
        
        # Human-readable stat display names (CRITICAL: distinguish 1st set vs total)
        STAT_DISPLAY_NAMES = {
            'games_won': 'TOTAL Games Won',
            '1st_set_games_won': '1ST SET Games Won',
            '1st_set_games': '1ST SET Games Played',
            'games_played': 'Total Games Played',
            'sets_won': 'Sets Won',
            'sets_played': 'Sets Played',
            'aces': 'Aces',
            'double_faults': 'Double Faults',
            'tiebreakers': 'Tiebreakers',
            'breakpoints_won': 'Break Points Won',
            'fantasy_score': 'Fantasy Score',
        }
        
        for i, p in enumerate(tier_plays, 1):
            player = p.get('player', 'Unknown')
            stat_raw = p.get('stat', p.get('stat_type', p.get('market', 'Unknown')))
            # Convert to display name
            stat = STAT_DISPLAY_NAMES.get(stat_raw, stat_raw.replace('_', ' ').title())
            direction = p.get('direction', 'HIGHER')
            line = p.get('line', 0) or 0
            prob = p.get('probability', 0) or 0
            confidence = p.get('confidence', prob * 100 if prob else 0) or 0
            
            # Direction symbol
            dir_sym = "⬆️" if direction.upper() == 'HIGHER' else "⬇️"
            
            lines.append(f"\n{i}. {player}")
            lines.append(f"   {dir_sym} {direction} {line} {stat}")
            lines.append(f"   📊 Prob: {prob:.1%} | Conf: {confidence:.0f}%")
            
            # Math breakdown (simulation data)
            sim_data = p.get('simulation', {}) or {}
            profile_data = p.get('profile_data', {}) or {}
            
            if sim_data:
                mean = sim_data.get('mean', 0)
                std = sim_data.get('std', 0)
                lines.append(f"   📈 MC: μ={mean:.1f} σ={std:.1f}")
            
            # Historical data
            n_matches = profile_data.get('n_matches', p.get('n_matches', 0)) or 0
            hist_mean = profile_data.get('historical_mean', 0) or 0
            hist_std = profile_data.get('historical_std', 0) or 0
            
            if n_matches > 0 and hist_mean > 0:
                lines.append(f"   📋 History: {hist_mean:.1f}±{hist_std:.1f} (n={n_matches})")
            
            # Edge calculation
            if sim_data and line:
                mean = sim_data.get('mean', 0) or 0
                if mean > 0:
                    gap = line - mean
                    gap_pct = abs(gap / mean * 100)
                    gap_dir = "above" if gap > 0 else "below"
                    lines.append(f"   🎯 Line {gap_dir} proj by {abs(gap):.1f} ({gap_pct:.0f}%)")
            
            # AI Commentary - explain the edge
            commentary = _generate_tennis_commentary(p, line, direction)
            if commentary:
                lines.append(f"   💡 {commentary}")
    
    # Footer
    lines.append("\n" + "━" * 45)
    lines.append("📊 SOP v2.1 | 10K MC Sims | Tennis Abstract Data")
    lines.append("⚠️ One player, one bet per match")
    lines.append("━" * 45)
    
    return "\n".join(lines)


def _generate_tennis_commentary(play: Dict, line: float, direction: str) -> str:
    """
    Generate MATH-ONLY commentary for tennis props.
    No speculation, only what was computed.
    """
    sim_data = play.get('simulation', {}) or {}
    profile_data = play.get('profile_data', {}) or {}
    
    mean = sim_data.get('mean', 0) or profile_data.get('historical_mean', 0) or 0
    std = sim_data.get('std', 0) or profile_data.get('historical_std', 0) or 0
    prob = play.get('probability', 0) or 0
    n_matches = profile_data.get('n_matches', play.get('n_matches', 0)) or 0
    
    if not mean:
        return ""
    
    # Calculate z-score
    z_score = (line - mean) / std if std > 0 else 0
    
    # Generate commentary based on math
    direction_upper = direction.upper()
    
    if direction_upper == 'HIGHER':
        if z_score < -0.5:
            return f"Line well below avg ({mean:.1f}) — favorable OVER"
        elif z_score < 0:
            return f"Line slightly below avg ({mean:.1f})"
        else:
            return f"Line at/above avg — variance play"
    else:  # LOWER
        if z_score > 0.5:
            return f"Line well above avg ({mean:.1f}) — favorable UNDER"
        elif z_score > 0:
            return f"Line slightly above avg ({mean:.1f})"
        else:
            return f"Line at/below avg — variance play"


def send_telegram(plays: List[Dict], enhanced: bool = True, surface: str = "Hard") -> bool:
    """
    Send plays to Telegram.
    
    Args:
        plays: List of play dicts
        enhanced: Use enhanced format with math/commentary (default True)
        surface: Court surface for context
    """
    
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
    
    if enhanced:
        message = format_enhanced_message(plays, surface)
    else:
        message = format_message(plays)
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
    }
    
    if HAS_REQUESTS:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️ Telegram error: {resp.text}")
        return resp.status_code == 200
    else:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200


def send_tennis_analysis(results: Dict) -> bool:
    """
    Send full tennis analysis results to Telegram.
    Handles message length limits by splitting into multiple messages.
    
    Args:
        results: Full results dict from CalibratedTennisPropsEngine.analyze_slate()
    """
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
    
    # Collect all playable picks
    tiers = results.get('tiers', {})
    slam_plays = tiers.get('SLAM', [])
    strong_plays = tiers.get('STRONG', [])
    lean_plays = tiers.get('LEAN', [])
    
    if not slam_plays and not strong_plays and not lean_plays:
        message = "🎾 TENNIS — No playable edges found (all props < 55%)"
        return _send_single_message(message)
    
    surface = results.get('surface', 'Hard')
    
    # Send in batches to avoid Telegram's 4096 char limit
    # First: Summary + SLAM picks (most important)
    messages_sent = 0
    
    # Message 1: Summary + SLAM
    msg1 = _format_summary_message(slam_plays, strong_plays, lean_plays, surface)
    if slam_plays:
        msg1 += "\n\n🔥 SLAM PICKS (70%+)\n" + "─" * 30
        for p in slam_plays[:10]:  # Top 10 SLAM
            msg1 += _format_single_play(p)
    
    if len(msg1) > 4000:
        msg1 = msg1[:3900] + "\n...(truncated)"
    
    if _send_single_message(msg1):
        messages_sent += 1
    
    # Message 2: STRONG picks (if any)
    if strong_plays:
        msg2 = "💪 STRONG PICKS (62-70%)\n" + "─" * 30
        for p in strong_plays[:8]:  # Top 8 STRONG
            msg2 += _format_single_play(p)
        msg2 += "\n\n📊 SOP v2.1 | 10K MC Sims"
        
        if _send_single_message(msg2):
            messages_sent += 1
    
    return messages_sent > 0


def send_tennis_signals(signals: List[Dict], surface: str = "Hard") -> bool:
    """Send already-exported governed tennis signals.

    This avoids re-analyzing from saved slates (which can go stale).
    Expected input is a JSON list like outputs/tennis_signals_latest.json.
    """
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

    if not signals:
        return _send_single_message("🎾 TENNIS — No governed signals available")

    slam = [s for s in signals if str(s.get('tier') or '').upper() == 'SLAM']
    strong = [s for s in signals if str(s.get('tier') or '').upper() == 'STRONG']
    lean = [s for s in signals if str(s.get('tier') or '').upper() == 'LEAN']

    # Message 1: Summary + SLAM (if any)
    msg1 = _format_summary_message(slam, strong, lean, surface)
    msg1 += "\n\n✅ Source: outputs/tennis_signals_latest.json"
    if slam:
        msg1 += "\n\n🔥 SLAM PICKS\n" + "─" * 30
        for p in slam[:10]:
            msg1 += _format_single_play(p)
    if len(msg1) > 4000:
        msg1 = msg1[:3900] + "\n...(truncated)"

    sent = 0
    if _send_single_message(msg1):
        sent += 1

    # Message 2: STRONG
    if strong:
        msg2 = "💪 STRONG PICKS\n" + "─" * 30
        for p in strong[:8]:
            msg2 += _format_single_play(p)
        msg2 += "\n\n📊 Governed tiers | pick_state=OPTIMIZABLE"
        if _send_single_message(msg2):
            sent += 1

    # Message 3: LEAN (optional, keep brief)
    if lean and sent < 3:
        msg3 = "📈 LEAN PICKS\n" + "─" * 30
        for p in lean[:6]:
            msg3 += _format_single_play(p)
        msg3 += "\n\n⚠️ LEAN = lower confidence tier"
        if _send_single_message(msg3):
            sent += 1

    return sent > 0


def _format_summary_message(slam: list, strong: list, lean: list, surface: str) -> str:
    """Format summary header for Telegram"""
    from datetime import datetime
    lines = [
        "━" * 35,
        "🎾 TENNIS PROPS — CALIBRATED",
        f"📅 {datetime.now().strftime('%B %d, %Y')}",
        f"🏟️ Surface: {surface}",
        "━" * 35,
        f"🔥 SLAM: {len(slam)} | 💪 STRONG: {len(strong)} | 📈 LEAN: {len(lean)}",
    ]
    return "\n".join(lines)


def _format_single_play(p: Dict) -> str:
    """Format a single play for Telegram (compact)"""
    # Support both legacy tennis-props keys and canonical signal keys
    player = (p.get('player') or p.get('entity') or 'Unknown')
    stat = (p.get('stat') or p.get('stat_type') or p.get('market') or '?')
    player = str(player)[:20]
    stat = str(stat)[:12]
    direction = "⬆️" if _norm_direction(p.get('direction', '')) == 'HIGHER' else "⬇️"
    line = p.get('line', 0) or 0
    prob = p.get('probability', 0) or 0
    
    # Handle both decimal (0.70) and percent (70) formats
    prob_pct = prob * 100 if prob < 1.5 else prob
    
    return f"\n{direction} {player}: {stat} {line} ({prob_pct:.0f}%)"


def _send_single_message(message: str) -> bool:
    """Send a single message to Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
    }
    
    try:
        if HAS_REQUESTS:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                print(f"⚠️ Telegram error: {resp.text}")
            return resp.status_code == 200
        else:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"⚠️ Telegram send error: {e}")
        return False


def send_telegram_raw(message: str) -> bool:
    """Send raw message to Telegram."""
    
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
    }
    
    if HAS_REQUESTS:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    else:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200


def send_parlays(picks: List[Dict], parlay_name: str = "Tennis Parlay") -> bool:
    """
    Send parlay picks to Telegram with professional formatting.
    
    Args:
        picks: List of pick dicts with player, stat, line, direction, probability
        parlay_name: Name for the parlay (e.g., "3-Leg Power Parlay")
    """
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
    
    if not picks:
        return False
    
    from datetime import datetime
    
    # Calculate combined probability
    combined_prob = 1.0
    for p in picks:
        prob = p.get('probability', 0) or 0
        if prob < 1.5:  # Decimal format
            combined_prob *= prob
        else:  # Already percent
            combined_prob *= (prob / 100)
    
    # Build professional message
    lines = [
        "━" * 35,
        f"🎾 {parlay_name.upper()}",
        f"📅 {datetime.now().strftime('%B %d, %Y')}",
        "━" * 35,
        "",
    ]
    
    # Human-readable stat display names (CRITICAL: distinguish 1st set vs total)
    STAT_DISPLAY_NAMES = {
        'games_won': 'TOTAL Games Won',
        '1st_set_games_won': '1ST SET Games Won',
        '1st_set_games': '1ST SET Games Played',
        'games_played': 'Total Games Played',
        'sets_won': 'Sets Won',
        'sets_played': 'Sets Played',
        'aces': 'Aces',
        'double_faults': 'Double Faults',
        'tiebreakers': 'Tiebreakers',
        'breakpoints_won': 'Break Points Won',
        'fantasy_score': 'Fantasy Score',
    }
    
    # Add each pick
    for i, p in enumerate(picks, 1):
        player = p.get('player', 'Unknown')
        stat_raw = p.get('stat', p.get('stat_type', '?'))
        # Convert to human-readable display name
        stat = STAT_DISPLAY_NAMES.get(stat_raw, stat_raw.replace('_', ' ').title())
        direction = _norm_direction(p.get('direction', ''))
        line = p.get('line', 0)
        prob = p.get('probability', 0) or 0
        prob_pct = prob * 100 if prob < 1.5 else prob
        
        dir_emoji = "⬆️" if direction == 'HIGHER' else "⬇️"
        tier = p.get('tier', 'PLAY')
        tier_emoji = "🔥" if tier == 'SLAM' else "💪" if tier == 'STRONG' else "📈"
        
        lines.append(f"LEG {i}: {tier_emoji}")
        lines.append(f"  {dir_emoji} {player}")
        lines.append(f"  {stat} {direction} {line}")
        lines.append(f"  Confidence: {prob_pct:.0f}%")
        lines.append("")
    
    # Footer with combined probability
    lines.append("━" * 35)
    lines.append(f"📊 Combined Probability: {combined_prob * 100:.1f}%")
    lines.append(f"🎯 Legs: {len(picks)}")
    lines.append("")
    lines.append("⚠️ Risk management: Max 2% bankroll")
    lines.append("📊 SOP v2.1 | 10K MC Sims")
    lines.append("━" * 35)
    
    message = '\n'.join(lines)
    
    return _send_single_message(message)


def send_professional_report(results: Dict) -> bool:
    """
    Send a full professional report to Telegram - comprehensive format.
    
    Args:
        results: Full results dict from CalibratedTennisPropsEngine.analyze_slate()
    """
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
    
    from datetime import datetime
    
    tiers = results.get('tiers', {})
    slam_plays = tiers.get('SLAM', [])
    strong_plays = tiers.get('STRONG', [])
    lean_plays = tiers.get('LEAN', [])
    
    if not slam_plays and not strong_plays and not lean_plays:
        message = "🎾 TENNIS — No playable edges found (all props < 55%)"
        return _send_single_message(message)
    
    surface = results.get('surface', 'Hard')
    total_analyzed = len(results.get('results', []))
    
    # Message 1: Summary + SLAM
    lines = [
        "╔" + "═" * 33 + "╗",
        "║   🎾 TENNIS ANALYSIS REPORT    ║",
        "╚" + "═" * 33 + "╝",
        "",
        f"📅 {datetime.now().strftime('%A, %B %d, %Y')}",
        f"🏟️ Surface: {surface}",
        f"📊 Props Analyzed: {total_analyzed}",
        "",
        "━" * 35,
        "SUMMARY",
        "━" * 35,
        f"🔥 SLAM (70%+):      {len(slam_plays)}",
        f"💪 STRONG (62-70%):  {len(strong_plays)}",
        f"📈 LEAN (55-62%):    {len(lean_plays)}",
        "",
    ]
    
    # Add SLAM picks
    if slam_plays:
        lines.append("🔥 SLAM PICKS")
        lines.append("─" * 30)
        for p in slam_plays[:8]:
            lines.append(_format_pro_pick(p))
        if len(slam_plays) > 8:
            lines.append(f"  ... +{len(slam_plays) - 8} more")
        lines.append("")
    
    msg1 = '\n'.join(lines)
    success1 = _send_single_message(msg1)
    
    # Message 2: STRONG + LEAN (if any)
    if strong_plays or lean_plays:
        lines2 = []
        
        if strong_plays:
            lines2.append("💪 STRONG PICKS")
            lines2.append("─" * 30)
            for p in strong_plays[:6]:
                lines2.append(_format_pro_pick(p))
            lines2.append("")
        
        if lean_plays:
            lines2.append("📈 LEAN PICKS")
            lines2.append("─" * 30)
            for p in lean_plays[:4]:
                lines2.append(_format_pro_pick(p))
            lines2.append("")
        
        lines2.append("━" * 35)
        lines2.append("⚠️ SOP v2.1 Rules:")
        lines2.append("• One player, one bet per match")
        lines2.append("• Don't combine correlated stats")
        lines2.append("• 2,000 Monte Carlo simulations")
        lines2.append("━" * 35)
        
        msg2 = '\n'.join(lines2)
        success2 = _send_single_message(msg2)
        return success1 and success2
    
    return success1


def _format_pro_pick(p: Dict) -> str:
    """Format a single pick for professional report."""
    player = p.get('player', 'Unknown')[:18]
    stat = p.get('stat', '?')[:10]
    direction = p.get('direction', '').upper()
    line = p.get('line', 0)
    prob = p.get('probability', 0) or 0
    prob_pct = prob * 100 if prob < 1.5 else prob
    
    dir_sym = "▲" if direction == 'HIGHER' else "▼"
    return f"  {dir_sym} {player}: {stat} {line} ({prob_pct:.0f}%)"


if __name__ == "__main__":
    # Test with sample data
    test_plays = [
        {
            "engine": "TOTAL_SETS_ENGINE",
            "players": ["Djokovic", "Alcaraz"],
            "line": 2.5,
            "direction": "OVER",
            "probability": 0.67,
            "tier": "STRONG",
            "generated_at": "2026-01-21T00:00:00Z",
        }
    ]
    
    msg = format_message(test_plays)
    print(msg)
    
    if BOT_TOKEN and CHAT_ID:
        send_telegram(test_plays)
        print("\n✅ Sent to Telegram")
    else:
        print("\n⚠️ Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to send")
