#!/usr/bin/env python3
"""
Parse Underdog Fantasy NBA props from structured text and ingest into picks.json.
Handles multi-game data with player, team, stat, line, direction, multiplier.
"""

import json
import re
from pathlib import Path
from datetime import datetime

# Parse game data
data = """
BKN @ WAS
6:00PM CST
Alex Sarr - WAS vs BKN - 6:00PM CST
  16.5 Points Higher / Lower
  27.5 Pts + Rebs + Asts Higher / Lower
  8.5 Rebounds Higher 1.05x / Lower 0.86x
  2.5 Assists Higher 1.08x / Lower 0.83x

Terance Mann - BKN @ WAS - 6:00PM CST
  8.5 Points Higher 1.02x / Lower 0.89x
  16.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 1.04x / Lower 0.82x
  3.5 Assists Higher 0.86x / Lower 1.07x

Bub Carrington - WAS vs BKN - 6:00PM CST
  9.5 Points Higher 0.88x / Lower 1.03x
  19.5 Pts + Rebs + Asts Higher 1.05x / Lower 0.94x
  4.5 Rebounds Higher 1.06x / Lower 0.85x
  4.5 Assists Higher 1.05x / Lower 0.87x

Noah Clowney - BKN @ WAS - 6:00PM CST
  17.5 Points Higher / Lower
  24.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.06x / Lower 0.86x
  1.5 Assists Higher 0.79x / Lower 1.07x

Egor Demin - BKN @ WAS - 6:00PM CST
  13.5 Points Higher / Lower
  21.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher / Lower
  3.5 Assists Higher 0.84x / Lower 1.05x

Danny Wolf - BKN @ WAS - 6:00PM CST
  14.5 Points Higher 1.04x / Lower 0.94x
  23.5 Pts + Rebs + Asts Higher / Lower
  6.5 Rebounds Higher 1.09x / Lower 0.83x
  2.5 Assists Higher 0.83x / Lower 1.09x

Khris Middleton - WAS vs BKN - 6:00PM CST
  9.5 Points Higher / Lower
  16.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.05x / Lower 0.87x
  3.5 Assists Higher / Lower

CJ McCollum - WAS vs BKN - 6:00PM CST
  18.5 Points Higher / Lower
  26.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.08x / Lower 0.83x
  3.5 Assists Higher 0.81x / Lower 1.04x

Bilal Coulibaly - WAS vs BKN - 6:00PM CST
  10.5 Points Higher / Lower
  17.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 0.85x / Lower 1.06x
  2.5 Assists Higher 1.07x / Lower 0.84x

Marvin Bagley - WAS vs BKN - 6:00PM CST
  10.5 Points Higher 1.04x / Lower 0.87x
  17.5 Pts + Rebs + Asts Higher / Lower
  6.5 Rebounds Higher 1.05x / Lower 0.85x
  1.5 Assists Higher / Lower

Tre Johnson - WAS vs BKN - 6:00PM CST
  13.5 Points Higher 0.87x / Lower 1.04x
  18.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher 0.79x / Lower 1.08x
  1.5 Assists Higher 0.75x / Lower 1.11x

Justin Champagnie - WAS vs BKN - 6:00PM CST
  8.5 Points Higher 0.88x / Lower 1.03x
  17.5 Pts + Rebs + Asts Higher / Lower
  7.5 Rebounds Higher 1.04x / Lower 0.87x
  1.5 Assists Higher 1.07x / Lower 0.8x

ATL @ NYK
6:30PM CST
Jalen Brunson - NYK vs ATL - 6:30PM CST
  30.5 Points Higher / Lower
  41.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher / Lower
  7.5 Assists Higher / Lower

Jordan Clarkson - NYK vs ATL - 6:30PM CST
  10.5 Points Higher / Lower
  14.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher 1.06x / Lower 0.84x
  1.5 Assists Higher 1.03x / Lower 0.78x

Mikal Bridges - NYK vs ATL - 6:30PM CST
  15.5 Points Higher / Lower
  25.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher / Lower
  4.5 Assists Higher 1.04x / Lower 0.94x

Deuce McBride - NYK vs ATL - 6:30PM CST
  10.5 Points Higher / Lower
  15.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher 0.93x / Lower 1.05x
  2.5 Assists Higher 1.08x / Lower 0.77x

Onyeka Okongwu - ATL @ NYK - 6:30PM CST
  14.5 Points Higher / Lower
  26.5 Pts + Rebs + Asts Higher / Lower
  11.5 Rebounds + Assists Higher / Lower
  22.5 Points + Rebounds Higher / Lower

Karl-Anthony Towns - NYK vs ATL - 6:30PM CST
  38.5 Pts + Rebs + Asts Higher / Lower
  12.5 Rebounds Higher 1.07x / Lower 0.86x
  2.5 Assists Higher 0.77x / Lower 1.05x
  1.5 3-Pointers Made Higher 0.87x / Lower 1.05x

OG Anunoby - NYK vs ATL - 6:30PM CST
  25.5 Pts + Rebs + Asts Higher / Lower
  6.5 Rebounds Higher 1.07x / Lower 0.8x
  2.5 Assists Higher 1.16x / Lower 0.73x
  2.5 3-Pointers Made Higher 1.06x / Lower 0.81x

Jalen Johnson - ATL @ NYK - 6:30PM CST
  43.5 Pts + Rebs + Asts Higher / Lower
  34.5 Points + Rebounds Higher / Lower
  33.5 Points + Assists Higher / Lower
  0.5 Double Doubles Higher 0.65x / Lower 1.43x

Nickeil Alexander-Walker - ATL @ NYK - 6:30PM CST
  20.5 Points Higher / Lower
  26.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.04x / Lower 0.81x
  3.5 3-Pointers Made Higher 1.09x / Lower 0.79x

Tyler Kolek - NYK vs ATL - 6:30PM CST
  5.5 Points Higher / Lower
  12.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher / Lower
  3.5 Assists Higher 0.83x / Lower 1.09x

DEN @ CLE
6:30PM CST
Darius Garland - CLE vs DEN - 6:30PM CST
  17.5 Points Higher / Lower
  28.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.09x / Lower 0.79x
  7.5 Assists Higher 1.05x / Lower 0.81x

Jamal Murray - DEN @ CLE - 6:30PM CST
  27.5 Points Higher / Lower
  39.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher / Lower
  7.5 Assists Higher / Lower

Jarrett Allen - CLE vs DEN - 6:30PM CST
  13.5 Points Higher / Lower
  25.5 Pts + Rebs + Asts Higher / Lower
  8.5 Rebounds Higher 0.88x / Lower 1.04x
  2.5 Assists Higher 1.04x / Lower 0.78x

Bruce Brown - DEN @ CLE - 6:30PM CST
  9.5 Points Higher / Lower
  17.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.06x / Lower 0.86x
  2.5 Assists Higher / Lower

Dean Wade - CLE vs DEN - 6:30PM CST
  6.5 Points Higher 1.05x / Lower 0.94x
  12.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher / Lower
  1.5 Assists Higher / Lower

DaRon Holmes - DEN @ CLE - 6:30PM CST
  12.5 Points Higher 1.03x / Lower 0.88x
  21.5 Pts + Rebs + Asts Higher / Lower
  6.5 Rebounds Higher 1.06x / Lower 0.85x
  2.5 Assists Higher 1.06x / Lower 0.8x

Spencer Jones - DEN @ CLE - 6:30PM CST
  9.5 Points Higher 1.04x / Lower 0.87x
  17.5 Pts + Rebs + Asts Higher 1.05x / Lower 0.94x
  5.5 Rebounds Higher / Lower
  1.5 Assists Higher 0.76x / Lower 1.07x

Donovan Mitchell - CLE vs DEN - 6:30PM CST
  28.5 Points Higher / Lower
  39.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher / Lower
  5.5 Assists Higher 1.05x / Lower 0.94x

Evan Mobley - CLE vs DEN - 6:30PM CST
  16.5 Points Higher / Lower
  29.5 Pts + Rebs + Asts Higher / Lower
  8.5 Rebounds Higher 0.86x / Lower 1.06x
  3.5 Assists Higher 0.87x / Lower 1.05x

De'Andre Hunter - CLE vs DEN - 6:30PM CST
  12.5 Points Higher / Lower
  18.5 Pts + Rebs + Asts Higher 0.94x / Lower 1.05x
  4.5 Rebounds Higher 1.06x / Lower 0.85x
  1.5 Assists Higher / Lower

Tim Hardaway Jr. - DEN @ CLE - 6:30PM CST
  15.5 Points Higher / Lower
  21.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.05x / Lower
  1.5 Assists Higher 0.82x / Lower 1.04x

Peyton Watson - DEN @ CLE - 6:30PM CST
  15.5 Points Higher 1.03x / Lower 0.88x
  22.5 Pts + Rebs + Asts Higher / Lower
  6.5 Rebounds Higher 1.02x / Lower 0.82x
  1.5 Assists Higher 1.21x / Lower 0.72x

Jalen Pickett - DEN @ CLE - 6:30PM CST
  8.5 Points Higher / Lower
  16.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.03x / Lower 0.89x
  4.5 Assists Higher 1.05x / Lower 0.88x

Sam Merrill - CLE vs DEN - 6:30PM CST
  3.5 Rebounds Higher 1.06x / Lower 0.85x

ORL @ CHI
7:00PM CST
Paolo Banchero - ORL @ CHI - 7:00PM CST
  23.5 Points Higher / Lower
  36.5 Pts + Rebs + Asts Higher / Lower
  8.5 Rebounds Higher / Lower
  4.5 Assists Higher 1.06x / Lower 0.77x

Jalen Suggs - ORL @ CHI - 7:00PM CST
  14.5 Points Higher 0.94x / Lower 1.05x
  23.5 Pts + Rebs + Asts Higher 1.05x / Lower 0.94x
  3.5 Rebounds Higher 1.06x / Lower 0.86x
  4.5 Assists Higher 1.07x / Lower 0.84x

Matas Buzelis - CHI vs ORL - 7:00PM CST
  16.5 Points Higher / Lower
  23.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.08x / Lower 0.83x
  1.5 Assists Higher / Lower

Patrick Williams - CHI vs ORL - 7:00PM CST
  8.5 Points Higher / Lower
  13.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.08x / Lower 0.84x
  1.5 Assists Higher / Lower
  1.5 3-Pointers Made Higher 1.11x / Lower 0.75x

Tyus Jones - ORL @ CHI - 7:00PM CST
  5.5 Points Higher 1.06x / Lower 0.86x
  10.5 Pts + Rebs + Asts Higher / Lower
  1.5 Rebounds Higher / Lower
  3.5 Assists Higher 1.05x / Lower 0.87x
  0.5 3-Pointers Made Higher 0.72x / Lower 1.2x

Isaac Okoro - CHI vs ORL - 7:00PM CST
  9.5 Points Higher 1.04x / Lower 0.87x
  14.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.07x / Lower 0.84x
  1.5 Assists Higher 0.77x / Lower 1.09x
  0.5 3-Pointers Made Higher 0.73x / Lower 1.16x

Goga Bitadze - ORL @ CHI - 7:00PM CST
  5.5 Points Higher / Lower
  12.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher / Lower
  1.5 Assists Higher 1.12x / Lower 0.75x

Tristan da Silva - ORL @ CHI - 7:00PM CST
  7.5 Points Higher / Lower
  12.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher / Lower
  1.5 Assists Higher 1.2x / Lower 0.71x
  1.5 3-Pointers Made Higher 1.15x / Lower 0.73x

Desmond Bane - ORL @ CHI - 7:00PM CST
  20.5 Points Higher / Lower
  29.5 Pts + Rebs + Asts Higher 0.94x / Lower 1.04x
  4.5 Rebounds Higher 0.83x / Lower 1.08x
  4.5 Assists Higher / Lower

Nikola Vucevic - CHI vs ORL - 7:00PM CST
  18.5 Points Higher 1.04x / Lower 0.94x
  31.5 Pts + Rebs + Asts Higher / Lower
  9.5 Rebounds Higher 1.05x / Lower 0.86x
  3.5 Assists Higher 0.81x / Lower 1.06x

Wendell Carter Jr. - ORL @ CHI - 7:00PM CST
  12.5 Points Higher / Lower
  22.5 Pts + Rebs + Asts Higher / Lower
  8.5 Rebounds Higher 1.05x / Lower 0.88x
  1.5 Assists Higher 0.78x / Lower 1.03x

Tre Jones - CHI vs ORL - 7:00PM CST
  13.5 Points Higher / Lower
  24.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.04x / Lower 0.87x
  7.5 Assists Higher 1.06x / Lower 0.86x

Ayo Dosunmu - CHI vs ORL - 7:00PM CST
  14.5 Points Higher 1.03x / Lower 0.88x
  21.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher 0.77x / Lower 1.05x
  4.5 Assists Higher 1.08x / Lower 0.83x

Anthony Black - ORL @ CHI - 7:00PM CST
  17.5 Points Higher / Lower
  25.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 1.03x / Lower 0.82x
  3.5 Assists Higher 0.82x / Lower 1.03x

Kevin Huerter - CHI vs ORL - 7:00PM CST
  13.5 Points Higher / Lower
  20.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 0.86x / Lower 1.06x
  2.5 Assists Higher 0.87x / Lower 1.06x

Jalen Smith - CHI vs ORL - 7:00PM CST
  11.5 Points Higher / Lower
  23.5 Pts + Rebs + Asts Higher / Lower
  8.5 Rebounds Higher / Lower
  2.5 Assists Higher 1.09x / Lower 0.76x

CHA @ MIL
7:00PM CST
Giannis Antetokounmpo - MIL vs CHA - 7:00PM CST
  28.5 Points Higher / Lower
  45.5 Pts + Rebs + Asts Higher 1.04x / Lower 0.94x
  9.5 Rebounds Higher 0.85x / Lower 1.07x
  5.5 Assists Higher 0.84x / Lower 1.07x

Kyle Kuzma - MIL vs CHA - 7:00PM CST
  10.5 Points Higher / Lower
  17.5 Pts + Rebs + Asts Higher 1.08x / Lower 0.83x
  4.5 Rebounds Higher 1.03x / Lower 0.88x
  2.5 Assists Higher 1.1x / Lower 0.79x

Myles Turner - MIL vs CHA - 7:00PM CST
  12.5 Points Higher 1.04x / Lower 0.94x
  18.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.07x / Lower 0.84x
  1.5 Assists Higher 1.03x / Lower 0.78x

Gary Trent Jr. - MIL vs CHA - 7:00PM CST
  5.5 Points Higher / Lower
  1.5 Rebounds Higher 1.2x / Lower 0.72x
  1.5 3-Pointers Made Higher 1.12x / Lower 0.75x

Collin Sexton - CHA @ MIL - 7:00PM CST
  12.5 Points Higher / Lower
  17.5 Pts + Rebs + Asts Higher / Lower
  1.5 Rebounds Higher / Lower
  3.5 Assists Higher 1.02x / Lower 0.87x
  1.5 3-Pointers Made Higher 1.24x / Lower 0.7x

Ryan Rollins - MIL vs CHA - 7:00PM CST
  14.5 Points Higher / Lower
  24.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 1.08x / Lower 0.83x
  5.5 Assists Higher 1.05x / Lower 0.84x

AJ Green - MIL vs CHA - 7:00PM CST
  9.5 Points Higher 1.03x / Lower 0.88x
  13.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher 1.07x / Lower 0.84x
  1.5 Assists Higher 0.8x / Lower 1.05x

Moussa Diabate - CHA @ MIL - 7:00PM CST
  8.5 Points Higher / Lower
  21.5 Pts + Rebs + Asts Higher / Lower
  11.5 Rebounds Higher / Lower
  1.5 Assists Higher 1.06x / Lower 0.84x

LaMelo Ball - CHA @ MIL - 7:00PM CST
  20.5 Points Higher / Lower
  32.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher / Lower
  7.5 Assists Higher / Lower

Miles Bridges - CHA @ MIL - 7:00PM CST
  16.5 Points Higher / Lower
  26.5 Pts + Rebs + Asts Higher / Lower
  6.5 Rebounds Higher 1.07x / Lower 0.86x
  3.5 Assists Higher 1.04x / Lower 0.81x

Brandon Miller - CHA @ MIL - 7:00PM CST
  19.5 Points Higher / Lower
  26.5 Pts + Rebs + Asts Higher 0.94x / Lower 1.05x
  4.5 Rebounds Higher 1.07x / Lower 0.85x
  2.5 Assists Higher 0.82x / Lower 1.03x

Bobby Portis - MIL vs CHA - 7:00PM CST
  11.5 Points Higher 0.89x / Lower 1.02x
  19.5 Pts + Rebs + Asts Higher / Lower
  6.5 Rebounds Higher 1.08x / Lower 0.83x
  1.5 Assists Higher 1.08x / Lower 0.79x

Kon Knueppel - CHA @ MIL - 7:00PM CST
  17.5 Points Higher / Lower
  25.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 1.08x / Lower 0.83x
  3.5 Assists Higher 1.09x / Lower 0.79x

Kevin Porter Jr. - MIL vs CHA - 7:00PM CST
  19.5 Points Higher 1.03x / Lower 0.88x
  32.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.07x / Lower 0.84x
  7.5 Assists Higher / Lower

Sion James - CHA @ MIL - 7:00PM CST
  4.5 Points Higher 0.89x / Lower 1.05x
  9.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher 0.83x / Lower 1.07x
  1.5 Assists Higher 1.05x / Lower 0.85x
  0.5 3-Pointers Made Higher 0.83x / Lower 1.09x

POR @ NOP
7:00PM CST
Zion Williamson - NOP vs POR - 7:00PM CST
  26.5 Points Higher / Lower
  36.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 0.83x / Lower 1.08x
  3.5 Assists Higher 0.79x / Lower 1.08x

Deni Avdija - POR @ NOP - 7:00PM CST
  26.5 Points Higher / Lower
  43.5 Pts + Rebs + Asts Higher / Lower
  7.5 Rebounds Higher 0.84x / Lower 1.05x
  8.5 Assists Higher / Lower

Trey Murphy III - NOP vs POR - 7:00PM CST
  21.5 Points Higher / Lower
  30.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.03x / Lower 0.88x
  3.5 Assists Higher / Lower

Robert Williams - POR @ NOP - 7:00PM CST
  7.5 Points Higher / Lower
  15.5 Pts + Rebs + Asts Higher / Lower
  7.5 Rebounds Higher 1.05x / Lower 0.88x
  8.5 Rebounds + Assists Higher 1.04x / Lower 0.88x

Caleb Love - POR @ NOP - 7:00PM CST
  14.5 Points Higher / Lower
  22.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 0.82x / Lower 1.04x
  3.5 Assists Higher 1.04x / Lower 0.88x

Kris Murray - POR @ NOP - 7:00PM CST
  6.5 Points Higher 0.88x / Lower 1.03x
  13.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher / Lower
  1.5 Assists Higher 1.02x / Lower 0.93x
  0.5 3-Pointers Made Higher 0.85x / Lower 1.05x

Jordan Poole - NOP vs POR - 7:00PM CST
  18.5 Points Higher / Lower
  25.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher / Lower
  3.5 3-Pointers Made Higher 1.2x / Lower 0.72x

Shaedon Sharpe - POR @ NOP - 7:00PM CST
  24.5 Points Higher / Lower
  32.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 0.83x / Lower 1.08x
  3.5 Assists Higher 1.03x / Lower 0.78x

Donovan Clingan - POR @ NOP - 7:00PM CST
  11.5 Points Higher 0.88x / Lower 1.03x
  25.5 Pts + Rebs + Asts Higher / Lower
  11.5 Rebounds Higher / Lower
  1.5 Assists Higher 0.81x / Lower 1.05x

Toumani Camara - POR @ NOP - 7:00PM CST
  14.5 Points Higher / Lower
  23.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher / Lower
  3.5 Assists Higher 1.05x / Lower 0.86x

Jeremiah Fears - NOP vs POR - 7:00PM CST
  15.5 Points Higher / Lower
  22.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 0.86x / Lower 1.06x
  3.5 Assists Higher / Lower

SAC @ PHX
8:00PM CST
Devin Booker - PHX vs SAC - 8:00PM CST
  25.5 Points Higher / Lower
  36.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 0.83x / Lower 1.09x
  6.5 Assists Higher 1.04x / Lower 0.88x

Keegan Murray - SAC @ PHX - 8:00PM CST
  14.5 Points Higher / Lower
  22.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.07x / Lower 0.84x
  1.5 Assists Higher / Lower

Russell Westbrook - SAC @ PHX - 8:00PM CST
  13.5 Points Higher / Lower
  24.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.06x / Lower 0.85x
  6.5 Assists Higher 1.08x / Lower 0.79x

Grayson Allen - PHX vs SAC - 8:00PM CST
  12.5 Points Higher / Lower
  18.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher / Lower
  3.5 Assists Higher 1.04x / Lower 0.78x

Royce O'Neale - PHX vs SAC - 8:00PM CST
  9.5 Points Higher / Lower
  16.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 1.05x / Lower 0.87x
  2.5 Assists Higher / Lower

Jordan Goodwin - PHX vs SAC - 8:00PM CST
  8.5 Points Higher / Lower
  15.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 1.03x / Lower 0.88x
  2.5 Assists Higher 1.07x / Lower 0.8x

Collin Gillespie - PHX vs SAC - 8:00PM CST
  14.5 Points Higher / Lower
  24.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 1.03x / Lower 0.82x
  5.5 Assists Higher 1.05x / Lower 0.87x

DeMar DeRozan - SAC @ PHX - 8:00PM CST
  18.5 Points Higher / Lower
  26.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 0.82x / Lower 1.03x
  3.5 Assists Higher 0.85x / Lower 1.05x

Dillon Brooks - PHX vs SAC - 8:00PM CST
  20.5 Points Higher / Lower
  25.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.03x / Lower 0.82x
  1.5 Assists Higher 0.76x / Lower 1.08x

Dennis Schroder - SAC @ PHX - 8:00PM CST
  11.5 Points Higher / Lower
  19.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher 1.02x / Lower 0.89x
  5.5 Assists Higher 1.09x / Lower 0.83x

Mark Williams - PHX vs SAC - 8:00PM CST
  13.5 Points Higher / Lower
  24.5 Pts + Rebs + Asts Higher 1.03x / Lower 0.88x
  9.5 Rebounds Higher / Lower
  1.5 Assists Higher 1.07x / Lower 0.77x

Keon Ellis - SAC @ PHX - 8:00PM CST
  5.5 Points Higher / Lower
  1.5 Rebounds Higher 0.94x / Lower 1.04x
  1.5 3-Pointers Made Higher 1.06x / Lower 0.77x

Precious Achiuwa - SAC @ PHX - 8:00PM CST
  5.5 Points Higher 0.88x / Lower 1.03x
  12.5 Pts + Rebs + Asts Higher 1.02x / Lower 0.88x
  4.5 Rebounds Higher 1.06x / Lower 0.85x
  0.5 3-Pointers Made Higher 1.3x / Lower 0.67x
  1.5 1Q Rebounds Higher / Lower

Maxime Raynaud - SAC @ PHX - 8:00PM CST
  13.5 Points Higher / Lower
  23.5 Pts + Rebs + Asts Higher / Lower
  8.5 Rebounds Higher / Lower
  1.5 Assists Higher 1.07x / Lower 0.85x

OKC @ GSW
9:00PM CST
Stephen Curry - GSW vs OKC - 9:00PM CST
  25.5 Points Higher / Lower
  34.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 1.04x / Lower 0.82x
  4.5 Assists Higher 1.06x / Lower 0.84x

Jimmy Butler - GSW vs OKC - 9:00PM CST
  18.5 Points Higher / Lower
  29.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher / Lower
  4.5 Assists Higher 0.83x / Lower 1.08x

Chet Holmgren - OKC @ GSW - 9:00PM CST
  18.5 Points Higher / Lower
  28.5 Pts + Rebs + Asts Higher 0.94x / Lower 1.04x
  9.5 Rebounds Higher 1.03x / Lower 0.87x
  1.5 Assists Higher 1.04x / Lower 0.78x

Alex Caruso - OKC @ GSW - 9:00PM CST
  5.5 Points Higher / Lower
  9.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher 0.87x / Lower 1.06x
  1.5 Assists Higher 1.04x / Lower 0.94x
  0.5 3-Pointers Made Higher 0.79x / Lower 1.09x

Al Horford - GSW vs OKC - 9:00PM CST
  7.5 Points Higher 1.06x / Lower 0.86x
  13.5 Pts + Rebs + Asts Higher 0.89x / Lower 1.02x
  5.5 Rebounds Higher 1.06x / Lower 0.85x
  1.5 Assists Higher 0.8x / Lower 1.06x

Aaron Wiggins - OKC @ GSW - 9:00PM CST
  7.5 Points Higher / Lower
  10.5 Pts + Rebs + Asts Higher / Lower
  2.5 Rebounds Higher / Lower
  1.5 Assists Higher 1.23x / Lower 0.71x
  0.5 3-Pointers Made Higher 0.72x / Lower 1.18x

Quinten Post - GSW vs OKC - 9:00PM CST
  8.5 Points Higher / Lower
  14.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.05x / Lower 0.81x
  1.5 Assists Higher 1.05x / Lower 0.85x

Moses Moody - GSW vs OKC - 9:00PM CST
  9.5 Points Higher / Lower
  15.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.06x / Lower 0.84x
  1.5 Assists Higher 1.07x / Lower 0.85x

Shai Gilgeous-Alexander - OKC @ GSW - 9:00PM CST
  31.5 Points Higher 1.03x / Lower 0.88x
  42.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.04x / Lower 0.82x
  6.5 Assists Higher 1.06x / Lower 0.85x

Jalen Williams - OKC @ GSW - 9:00PM CST
  18.5 Points Higher / Lower
  29.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 1.06x / Lower 0.86x
  4.5 Assists Higher 0.82x / Lower 1.03x

Brandin Podziemski - GSW vs OKC - 9:00PM CST
  11.5 Points Higher / Lower
  18.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 1.06x / Lower 0.8x
  2.5 Assists Higher 0.82x / Lower 1.02x

Lu Dort - OKC @ GSW - 9:00PM CST
  6.5 Points Higher 0.87x / Lower 1.04x
  11.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.03x / Lower 0.88x
  1.5 3-Pointers Made Higher / Lower

Cason Wallace - OKC @ GSW - 9:00PM CST
  8.5 Points Higher 1.03x / Lower 0.88x
  13.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 1.08x / Lower 0.76x
  2.5 Assists Higher 1.08x / Lower 0.76x

Isaiah Joe - OKC @ GSW - 9:00PM CST
  5.5 Points Higher 1.02x / Lower 0.89x
  1.5 Rebounds Higher 0.79x / Lower 1.09x
  1.5 3-Pointers Made Higher 1.04x / Lower 0.78x

Ajay Mitchell - OKC @ GSW - 9:00PM CST
  11.5 Points Higher 1.05x / Lower 0.94x
  17.5 Pts + Rebs + Asts Higher 0.88x / Lower 1.03x
  3.5 Rebounds Higher 1.06x / Lower 0.86x
  2.5 Assists Higher 0.78x / Lower 1.03x

MEM @ LAL
9:30PM CST
LeBron James - LAL vs MEM - 9:30PM CST
  23.5 Points Higher / Lower 0.94x
  36.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher 0.83x / Lower 1.08x
  6.5 Assists Higher 1.06x / Lower 0.84x

Ja Morant - MEM @ LAL - 9:30PM CST
  8.5 Assists Higher 1.05x / Lower 0.81x
  1.5 3-Pointers Made Higher 1.02x / Lower 0.82x
  0.5 Double Doubles Higher 1.24x / Lower 0.68x
  3.5 Turnovers Higher 1.05x / Lower 0.85x

Deandre Ayton - LAL vs MEM - 9:30PM CST
  13.5 Points Higher / Lower
  23.5 Pts + Rebs + Asts Higher / Lower
  9.5 Rebounds Higher 1.06x / Lower 0.86x
  9.5 Rebounds + Assists Higher 0.85x / Lower 1.05x

Jaren Jackson Jr. - MEM @ LAL - 9:30PM CST
  19.5 Points Higher / Lower
  27.5 Pts + Rebs + Asts Higher / Lower
  6.5 Rebounds Higher 1.05x / Lower 0.85x
  7.5 Rebounds + Assists Higher 0.85x / Lower 1.06x

Jake LaRavia - LAL vs MEM - 9:30PM CST
  10.5 Points Higher / Lower
  17.5 Pts + Rebs + Asts Higher / Lower
  4.5 Rebounds Higher 0.84x / Lower 1.06x
  1.5 Assists Higher 0.8x / Lower 1.06x

Jaxson Hayes - LAL vs MEM - 9:30PM CST
  5.5 Points Higher / Lower
  9.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher / Lower

Luka Doncic - LAL vs MEM - 9:30PM CST
  35.5 Points Higher / Lower
  52.5 Pts + Rebs + Asts Higher / Lower
  8.5 Rebounds Higher 1.03x / Lower 0.88x
  8.5 Assists Higher 0.94x / Lower 1.04x

Marcus Smart - LAL vs MEM - 9:30PM CST
  9.5 Points Higher / Lower
  15.5 Pts + Rebs + Asts Higher 0.94x / Lower 1.04x
  2.5 Rebounds Higher / Lower
  3.5 Assists Higher 1.05x / Lower 0.78x

Jarred Vanderbilt - LAL vs MEM - 9:30PM CST
  5.5 Points Higher / Lower
  13.5 Pts + Rebs + Asts Higher / Lower
  5.5 Rebounds Higher / Lower
  1.5 Assists Higher 1.08x / Lower 0.76x

Santi Aldama - MEM @ LAL - 9:30PM CST
  14.5 Points Higher / Lower
  24.5 Pts + Rebs + Asts Higher / Lower
  7.5 Rebounds Higher 1.04x / Lower 0.86x
  2.5 Assists Higher 0.84x / Lower 1.06x

Jaylen Wells - MEM @ LAL - 9:30PM CST
  12.5 Points Higher / Lower
  18.5 Pts + Rebs + Asts Higher / Lower
  3.5 Rebounds Higher 0.88x / Lower 1.04x
  1.5 Assists Higher 0.86x / Lower 1.06x

Cedric Coward - MEM @ LAL - 9:30PM CST
  3.5 Assists Higher 1.09x / Lower 0.79x
  0.5 Double Doubles Higher 3.43x
"""

