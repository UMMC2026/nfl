#!/usr/bin/env python3
"""Convert scraped props to menu format.

Also updates the canonical "active slate" pointers used by menu.py:
- .analyzer_settings.json (primary)
- state/active_slate.json (canonical pointer)

And keeps legacy menu_settings.json in sync for older helper scripts.
"""

import json
from datetime import date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def _safe_load_json(path: Path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _set_active_slate(output_path: Path, *, label: str) -> None:
    # Canonical menu settings
    analyzer_settings_path = PROJECT_ROOT / ".analyzer_settings.json"
    analyzer = _safe_load_json(analyzer_settings_path)
    analyzer["last_slate"] = str(output_path)
    analyzer["last_label"] = label
    _write_json(analyzer_settings_path, analyzer)

    # Canonical active slate pointer
    active_slate_path = PROJECT_ROOT / "state" / "active_slate.json"
    active_payload = {
        "path": str(output_path),
        "label": label,
        "updated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _write_json(active_slate_path, active_payload)

    # Legacy settings for older scripts
    legacy_settings_path = PROJECT_ROOT / "menu_settings.json"
    legacy = _safe_load_json(legacy_settings_path)
    legacy["last_slate"] = str(output_path)
    legacy["last_label"] = label
    _write_json(legacy_settings_path, legacy)

def main():
    # Load scraped props
    with open(PROJECT_ROOT / 'outputs' / 'props_latest.json', encoding="utf-8") as f:
        data = json.load(f)
    
    # Convert to menu format
    props = []
    for p in data['props']:
        if p.get('parsed') and p.get('player') and p.get('stat') and p.get('line') and p.get('direction'):
            props.append({
                'player': p['player'],
                'stat': p['stat'],
                'line': p['line'],
                'direction': p['direction'],
                'league': 'NBA',
                'source': p.get('source', 'Scraped')
            })
    
    # Save in menu format
    output = {
        'plays': props,
        'raw_lines': [p.get('raw', '') for p in data['props'] if p.get('parsed')]
    }
    
    output_path = (PROJECT_ROOT / 'outputs' / f'SCRAPED_{date.today().strftime("%Y%m%d")}.json').resolve()
    with open(output_path, 'w', encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f'✓ Converted {len(props)} props to menu format')
    print(f'✓ Saved to: {output_path}')
    
    # Update canonical + legacy active slate pointers
    _set_active_slate(output_path, label='SCRAPED')
    
    print(f'✓ Set as active slate')
    print(f'\nNow run: .venv\\Scripts\\python.exe menu.py')
    print(f'Then press [2] to analyze the scraped slate')

if __name__ == "__main__":
    main()
