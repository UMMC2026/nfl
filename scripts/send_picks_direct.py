"""Send NFL picks directly to Telegram - bypass push_signals filter"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from telegram_push import _send

# Top 10 picks
picks_message = """*TOP 10 NFL PICKS - SUPER BOWL LX*

🔥 *Rhamondre Stevenson* (NE) RECEPTIONS LOWER 3.5
   70.0% confidence

🔥 *Jaxon Smith-Njigba* (SEA) REC_YDS HIGHER 94.5
   70.0% confidence

🔥 *Hunter Henry* (NE) REC_YDS HIGHER 40.5
   70.0% confidence

🔥 *Kayshon Boutte* (NE) REC_YDS HIGHER 31.5
   70.0% confidence

🔥 *AJ Barner* (SEA) REC_YDS HIGHER 24.5
   70.0% confidence

🔥 *Rhamondre Stevenson* (NE) REC_YDS HIGHER 24.5
   70.0% confidence

🔥 *Drake Maye* (NE) PASS_YDS HIGHER 223.5
   70.0% confidence

🔥 *Drake Maye* (NE) RUSH_YDS LOWER 36.5
   70.0% confidence

🔥 *Rhamondre Stevenson* (NE) RUSH_YDS HIGHER 50.5
   70.0% confidence

✅ *AJ Barner* (SEA) RECEPTIONS HIGHER 2.5
   66.6% confidence
"""

success = _send(picks_message)

if success:
    print("✅ Picks sent to Telegram!")
else:
    print("❌ Failed to send - check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
