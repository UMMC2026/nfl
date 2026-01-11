"""
Telegram Signal Deduplication & History Tracker

Prevents duplicate picks from being sent multiple times.
Tracks what's been sent and only sends new/updated picks.
"""

import json
from datetime import datetime
from pathlib import Path


class TelegramSentTracker:
    """Track which picks have been sent to Telegram."""
    
    def __init__(self, history_file: str = "data/telegram_sent_history.json"):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = self._load_history()
    
    def _load_history(self) -> dict:
        """Load sent history from file."""
        if not self.history_file.exists():
            return {}
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def _save_history(self):
        """Save sent history to file."""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2)
    
    def _pick_key(self, pick: dict) -> str:
        """Generate unique key for a pick."""
        date = pick.get('date', 'unknown')
        player = pick.get('player', 'unknown').lower()
        stat = pick.get('stat', 'unknown').lower()
        line = pick.get('line', '0')
        return f"{date}|{player}|{stat}|{line}"
    
    def has_been_sent(self, pick: dict) -> bool:
        """Check if pick was already sent to Telegram."""
        key = self._pick_key(pick)
        return key in self.history
    
    def mark_sent(self, picks: list[dict], chat_id: str = None) -> int:
        """
        Mark picks as sent.
        
        Returns:
            Count of newly marked picks
        """
        new_count = 0
        timestamp = datetime.utcnow().isoformat()
        
        for pick in picks:
            key = self._pick_key(pick)
            if key not in self.history:
                self.history[key] = {
                    'sent_at': timestamp,
                    'pick': pick,
                    'chat_id': chat_id,
                }
                new_count += 1
        
        self._save_history()
        return new_count
    
    def filter_new_picks(self, picks: list[dict]) -> tuple[list, list]:
        """
        Separate picks into new and already-sent.
        
        Returns:
            (new_picks, already_sent_picks)
        """
        new = []
        already_sent = []
        
        for pick in picks:
            if self.has_been_sent(pick):
                already_sent.append(pick)
            else:
                new.append(pick)
        
        return new, already_sent
    
    def get_stats(self) -> dict:
        """Get statistics about sent picks."""
        return {
            'total_sent': len(self.history),
            'history_file': str(self.history_file),
        }
    
    def clear_history(self):
        """Clear all sent history (use with caution)."""
        self.history = {}
        self._save_history()
    
    def print_sent_picks(self, limit: int = 5):
        """Print recently sent picks."""
        items = list(self.history.items())[-limit:]
        print("\n" + "=" * 60)
        print(f"📨 RECENTLY SENT PICKS (Last {limit})")
        print("=" * 60)
        for key, entry in items:
            pick = entry.get('pick', {})
            sent_at = entry.get('sent_at', 'unknown')
            print(f"  {pick.get('player')} {pick.get('stat')} - {sent_at}")
        print("=" * 60 + "\n")
