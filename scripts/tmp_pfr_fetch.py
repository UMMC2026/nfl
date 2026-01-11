import ssl, urllib.request, re, os
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

def url_for(cid, name, season=2025):
    last_letter = re.sub(r"[,.'-]", "", name).split()[-1][0].upper()
    return f"https://www.pro-football-reference.com/players/{last_letter}/{cid}/gamelog/{season}/"

def fetch(cid, name):
    url = url_for(cid, name)
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    out = os.path.join('outputs', f'{cid}_gamelog_2025.html')
    os.makedirs('outputs', exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print('Saved:', out)

# Known resolved IDs from run
pairs = [
    ('TaylJo02', 'Jonathan Taylor'),
    ('EtieTr00', 'Travis Etienne Jr.'),
    ('LawrTr00', 'Trevor Lawrence'),
    ('PittMi01', 'Michael Pittman Jr.'),
]
for cid, name in pairs:
    try:
        fetch(cid, name)
    except Exception as e:
        print('Error', cid, e)