def parse_player_props(text):
    """Parse Underdog text format into structured picks."""
    picks = []
    
    # Split by game header (uppercase with @ or vs)
    game_pattern = r'^([A-Z]{3})\s+(@|vs)\s+([A-Z]{3})\s+(\d{1,2}:\d{2}[AP]M)\s+([A-Z]+)$'
    lines = text.strip().split('\n')
    
    current_game = None
    current_player = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if it's a game header
        if '@' in line and ':' in line and any(t in line for t in ['CST', 'EST', 'PST']):
            parts = line.split()
            if len(parts) >= 4:
                team1, _, team2, time = parts[0], parts[1], parts[2], parts[3]
                current_game = {
                    'teams': (team1, team2),
                    'time': time,
                    'symbol': parts[1]
                }
        # Check if it's a player line (player - team - game info)
        elif ' - ' in line and ':' in line:
            parts = line.split(' - ')
            if len(parts) >= 2:
                player_name = parts[0].strip()
                game_info = ' - '.join(parts[1:])
                current_player = {
                    'name': player_name,
                    'game_info': game_info
                }
        # Check if it's a prop line
        elif current_player and current_game:
            # Parse prop line: "16.5 Points Higher / Lower"
            prop_match = re.match(r'(\d+\.?\d*)\s+(.+?)\s+(Higher|Lower)(?:\s+(\d+\.?\d*)x)?(?:\s+/\s+(Higher|Lower))?(?:\s+(\d+\.?\d*)x)?', line)
            if prop_match:
                line_val = float(prop_match.group(1))
                stat = prop_match.group(2).strip()
                direction1 = prop_match.group(3)
                mult1 = float(prop_match.group(4)) if prop_match.group(4) else None
                direction2 = prop_match.group(5)
                mult2 = float(prop_match.group(6)) if prop_match.group(6) else None
                
                # Normalize stat names
                stat = normalize_stat(stat)
                
                # Extract team from game_info (e.g., "WAS vs BKN - 6:00PM CST" -> "WAS")
                team_match = re.search(r'^([A-Z]{3})', current_player['game_info'])
                player_team = team_match.group(1) if team_match else ""
                
                # Create pick for "higher"
                pick = {
                    'player': current_player['name'],
                    'team': player_team,
                    'stat': stat,
                    'line': line_val,
                    'direction': 'higher'
                }
                picks.append(pick)
                
                # Create pick for "lower" if available
                if direction2:
                    pick_lower = {
                        'player': current_player['name'],
                        'team': player_team,
                        'stat': stat,
                        'line': line_val,
                        'direction': 'lower'
                    }
                    picks.append(pick_lower)
    
    return picks

