#!/usr/bin/env python
"""Send Monte Carlo analysis to Telegram."""

import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from pathlib import Path
import re

load_dotenv()


def get_latest_mc_file() -> str:
    """Find the most recent Monte Carlo output file."""
    outputs = list(Path('outputs').glob('MC_ALL_GAMES_*.txt'))
    if outputs:
        latest = sorted(outputs, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        return latest
    return None


def parse_mc_file(filepath: str) -> str:
    """Extract key data from MC output and format for Telegram."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        message_lines = ['📊 UNDERDOG ANALYSIS\n']
        current_league = None
        in_game = False
        in_bet_section = False
        game_name = ""
        bet_count = 0
        nfl_complete = False
        
        for i, line in enumerate(lines):
            # Detect NFL section
            if '🏈 NFL WILD CARD' in line:
                current_league = 'NFL'
                message_lines.append('\n🏈 NFL PLAYOFF SLATE')
                message_lines.append('-' * 45)
            
            # Detect NBA section
            elif '🏀 NBA REGULAR' in line:
                current_league = 'NBA'
                if not nfl_complete:
                    message_lines.append('\n\n🏀 NBA SLATE (Top 65%+ Picks)')
                    message_lines.append('-' * 45)
                    nfl_complete = True
            
            # Detect game header (IND @ HOU — Sunday 12:00 PM CST)
            if '### GAME:' in line:
                in_game = True
                in_bet_section = False
                match = re.search(r'### GAME: (.+?) —', line)
                if match:
                    game_name = match.group(1).strip()
                    message_lines.append(f'\n{game_name}')
                bet_count = 0
            
            # Detect start of Individual Bet Hit Rates section
            if in_game and '**Individual Bet Hit Rates:**' in line:
                in_bet_section = True
                bet_count = 0
            
            # End of game section (dashes indicate end)
            if in_game and line.startswith('-' * 10):
                in_game = False
                in_bet_section = False
            
            # Extract individual bet rates when in bet section
            if in_bet_section and re.match(r'^\s+\d+\.\s+', line):
                match = re.search(r'\d+\.\s+(.+?):\s+(\d+\.\d+)%', line)
                if match:
                    player_stat = match.group(1).strip()
                    pct = float(match.group(2))
                    bet_count += 1
                    
                    # For NFL: show all bets
                    if current_league == 'NFL':
                        if pct > 68:
                            emoji = '🔥'
                        elif pct > 65:
                            emoji = '✅'
                        else:
                            emoji = '•'
                        message_lines.append(f'  {emoji} {player_stat}: {pct}%')
                    
                    # For NBA: only show 65%+ bets, max 5 per game
                    elif current_league == 'NBA' and pct > 65 and bet_count <= 5:
                        message_lines.append(f'  ✅ {player_stat}: {pct}%')
        
        message = '\n'.join(message_lines)
        
        return message
        
    except Exception as e:
        print(f"Error parsing MC file: {e}")
        return f"📊 Error parsing analysis. Check file: {filepath}"


async def send_analysis():
    token = os.getenv("SPORTS_BOT_TOKEN")
    chat_id = os.getenv("ADMIN_TELEGRAM_IDS") or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("❌ Missing SPORTS_BOT_TOKEN or chat ID in .env")
        return False

    # Get latest MC file
    mc_file = get_latest_mc_file()
    if not mc_file:
        print("❌ No Monte Carlo output file found")
        return False
    
    print(f"📄 Reading: {mc_file.name}")
    
    # Parse message from file
    message = parse_mc_file(str(mc_file))
    if not message:
        print("❌ Failed to parse MC file")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
        ) as resp:
            result = await resp.json()
            if result.get("ok"):
                print("✅ Message sent successfully!")
                print(f"   Chat: {chat_id}")
                print(f"   Message ID: {result['result']['message_id']}")
                return True
            else:
                print(f"❌ Failed: {result}")
                return False


if __name__ == "__main__":
    asyncio.run(send_analysis())
