#!/usr/bin/env python3
if __name__ == "__main__":
    raise RuntimeError("Direct execution forbidden. Use run_daily.py")

from auto_ingest import UnderDogIngester

picks_text = """athlete or team avatar
Jonathan Taylor

IND @ HOU - 12:00PM CST

0.5
Rush + Rec TDs

Higher
1.04x

athlete or team avatar
C.J. Stroud

HOU vs IND - 12:00PM CST

213.5
Pass Yards

Higher

1.5
Pass TDs

Higher
1.03x

athlete or team avatar
Michael Pittman Jr.

IND @ HOU - 12:00PM CST

0.5
Rush + Rec TDs

Higher
2.6x

athlete or team avatar
Christian Kirk

HOU vs IND - 12:00PM CST

0.5
Rush + Rec TDs

Higher
1.85x

athlete or team avatar
Nico Collins

HOU vs IND - 12:00PM CST

61.5
Receiving Yards

Higher
"""

ingester = UnderDogIngester()
picks = ingester.ingest(picks_text)
print(f'\n📊 Ingested {len(picks)} picks')
for p in picks:
    print(f"   {p['player']} ({p['team']}) - {p['stat']}: {p['line']} {p['direction']}")
