"""Clear old updates and get fresh ones from Telegram."""
import os
import time
import requests
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('TELEGRAM_BOT_TOKEN')

# Delete webhook and clear pending updates
print('Clearing webhook and old updates...')
requests.get(f'https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true')

print('Waiting 3 seconds...')
time.sleep(3)

print('Fetching fresh updates (10 second timeout)...')
resp = requests.get(f'https://api.telegram.org/bot{token}/getUpdates?timeout=10')
data = resp.json()

updates = data.get('result', [])
print(f'Fresh updates received: {len(updates)}')
print()

chats = {}
for u in updates:
    for key in ['message', 'my_chat_member', 'chat_member', 'channel_post']:
        if key in u:
            obj = u[key]
            chat = obj.get('chat', obj) if isinstance(obj, dict) else {}
            if chat.get('id'):
                chats[chat['id']] = {
                    'type': chat.get('type'),
                    'title': chat.get('title') or chat.get('first_name')
                }

print('=== CHATS DETECTED ===')
for cid, info in chats.items():
    t = info['type']
    marker = '👥 GROUP/SUPERGROUP' if t in ('group', 'supergroup') else ('📢 CHANNEL' if t == 'channel' else '👤 PRIVATE')
    print(f"  {cid}: {marker} - {info['title']}")
    
# Check for groups specifically
groups = {k: v for k, v in chats.items() if v['type'] in ('group', 'supergroup')}
if groups:
    print()
    print('🎉 GROUP FOUND! Update your .env with:')
    for gid, ginfo in groups.items():
        print(f'   TELEGRAM_CHAT_ID={gid}')
else:
    print()
    print('⚠️ No groups detected yet.')
    print('Please send another message in your group, then run this again.')
