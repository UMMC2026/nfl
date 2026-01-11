import json, ssl, urllib.request
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

def fetch(pid):
    url=f'https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{pid}/gamelog?season=2025&seasontype=2'
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        data=json.loads(resp.read().decode())
    labels=data.get('labels', [])
    st=data.get('seasonTypes') or []
    cats=st[0]['categories'] if st else []
    totals0=cats[0].get('totals') if cats else []
    totals1=cats[1].get('totals') if len(cats)>1 else []
    print('labels:', labels)
    if cats:
        print('cat0 keys:', list(cats[0].keys()))
        print('cat1 keys:', list(cats[1].keys()) if len(cats)>1 else None)
    print('category0 totals:', totals0)
    print('category1 totals:', totals1)

print('--- Pittman ---')
fetch(4241478)
print('--- Alec Pierce ---')
fetch(4362628)
print('--- Pat Freiermuth ---')
fetch(4361411)
print('--- Aaron Rodgers ---')
fetch(8439)
