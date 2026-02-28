"""Quick ingest for MIN @ HOU slate."""
from parse_underdog_paste import parse_lines
import json
from pathlib import Path
from datetime import date

text = """athlete or team avatar
Kevin Durant

HOU vs MIN - 8:30PM CST

25.5
Points

Higher

Lower

35.5
Pts + Rebs + Asts

Higher

Lower

5.5
Rebounds

Higher

Lower

4.5
Assists

Higher

Lower

athlete or team avatar
Julius Randle

MIN @ HOU - 8:30PM CST

23.5
Points

Higher

Lower

35.5
Pts + Rebs + Asts

Higher

Lower

7.5
Rebounds

Higher

Lower

5.5
Assists

Higher

Lower

athlete or team avatar
Donte DiVincenzo

MIN @ HOU - 8:30PM CST

14.5
Points

Higher

Lower

23.5
Pts + Rebs + Asts

Higher

Lower

4.5
Rebounds

Higher

Lower

3.5
Assists

Higher

Lower

athlete or team avatar
Jaden McDaniels

MIN @ HOU - 8:30PM CST

15.5
Points

Higher

Lower

23.5
Pts + Rebs + Asts

Higher

Lower

4.5
Rebounds

Higher

Lower

2.5
Assists

Higher

Lower

athlete or team avatar
Reed Sheppard

HOU vs MIN - 8:30PM CST

9.5
Points

Higher

Lower

14.5
Pts + Rebs + Asts

Higher

Lower

1.5
Rebounds

Higher

Lower

2.5
Assists

Higher

Lower

athlete or team avatar
Amen Thompson

HOU vs MIN - 8:30PM CST

17.5
Points

Higher

Lower

30.5
Pts + Rebs + Asts

Higher

Lower

7.5
Rebounds

Higher

Lower

5.5
Assists

Higher

Lower

athlete or team avatar
Tari Eason

HOU vs MIN - 8:30PM CST

10.5
Points

Higher

Lower

18.5
Pts + Rebs + Asts

Higher

Lower

6.5
Rebounds

Higher

Lower

1.5
Assists

Higher

Lower

athlete or team avatar
Alperen Sengun

HOU vs MIN - 8:30PM CST

20.5
Points

Higher

Lower

36.5
Pts + Rebs + Asts

Higher

Lower

8.5
Rebounds

Higher

Lower

6.5
Assists

Higher

Lower

athlete or team avatar
Rudy Gobert

MIN @ HOU - 8:30PM CST

10.5
Points

Higher

Lower

23.5
Pts + Rebs + Asts

Higher

Lower

11.5
Rebounds

Higher

Lower

1.5
Assists

Higher

Lower

athlete or team avatar
Jabari Smith Jr.

HOU vs MIN - 8:30PM CST

14.5
Points

Higher

Lower

23.5
Pts + Rebs + Asts

Higher

Lower

6.5
Rebounds

Higher

Lower

1.5
Assists

Higher

Lower

athlete or team avatar
Mike Conley

MIN @ HOU - 8:30PM CST

6.5
Points

Higher

Lower

12.5
Pts + Rebs + Asts

Higher

Lower

2.5
Rebounds

Higher

Lower

3.5
Assists

Higher

Lower

athlete or team avatar
Naz Reid

MIN @ HOU - 8:30PM CST

14.5
Points

Higher

Lower

22.5
Pts + Rebs + Asts

Higher

Lower

5.5
Rebounds

Higher

Lower

2.5
Assists

Higher

Lower

athlete or team avatar
Bones Hyland

MIN @ HOU - 8:30PM CST

11.5
Points

Higher

Lower

17.5
Pts + Rebs + Asts

Higher

Lower

1.5
Rebounds

Higher

Lower

3.5
Assists

Higher

Lower
"""

lines = text.strip().split('\n')
props = parse_lines(lines)
print(f'Parsed {len(props)} props')

out_path = Path('slates') / f'MIN_HOU_USERPASTE_{date.today().strftime("%Y%m%d")}.json'
out_path.parent.mkdir(exist_ok=True)
out_path.write_text(json.dumps({'plays': props}, indent=2))
print(f'Saved to: {out_path}')

# Show first few
for p in props[:8]:
    print(f'  {p["player"]} {p["stat"]} {p["direction"]} {p["line"]}')
print(f'  ... and {len(props)-8} more')
