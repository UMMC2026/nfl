"""Quick script to find all Telegram chats the bot can access."""
import os
import requests
from dotenv import load_dotenv
load_dotenv()

bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

# Get bot info
bot_info = requests.get(f'https://api.telegram.org/bot{bot_token}/getMe').json()
print('Bot:', bot_info.get('result', {}).get('username'))

# Get updates
updates = requests.get(f'https://api.telegram.org/bot{bot_token}/getUpdates?limit=100').json()
print(f"Updates: {len(updates.get('result', []))} messages")

# Find all unique chats
chats = {}
for u in updates.get('result', []):
    for key in ['message', 'channel_post', 'my_chat_member', 'edited_channel_post']:
        if key in u:
            chat = u[key].get('chat', u[key])
            if isinstance(chat, dict) and chat.get('id'):
                chats[chat['id']] = {
                    'type': chat.get('type'),
                    'title': chat.get('title') or chat.get('username') or chat.get('first_name')
                }

print()
print('=== CHATS BOT HAS ACCESS TO ===')
if chats:
    for cid, info in chats.items():
        print(f"  {cid}: {info['type']} - {info['title']}")
else:
    print("  No chats found in recent updates.")
    print()
    print("TO FIX THIS:")
    print("  1. Open Telegram")
    print("  2. Go to your channel/group: @ummc_sports_analysis or @ummc_sportsbot")
    print("  3. Make sure the bot (@Ummc_I_Tech_Bot or similar) is added as ADMIN")
    print("  4. Send ANY message in the channel/group")
    print("  5. Run this script again")
