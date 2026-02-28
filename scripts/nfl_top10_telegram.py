"""
NFL Top 10 Telegram Sender with AI + Game Context
Generates and sends TOP 10 picks with DeepSeek commentary and matchup context
"""

import json
import sys
import io
import os
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from dotenv import load_dotenv
import requests

# Load environment variables from .env
load_dotenv()

# Force UTF-8 encoding for Windows console
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent))

# Custom Telegram send for UMMCSPORTS channel only
def telegram_send_to_channel(text: str) -> bool:
    """Send message to UMMCSPORTS Telegram channel only."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "-1003743893834")
    
    if not token or not channel_id:
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": channel_id,
        "text": text,
        "parse_mode": "HTML"  # HTML is more lenient than Markdown
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json() if response.content else {}
        return bool(data.get("ok"))
    except Exception:
        return False

TELEGRAM_AVAILABLE = True


def sanitize_markdown(text: str) -> str:
    """Clean AI text for Telegram - remove formatting that conflicts with message markdown."""
    result = text
    
    # Replace curly quotes/dashes with standard ASCII
    result = result.replace('\u2018', "'").replace('\u2019', "'")
    result = result.replace('\u201c', '"').replace('\u201d', '"')  
    result = result.replace('\u2013', '-').replace('\u2014', '-')
    
    # Remove ALL markdown formatting from AI text
    result = result.replace('**', '')  # Bold
    result = result.replace('__', '')  # Underline
    result = result.replace('*', '')   # Italic
    result = result.replace('_', '')   # Underscore
    result = result.replace('`', '')   # Code
    
    return result


def get_matchup_context_summary() -> str:
    """Extract matchup context from team rankings."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from nfl_team_context import NFL_TEAM_CONTEXT
        
        # Get today's matchups
        from nfl_menu import get_todays_matchups
        matchups = get_todays_matchups()
        
        if not matchups:
            return "No matchup data available."
        
        context_lines = []
        for game in matchups:
            away = game.get('away', '')
            home = game.get('home', '')
            
            if not away or not home:
                continue
            
            away_ctx = NFL_TEAM_CONTEXT.get(away)
            home_ctx = NFL_TEAM_CONTEXT.get(home)
            
            if away_ctx and home_ctx:
                context_lines.append(f"{away} @ {home}:")
                context_lines.append(f"  {away}: Off Rush #{away_ctx.rush_off_rank} Pass #{away_ctx.pass_off_rank} | Def Rush #{away_ctx.rush_def_rank} Pass #{away_ctx.pass_def_rank}")
                context_lines.append(f"  {home}: Off Rush #{home_ctx.rush_off_rank} Pass #{home_ctx.pass_off_rank} | Def Rush #{home_ctx.rush_def_rank} Pass #{home_ctx.pass_def_rank}")
        
        return "\n".join(context_lines) if context_lines else "Matchup context not available."
    
    except Exception as e:
        return f"Could not load matchup context: {e}"


def generate_ai_commentary_with_context(picks: List[Dict], matchup_context: str) -> str:
    """Generate AI commentary including game context."""
    import os
    import requests
    
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        return _generate_fallback_commentary(picks, matchup_context)
    
    # Build context for LLM
    playable = [p for p in picks 
                if p.get('tier') in ['SLAM', 'STRONG', 'LEAN'] 
                or p.get('action') in ['SLAM', 'STRONG', 'CONSIDER', 'LEAN']
                or p.get('grade') in ['A+', 'A', 'B']]
    
    if not playable:
        return "No playable NFL picks found."
    
    # Helper to get probability as percentage
    def get_prob(p):
        prob = p.get('probability', 0)
        return prob * 100 if prob <= 1.0 else prob
    
    prompt = "Analyze these NFL prop picks with game context and provide brief insights:\n\n"
    prompt += "GAME CONTEXT:\n"
    prompt += matchup_context + "\n\n"
    prompt += "TOP PICKS:\n"
    
    for i, pick in enumerate(playable[:5], 1):
        prob = get_prob(pick)
        recent_avg = pick.get('mu', pick.get('recent_avg', 0))
        sigma = pick.get('sigma', 0)
        
        prompt += f"{i}. {pick.get('player')} ({pick.get('team')}) - "
        prompt += f"{pick.get('stat')} {pick.get('direction')} {pick.get('line')}\n"
        prompt += f"   Confidence: {prob:.1f}%, Recent Avg: {recent_avg:.1f} (σ={sigma:.1f})\n"
        
        if pick.get('opponent'):
            prompt += f"   vs {pick['opponent']}\n"
    
    prompt += "\nProvide (in 200 words max):\n"
    prompt += "1. Why top picks have strong edges (matchup advantages)\n"
    prompt += "2. Key scheme/ranking factors from game context\n"
    prompt += "3. Risk warnings (injuries, weather, variance)\n"
    prompt += "Use 'data suggests' language, not imperatives."
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {deepseek_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an NFL analytics expert providing concise, "
                            "data-driven insights on prop bets. Focus on matchup dynamics, "
                            "scheme advantages, and risk factors. Keep responses under 200 words."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 350
            },
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            print(f"⚠️  DeepSeek API error: {response.status_code}")
            return _generate_fallback_commentary(picks, matchup_context)
            
    except Exception as e:
        print(f"⚠️  AI commentary error: {e}")
        return _generate_fallback_commentary(picks, matchup_context)


