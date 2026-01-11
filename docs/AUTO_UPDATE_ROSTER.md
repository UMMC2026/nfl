# Auto-Update Roster Knowledge - Quick Reference

## How It Works

Your LocalValidator knowledge base now **automatically updates from picks.json** every time you run `ingest_underdog_data.py`.

## Workflow

1. **You enter Underdog lines** → `ingest_underdog_data.py` parses them
2. **Saves to picks.json** → Your source of truth
3. **Auto-updates LocalValidator** → Extracts player→team mappings
4. **Cheatsheet generation** → Uses fresh roster data

## Benefits

✅ **Always current** - Matches what you see on Underdog today  
✅ **Zero extra work** - Runs automatically when you ingest picks  
✅ **No stale APIs** - Uses your manual entry as source of truth  
✅ **Gradual learning** - Each day improves the knowledge base  
✅ **Manual override** - You can still edit `local_validator.py` directly  

## Files

- **`scripts/auto_update_roster_kb.py`** - Auto-update script
- **`local_validator.py`** - Updated with markers `# TEAM_KNOWLEDGE START/END`
- **`cache/nba_roster_kb.json`** - Full roster cache (for Ollama if needed)
- **`ingest_underdog_data.py`** - Now calls auto-update after saving picks.json

## Manual Updates (Optional)

If you need to update without running ingest:

```bash
.venv\Scripts\python.exe scripts\auto_update_roster_kb.py
```

## What Gets Updated

- **LocalValidator.TEAM_KNOWLEDGE** - Rebuilt from all players in picks.json
- **cache/nba_roster_kb.json** - Full roster with metadata for future Ollama use

## Verification

Check current roster knowledge:

```python
from local_validator import LocalValidator
print(f"Total players: {len(LocalValidator.TEAM_KNOWLEDGE)}")
print(f"Alex Sarr: {LocalValidator.TEAM_KNOWLEDGE.get('alex sarr')}")
```

## Troubleshooting

**Q: Player missing from KB?**  
A: They weren't in today's picks.json. Either:
- Wait until they appear in a future slate
- Manually add to `local_validator.py` between the START/END markers

**Q: Wrong team in KB?**  
A: Check `picks.json` - the auto-update uses that as source of truth.
If picks.json is wrong, fix it there and re-run auto-update.

**Q: Want to disable auto-update?**  
A: Comment out the auto-update block at the end of `ingest_underdog_data.py`

## Future: Ollama Integration

The `cache/nba_roster_kb.json` file is ready for Ollama prompt injection:

```python
# Load roster context for Ollama
import json
kb = json.load(open('cache/nba_roster_kb.json'))

prompt = f"""
Current NBA rosters (from picks.json):
{json.dumps(kb['rosters'], indent=2)}

Validate this pick: ...
"""
```

This gives Ollama your current, accurate roster data without relying on its stale training data.
