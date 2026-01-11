import json, os, datetime, sys
p='outputs/validated_primary_edges.json'
print('path:',p)
print('exists', os.path.exists(p))
if not os.path.exists(p):
    print('validated file missing')
    sys.exit(2)
print('mtime', datetime.datetime.fromtimestamp(os.path.getmtime(p)))
with open(p,'r',encoding='utf-8') as f:
    data=json.load(f)
print('total picks', len(data))
if not data:
    print('no picks')
    sys.exit(3)
from collections import Counter
keys=set()
for item in data[:5]:
    keys.update(item.keys())
print('sample keys (first 5 picks):', sorted(list(keys))[:40])
# count resolved/status/result presence
cnt=Counter()
for item in data:
    if 'resolved' in item:
        cnt['resolved']+=1
    if 'result' in item:
        cnt['result']+=1
    if 'status' in item:
        cnt['status']+=1
    if item.get('resolved') or item.get('result') or item.get('status'):
        cnt['any_flag']+=1
print('flags counts:', dict(cnt))
# sample game id fields
sample=data[0]
possible_ids=['game_id','game_pk','espn_game_id','gameId','game_pk_espn','game_pk']
found={k: sample.get(k) for k in possible_ids if sample.get(k) is not None}
print('sample id fields found in first pick:', found)
print('first pick snippet:')
import pprint
pprint.pprint({k: sample[k] for k in list(sample.keys())[:20]})
