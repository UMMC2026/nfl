"""Force get all Telegram updates including group events."""
import os
import requests
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('TELEGRAM_BOT_TOKEN')

# Force get ALL updates
resp = requests.get(
    f'https://api.telegram.org/bot{token}/getUpdates',
    params={'allowed_updates': '["message","my_chat_member","chat_member"]'}
)
data = resp.json()

print(f'Total updates: {len(data.get("result", []))}')
print()

chats_found = {}

for u in data.get('result', []):
    for key in ['message', 'my_chat_member', 'chat_member', 'channel_post']:
        if key in u:
            obj = u[key]
            if isinstance(obj, dict):
                chat = obj.get('chat', obj)
                if isinstance(chat, dict) and chat.get('id'):
                    cid = chat['id']
                    if cid not in chats_found:
                        chats_found[cid] = {
                            'type': chat.get('type'),
                            'title': chat.get('title') or chat.get('first_name') or chat.get('username'),
                        }

print('=== ALL CHATS FOUND ===')
for cid, info in chats_found.items():
    marker = '👥 GROUP' if info['type'] in ('group', 'supergroup') else '👤 PRIVATE'
    print(f"  {cid}: {marker} - {info['title']}")

if not any(info['type'] in ('group', 'supergroup') for info in chats_found.values()):
    print()
    print("⚠️  NO GROUPS FOUND YET")
    print()
    print("Please do this in Telegram:")
    print("  1. Open UMMC_SPORTS_Analysis group")
    print("  2. Type any message (like 'test')")
    print("  3. Run this script again")