def _generate_fallback_commentary(picks: List[Dict], matchup_context: str = "") -> str:
    """Generate basic commentary without AI."""
    playable = [p for p in picks 
                if p.get('tier') in ['SLAM', 'STRONG', 'LEAN'] 
                or p.get('action') in ['SLAM', 'STRONG', 'CONSIDER', 'LEAN']
                or p.get('grade') in ['A+', 'A', 'B']]
    
    if not playable:
        return "No playable picks found in today's NFL slate."
    
    def get_prob(p):
        prob = p.get('probability', 0)
        return prob * 100 if prob <= 1.0 else prob
    
    total_plays = len(playable)
    probs = [get_prob(p) for p in playable]
    avg_prob = sum(probs) / len(probs) if probs else 0
    
    strongs = len([p for p in playable if p.get('grade') in ['A', 'A+'] or p.get('tier') == 'STRONG'])
    
    commentary = f"Analysis identified {total_plays} playable NFL props with average confidence {avg_prob:.1f}%. "
    
    if strongs > 0:
        commentary += f"{strongs} STRONG plays backed by statistical trends and matchup advantages. "
    
    top_pick = playable[0]
    prob = get_prob(top_pick)
    commentary += f"Top pick: {top_pick.get('player')} {top_pick.get('stat')} {top_pick.get('direction')} {top_pick.get('line')} ({prob:.0f}% confidence). "
    
    if matchup_context:
        commentary += "Game context shows key scheme advantages in selected matchups. "
    
    commentary += "Monitor weather, late injury news, and snap count for final decisions."
    
    return commentary


def generate_top_10_telegram_message(analysis_file: Path) -> str:
    """Generate TOP 10 NFL picks Telegram message with AI + game context."""
    
    with open(analysis_file, 'r') as f:
        data = json.load(f)
    
    # Handle both data formats
    picks = data.get('picks', data.get('results', []))
    
    # Filter to playable picks
    playable = [p for p in picks 
                if p.get('tier') in ['SLAM', 'STRONG', 'LEAN'] 
                or p.get('action') in ['SLAM', 'STRONG', 'CONSIDER', 'LEAN']
                or p.get('grade') in ['A+', 'A', 'B']]
    
    if not playable:
        return "❌ No playable NFL picks found.\nAll props below confidence threshold."
    
    # Sort by probability and take TOP 10
    def get_prob(p):
        prob = p.get('probability', 0)
        return prob * 100 if prob <= 1.0 else prob
    
    playable.sort(key=get_prob, reverse=True)
    top_10 = playable[:10]
    
    # Get matchup context
    print("📊 Loading matchup context...")
    matchup_context = get_matchup_context_summary()
    
    # Generate AI commentary with context
    print("🤖 Generating AI commentary with game context...")
    ai_commentary = generate_ai_commentary_with_context(top_10, matchup_context)
    
    # Build message (HTML format for Telegram)
    message = "🏈 <b>NFL TOP 10 PICKS</b>\n"
    message += "=" * 40 + "\n\n"
    
    for i, pick in enumerate(top_10, 1):
        emoji = "📈" if pick.get('direction', '').lower() in ['higher', 'over'] else "📉"
        prob = get_prob(pick)
        
        # Tier badge
        tier = pick.get('tier') or pick.get('action', '')
        grade = pick.get('grade', '')
        if tier == 'SLAM' or grade == 'A+':
            badge = "🔥"
        elif tier == 'STRONG' or grade == 'A':
            badge = "💪"
        else:
            badge = "⚡"
        
        message += f"{badge} <b>#{i}</b> - {pick.get('player')} ({pick.get('team', 'N/A')})\n"
        message += f"   {emoji} {pick.get('stat', '').upper()} {pick.get('direction', '').upper()} {pick.get('line', 0)}\n"
        message += f"   💯 {prob:.1f}%"
        
        if pick.get('opponent'):
            message += f" | vs {pick['opponent']}"
        
        message += "\n\n"
    
    message += "=" * 40 + "\n"
    message += f"📊 Top {len(top_10)} of {len(playable)} Playable\n"
    message += "🎯 Risk-First | Drive-Level MC\n"
    
    # Add AI commentary (sanitized, HTML format)
    message += "\n💬 <b>AI INSIGHTS</b>\n"
    message += sanitize_markdown(ai_commentary[:500])  # Sanitize and truncate if needed
    
    return message


def send_top_10_to_telegram(analysis_file: Path = None):
    """Send TOP 10 NFL picks to Telegram with AI + game context."""
    
    # Find latest if not specified
    if not analysis_file:
        outputs_dir = Path("outputs")
        nfl_files = sorted(outputs_dir.glob("nfl_analysis_*.json"), reverse=True)
        if not nfl_files:
            print("❌ No NFL analysis files found in outputs/")
            print("   Run [2] ANALYZE NFL SLATE first")
            return False
        analysis_file = nfl_files[0]
        print(f"📁 Using: {analysis_file.name}")
    
    if not analysis_file.exists():
        print(f"❌ File not found: {analysis_file}")
        return False
    
    # Generate message
    message = generate_top_10_telegram_message(analysis_file)
    
    # Show preview
    print("\n" + "=" * 70)
    print("TELEGRAM MESSAGE PREVIEW")
    print("=" * 70)
    print(message)
    print("=" * 70)
    
    # Send to Telegram
    if not TELEGRAM_AVAILABLE:
        print("\n⚠️  Telegram module not available")
        return False
    
    print("\n📱 Sending to UMMCSPORTS Telegram channel...")
    try:
        result = telegram_send_to_channel(message)
        if result:
            print("✅ TOP 10 NFL picks sent to UMMCSPORTS!")
            return True
        else:
            print("⚠️  Telegram send failed")
            print("   Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in .env")
            return False
    except Exception as e:
        print(f"⚠️  Telegram error: {e}")
        return False


if __name__ == "__main__":
    send_top_10_to_telegram()
