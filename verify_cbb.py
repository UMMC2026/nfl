import sys
sys.path.insert(0, 'sports/cbb')
from shared.config import CBB_REGISTRY, L10_BLEND_WEIGHT, MARKET_ALIGNMENT_THRESHOLD

print('='*60)
print('CBB PRODUCTION STATUS VERIFICATION'.center(60))
print('='*60)
print(f'Enabled: {CBB_REGISTRY["enabled"]}')
print(f'Status: {CBB_REGISTRY["status"]}')
print(f'Version: {CBB_REGISTRY["version"]}')
print(f'L10 Blend: {L10_BLEND_WEIGHT}')
print(f'Market Gate: {MARKET_ALIGNMENT_THRESHOLD}%')
print('='*60)