def normalize_stat(stat):
    """Normalize stat names to match system conventions."""
    stat = stat.lower().strip()
    
    # Combo stats
    if 'pts' in stat and 'reb' in stat and 'ast' in stat:
        return 'pts+reb+ast'
    if 'points' in stat and 'rebounds' in stat and 'assists' in stat:
        return 'pts+reb+ast'
    if 'pts+reb' in stat:
        return 'pts+reb'
    if 'points+rebounds' in stat:
        return 'pts+reb'
    if 'pts+ast' in stat:
        return 'pts+ast'
    if 'points+assists' in stat:
        return 'pts+ast'
    if 'reb+ast' in stat or 'rebounds+assists' in stat:
        return 'reb+ast'
    
    # Single stats
    stat_map = {
        'points': 'points',
        'pts': 'points',
        'rebounds': 'rebounds',
        'reb': 'rebounds',
        'assists': 'assists',
        'ast': 'assists',
        '3pm': '3pm',
        '3-pointers made': '3pm',
        'three-pointers made': '3pm',
        'fg3m': '3pm',
        'steals': 'steals',
        'blocks': 'blocks',
        'turnovers': 'turnovers',
        'double doubles': 'double_doubles',
        '1q rebounds': '1q_rebounds'
    }
    
    for key, value in stat_map.items():
        if key in stat:
            return value
    
    return stat

# Parse the provided data
picks = parse_player_props(data)

print(f"Parsed {len(picks)} picks")
for i, pick in enumerate(picks[:10]):
    print(f"{i+1}. {pick['player']} ({pick['team']}) - {pick['stat']} {pick['line']} {pick['direction']}")

# Load existing picks if available
picks_file = Path("picks.json")
existing_picks = []
if picks_file.exists():
    with open(picks_file) as f:
        existing_picks = json.load(f)

# Merge (replace today's data)
today_date = datetime.now().strftime("%Y-%m-%d")
other_picks = [p for p in existing_picks if p.get('date') != today_date and 'date' in p]
all_picks = other_picks + picks

# Save
with open(picks_file, 'w') as f:
    json.dump(all_picks, f, indent=2)

print(f"\nWrote {len(all_picks)} total picks to {picks_file}")

# Auto-update roster knowledge from picks.json (source of truth)
print("\n🔄 Auto-updating roster knowledge base from picks.json...")
try:
    from scripts.auto_update_roster_kb import update_local_validator
    player_count = update_local_validator()
    print(f"✅ LocalValidator updated with {player_count} current players")
except Exception as e:
    print(f"⚠️  Could not auto-update roster: {e}")
    print("   (This is optional - you can still update manually)")
