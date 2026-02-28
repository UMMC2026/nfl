#!/usr/bin/env python3
"""Quick registry status checker."""
import json

with open('config/sport_registry.json') as f:
    registry = json.load(f)

print("=" * 60)
print("SPORT REGISTRY STATUS - 2026-02-03")
print("=" * 60)

for sport, cfg in registry['sports'].items():
    if cfg['enabled'] and cfg['status'] == 'PRODUCTION':
        status = '✅'
    elif cfg['enabled']:
        status = '⚠️'
    else:
        status = '❌'
    
    frozen = ' [FROZEN]' if cfg.get('frozen') else ''
    print(f"{status} {sport:8} | enabled={str(cfg['enabled']):5} | {cfg['status']:12} | v{cfg['version']}{frozen}")

print("=" * 60)
