"""Check calibration data issues"""
import csv
from collections import Counter

# Check calibration_history.csv
with open('calibration_history.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f'Total rows: {len(rows)}')
if rows:
    print(f'Columns: {list(rows[0].keys())}')
print()

# Sample first 5 rows
print('First 5 rows:')
for r in rows[:5]:
    print(r)
print()

# Check 'actual_result' field (this is where hit/miss should be)
results = Counter(r.get('actual_result', 'MISSING') for r in rows)
print('actual_result values:')
for val, count in results.most_common():
    print(f'  {repr(val)}: {count}')

# Check 'outcome' field
outcomes = Counter(r.get('outcome', 'MISSING') for r in rows)
print('\noutcome values:')
for val, count in outcomes.most_common():
    print(f'  {repr(val)}: {count}')

# Combined check - what's the total resolved?
resolved = 0
hits = 0
for r in rows:
    hit_val = r.get('outcome', '') or r.get('hit', '') or r.get('actual_result', '')
    if hit_val.upper() in ('HIT', 'TRUE', '1', 'YES'):
        hits += 1
        resolved += 1
    elif hit_val.upper() in ('MISS', 'FALSE', '0', 'NO'):
        resolved += 1

print(f'\nResolved: {resolved}/{len(rows)}')
print(f'Hits: {hits}')
print(f'Hit Rate: {hits/resolved*100:.1f}%' if resolved > 0 else 'N/A')
