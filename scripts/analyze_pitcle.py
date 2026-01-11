"""
PIT @ CLE - Sunday December 28, 2025 - 12:00 PM CST
Full Props Analysis with Yes/No Recommendations
"""
from collections import defaultdict

# All props from the game
picks = []

# JAYLEN WARREN (PIT RB)
picks.extend([
    {'player': 'Jaylen Warren', 'team': 'PIT', 'pos': 'RB', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.12, 'lower_mult': 0.74},
    {'player': 'Jaylen Warren', 'team': 'PIT', 'pos': 'RB', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 3.32, 'lower_mult': None},
    {'player': 'Jaylen Warren', 'team': 'PIT', 'pos': 'RB', 'stat': '1Q Rush+Rec TDs', 'line': 0.5, 'higher_mult': 4.30, 'lower_mult': None},
    {'player': 'Jaylen Warren', 'team': 'PIT', 'pos': 'RB', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.98, 'lower_mult': None},
])

# KENNETH GAINWELL (PIT RB)
picks.extend([
    {'player': 'Kenneth Gainwell', 'team': 'PIT', 'pos': 'RB', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.23, 'lower_mult': 0.71},
    {'player': 'Kenneth Gainwell', 'team': 'PIT', 'pos': 'RB', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 3.75, 'lower_mult': None},
    {'player': 'Kenneth Gainwell', 'team': 'PIT', 'pos': 'RB', 'stat': '1Q Rush+Rec TDs', 'line': 0.5, 'higher_mult': 4.38, 'lower_mult': None},
    {'player': 'Kenneth Gainwell', 'team': 'PIT', 'pos': 'RB', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.12, 'lower_mult': None},
])

# KALEB JOHNSON (PIT)
picks.extend([
    {'player': 'Kaleb Johnson', 'team': 'PIT', 'pos': 'RB', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 4.16, 'lower_mult': None},
    {'player': 'Kaleb Johnson', 'team': 'PIT', 'pos': 'RB', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 14.01, 'lower_mult': None},
    {'player': 'Kaleb Johnson', 'team': 'PIT', 'pos': 'RB', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 9.55, 'lower_mult': None},
])

# DYLAN SAMPSON (CLE RB)
picks.extend([
    {'player': 'Dylan Sampson', 'team': 'CLE', 'pos': 'RB', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.10, 'lower_mult': 0.75},
    {'player': 'Dylan Sampson', 'team': 'CLE', 'pos': 'RB', 'stat': 'Rush Yards', 'line': 42.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Dylan Sampson', 'team': 'CLE', 'pos': 'RB', 'stat': 'Receiving Yards', 'line': 17.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Dylan Sampson', 'team': 'CLE', 'pos': 'RB', 'stat': 'Receptions', 'line': 2.5, 'higher_mult': 0.86, 'lower_mult': 1.06},
])

# AARON RODGERS (PIT QB)
picks.extend([
    {'player': 'Aaron Rodgers', 'team': 'PIT', 'pos': 'QB', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 12.29, 'lower_mult': None},
    {'player': 'Aaron Rodgers', 'team': 'PIT', 'pos': 'QB', 'stat': 'Pass Yards', 'line': 183.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Aaron Rodgers', 'team': 'PIT', 'pos': 'QB', 'stat': 'Pass TDs', 'line': 1.5, 'higher_mult': 1.34, 'lower_mult': 0.68},
    {'player': 'Aaron Rodgers', 'team': 'PIT', 'pos': 'QB', 'stat': 'Rush Yards', 'line': 0.5, 'higher_mult': 1.08, 'lower_mult': 0.80},
    {'player': 'Aaron Rodgers', 'team': 'PIT', 'pos': 'QB', 'stat': 'Rush Attempts', 'line': 1.5, 'higher_mult': 1.04, 'lower_mult': 0.87},
    {'player': 'Aaron Rodgers', 'team': 'PIT', 'pos': 'QB', 'stat': 'INTs Thrown', 'line': 0.5, 'higher_mult': 1.05, 'lower_mult': 0.81},
    {'player': 'Aaron Rodgers', 'team': 'PIT', 'pos': 'QB', 'stat': 'Fantasy Points', 'line': 11.85, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Aaron Rodgers', 'team': 'PIT', 'pos': 'QB', 'stat': '1Q Pass TDs', 'line': 0.5, 'higher_mult': 1.80, 'lower_mult': 0.60},
    {'player': 'Aaron Rodgers', 'team': 'PIT', 'pos': 'QB', 'stat': '1H Pass TDs', 'line': 0.5, 'higher_mult': 1.09, 'lower_mult': 0.84},
    {'player': 'Aaron Rodgers', 'team': 'PIT', 'pos': 'QB', 'stat': 'Fumbles Lost', 'line': 0.5, 'higher_mult': 1.61, 'lower_mult': 0.62},
])

# SHEDEUR SANDERS (CLE QB)
picks.extend([
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.47, 'lower_mult': None},
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': 'Pass Yards', 'line': 178.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': 'Pass TDs', 'line': 0.5, 'higher_mult': 0.81, 'lower_mult': 1.04},
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': 'Rush Yards', 'line': 12.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': 'Rush Attempts', 'line': 2.5, 'higher_mult': 0.83, 'lower_mult': 1.02},
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': 'INTs Thrown', 'line': 0.5, 'higher_mult': 0.75, 'lower_mult': 1.13},
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': 'Fantasy Points', 'line': 10.95, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': '1Q Pass TDs', 'line': 0.5, 'higher_mult': 2.76, 'lower_mult': None},
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': '1H Pass TDs', 'line': 0.5, 'higher_mult': 1.30, 'lower_mult': 0.68},
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': 'Fumbles Lost', 'line': 0.5, 'higher_mult': 1.54, 'lower_mult': 0.63},
    {'player': 'Shedeur Sanders', 'team': 'CLE', 'pos': 'QB', 'stat': '1Q Rush Yards', 'line': 0.5, 'higher_mult': 1.10, 'lower_mult': 0.76},
])

# JONNU SMITH (PIT TE)
picks.extend([
    {'player': 'Jonnu Smith', 'team': 'PIT', 'pos': 'TE', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.12, 'lower_mult': None},
    {'player': 'Jonnu Smith', 'team': 'PIT', 'pos': 'TE', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 12.29, 'lower_mult': None},
    {'player': 'Jonnu Smith', 'team': 'PIT', 'pos': 'TE', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 6.91, 'lower_mult': None},
])

# PAT FREIERMUTH (PIT TE)
picks.extend([
    {'player': 'Pat Freiermuth', 'team': 'PIT', 'pos': 'TE', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.82, 'lower_mult': None},
    {'player': 'Pat Freiermuth', 'team': 'PIT', 'pos': 'TE', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 9.57, 'lower_mult': None},
    {'player': 'Pat Freiermuth', 'team': 'PIT', 'pos': 'TE', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 5.75, 'lower_mult': None},
])

# HAROLD FANNIN (CLE TE)
picks.extend([
    {'player': 'Harold Fannin', 'team': 'CLE', 'pos': 'TE', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 1.47, 'lower_mult': 0.64},
    {'player': 'Harold Fannin', 'team': 'CLE', 'pos': 'TE', 'stat': 'Receiving Yards', 'line': 52.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Harold Fannin', 'team': 'CLE', 'pos': 'TE', 'stat': 'Receptions', 'line': 5.5, 'higher_mult': 1.07, 'lower_mult': 0.84},
    {'player': 'Harold Fannin', 'team': 'CLE', 'pos': 'TE', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 5.04, 'lower_mult': None},
    {'player': 'Harold Fannin', 'team': 'CLE', 'pos': 'TE', 'stat': '1Q Receptions', 'line': 1.5, 'higher_mult': 1.21, 'lower_mult': 0.72},
    {'player': 'Harold Fannin', 'team': 'CLE', 'pos': 'TE', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.99, 'lower_mult': None},
])

# JERRY JEUDY (CLE WR)
picks.extend([
    {'player': 'Jerry Jeudy', 'team': 'CLE', 'pos': 'WR', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.65, 'lower_mult': None},
    {'player': 'Jerry Jeudy', 'team': 'CLE', 'pos': 'WR', 'stat': 'Receiving Yards', 'line': 27.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Jerry Jeudy', 'team': 'CLE', 'pos': 'WR', 'stat': 'Receptions', 'line': 2.5, 'higher_mult': 1.03, 'lower_mult': 0.88},
])

# ADAM THIELEN (PIT WR)
picks.extend([
    {'player': 'Adam Thielen', 'team': 'PIT', 'pos': 'WR', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.27, 'lower_mult': None},
    {'player': 'Adam Thielen', 'team': 'PIT', 'pos': 'WR', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 8.16, 'lower_mult': None},
    {'player': 'Adam Thielen', 'team': 'PIT', 'pos': 'WR', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 4.34, 'lower_mult': None},
])

# ROMAN WILSON (PIT WR)
picks.extend([
    {'player': 'Roman Wilson', 'team': 'PIT', 'pos': 'WR', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 6.03, 'lower_mult': None},
    {'player': 'Roman Wilson', 'team': 'PIT', 'pos': 'WR', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 13.14, 'lower_mult': None},
])

# MVS (PIT WR)
picks.extend([
    {'player': 'Marquez Valdes-Scantling', 'team': 'PIT', 'pos': 'WR', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.36, 'lower_mult': None},
    {'player': 'Marquez Valdes-Scantling', 'team': 'PIT', 'pos': 'WR', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 8.18, 'lower_mult': None},
    {'player': 'Marquez Valdes-Scantling', 'team': 'PIT', 'pos': 'WR', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 4.62, 'lower_mult': None},
])

# ISAIAH BOND (CLE WR)
picks.extend([
    {'player': 'Isaiah Bond', 'team': 'CLE', 'pos': 'WR', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 3.72, 'lower_mult': None},
    {'player': 'Isaiah Bond', 'team': 'CLE', 'pos': 'WR', 'stat': 'Receiving Yards', 'line': 10.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Isaiah Bond', 'team': 'CLE', 'pos': 'WR', 'stat': 'Receptions', 'line': 1.5, 'higher_mult': 1.28, 'lower_mult': 0.70},
    {'player': 'Isaiah Bond', 'team': 'CLE', 'pos': 'WR', 'stat': '1Q Rec Yards', 'line': 0.5, 'higher_mult': 1.73, 'lower_mult': 0.61},
    {'player': 'Isaiah Bond', 'team': 'CLE', 'pos': 'WR', 'stat': '1Q Receptions', 'line': 0.5, 'higher_mult': 1.68, 'lower_mult': 0.61},
    {'player': 'Isaiah Bond', 'team': 'CLE', 'pos': 'WR', 'stat': '1H Rec Yards', 'line': 0.5, 'higher_mult': 1.05, 'lower_mult': 0.81},
    {'player': 'Isaiah Bond', 'team': 'CLE', 'pos': 'WR', 'stat': '1H Receptions', 'line': 0.5, 'higher_mult': 1.02, 'lower_mult': 0.82},
])

# CEDRIC TILLMAN (CLE WR)
picks.extend([
    {'player': 'Cedric Tillman', 'team': 'CLE', 'pos': 'WR', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 5.81, 'lower_mult': None},
    {'player': 'Cedric Tillman', 'team': 'CLE', 'pos': 'WR', 'stat': 'Receiving Yards', 'line': 11.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Cedric Tillman', 'team': 'CLE', 'pos': 'WR', 'stat': 'Receptions', 'line': 1.5, 'higher_mult': 1.03, 'lower_mult': 0.78},
])

# MALACHI CORLEY (CLE WR)
picks.extend([
    {'player': 'Malachi Corley', 'team': 'CLE', 'pos': 'WR', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.92, 'lower_mult': None},
    {'player': 'Malachi Corley', 'team': 'CLE', 'pos': 'WR', 'stat': 'Receiving Yards', 'line': 12.5, 'higher_mult': 1.0, 'lower_mult': 1.0},
    {'player': 'Malachi Corley', 'team': 'CLE', 'pos': 'WR', 'stat': '1Q Rec Yards', 'line': 0.5, 'higher_mult': 1.30, 'lower_mult': 0.67},
    {'player': 'Malachi Corley', 'team': 'CLE', 'pos': 'WR', 'stat': '1Q Receptions', 'line': 0.5, 'higher_mult': 1.36, 'lower_mult': 0.68},
    {'player': 'Malachi Corley', 'team': 'CLE', 'pos': 'WR', 'stat': '1H Receptions', 'line': 0.5, 'higher_mult': 0.82, 'lower_mult': 1.04},
])

# DARNELL WASHINGTON (PIT TE)
picks.extend([
    {'player': 'Darnell Washington', 'team': 'PIT', 'pos': 'TE', 'stat': 'Rush+Rec TDs', 'line': 0.5, 'higher_mult': 2.47, 'lower_mult': None},
    {'player': 'Darnell Washington', 'team': 'PIT', 'pos': 'TE', 'stat': 'First TD Scorer', 'line': 0.5, 'higher_mult': 9.16, 'lower_mult': None},
    {'player': 'Darnell Washington', 'team': 'PIT', 'pos': 'TE', 'stat': '1H Rush+Rec TDs', 'line': 0.5, 'higher_mult': 4.74, 'lower_mult': None},
])

# KICKERS
picks.extend([
    {'player': 'Chris Boswell', 'team': 'PIT', 'pos': 'K', 'stat': 'FG Made', 'line': 1.5, 'higher_mult': 0.76, 'lower_mult': 1.09},
    {'player': 'Chris Boswell', 'team': 'PIT', 'pos': 'K', 'stat': 'XP Made', 'line': 1.5, 'higher_mult': 0.85, 'lower_mult': 1.05},
    {'player': 'Chris Boswell', 'team': 'PIT', 'pos': 'K', 'stat': '1st XP Made', 'line': 0.5, 'higher_mult': 0.86, 'lower_mult': None},
    {'player': 'Andre Szmyt', 'team': 'CLE', 'pos': 'K', 'stat': 'FG Made', 'line': 1.5, 'higher_mult': 1.05, 'lower_mult': 0.82},
    {'player': 'Andre Szmyt', 'team': 'CLE', 'pos': 'K', 'stat': 'XP Made', 'line': 1.5, 'higher_mult': 1.07, 'lower_mult': 0.84},
    {'player': 'Andre Szmyt', 'team': 'CLE', 'pos': 'K', 'stat': '1st XP Made', 'line': 0.5, 'higher_mult': 1.06, 'lower_mult': None},
])

# DEFENSE - MYLES GARRETT
picks.extend([
    {'player': 'Myles Garrett', 'team': 'CLE', 'pos': 'DE', 'stat': 'Sacks', 'line': 1.5, 'higher_mult': 1.08, 'lower_mult': 0.76},
    {'player': 'Myles Garrett', 'team': 'CLE', 'pos': 'DE', 'stat': 'Tackles+Assists', 'line': 3.5, 'higher_mult': 0.86, 'lower_mult': 1.05},
    {'player': 'Myles Garrett', 'team': 'CLE', 'pos': 'DE', 'stat': 'Assists', 'line': 1.5, 'higher_mult': 1.10, 'lower_mult': 0.76},
])

# ALEX WRIGHT
picks.extend([
    {'player': 'Alex Wright', 'team': 'CLE', 'pos': 'DE', 'stat': 'Sacks', 'line': 0.5, 'higher_mult': 1.22, 'lower_mult': 0.71},
])

# MASON GRAHAM
picks.extend([
    {'player': 'Mason Graham', 'team': 'CLE', 'pos': 'DT', 'stat': 'Sacks', 'line': 0.5, 'higher_mult': 1.55, 'lower_mult': 0.63},
])

# SHELBY HARRIS
picks.extend([
    {'player': 'Shelby Harris', 'team': 'CLE', 'pos': 'DT', 'stat': 'Sacks', 'line': 0.5, 'higher_mult': 1.91, 'lower_mult': None},
])

# CARSON SCHWESINGER
picks.extend([
    {'player': 'Carson Schwesinger', 'team': 'CLE', 'pos': 'LB', 'stat': 'Sacks', 'line': 0.5, 'higher_mult': 2.69, 'lower_mult': None},
    {'player': 'Carson Schwesinger', 'team': 'CLE', 'pos': 'LB', 'stat': 'Tackles+Assists', 'line': 10.5, 'higher_mult': 1.04, 'lower_mult': None},
    {'player': 'Carson Schwesinger', 'team': 'CLE', 'pos': 'LB', 'stat': 'Assists', 'line': 5.5, 'higher_mult': 1.06, 'lower_mult': 0.86},
    {'player': 'Carson Schwesinger', 'team': 'CLE', 'pos': 'LB', 'stat': 'Solo Tackles', 'line': 4.5, 'higher_mult': 0.81, 'lower_mult': 1.06},
    {'player': 'Carson Schwesinger', 'team': 'CLE', 'pos': 'LB', 'stat': 'Defensive INTs', 'line': 0.5, 'higher_mult': 6.36, 'lower_mult': None},
])

# PATRICK QUEEN
picks.extend([
    {'player': 'Patrick Queen', 'team': 'PIT', 'pos': 'LB', 'stat': 'Sacks', 'line': 0.5, 'higher_mult': 2.14, 'lower_mult': None},
    {'player': 'Patrick Queen', 'team': 'PIT', 'pos': 'LB', 'stat': 'Solo Tackles', 'line': 4.5, 'higher_mult': 1.04, 'lower_mult': 0.82},
    {'player': 'Patrick Queen', 'team': 'PIT', 'pos': 'LB', 'stat': 'Defensive INTs', 'line': 0.5, 'higher_mult': 4.23, 'lower_mult': None},
])

# JALEN RAMSEY
picks.extend([
    {'player': 'Jalen Ramsey', 'team': 'PIT', 'pos': 'CB', 'stat': 'Sacks', 'line': 0.5, 'higher_mult': 3.91, 'lower_mult': None},
    {'player': 'Jalen Ramsey', 'team': 'PIT', 'pos': 'CB', 'stat': 'Tackles+Assists', 'line': 5.5, 'higher_mult': 1.04, 'lower_mult': 0.82},
    {'player': 'Jalen Ramsey', 'team': 'PIT', 'pos': 'CB', 'stat': 'Assists', 'line': 2.5, 'higher_mult': 1.12, 'lower_mult': 0.75},
    {'player': 'Jalen Ramsey', 'team': 'PIT', 'pos': 'CB', 'stat': 'Solo Tackles', 'line': 2.5, 'higher_mult': 0.78, 'lower_mult': 1.10},
    {'player': 'Jalen Ramsey', 'team': 'PIT', 'pos': 'CB', 'stat': 'Defensive INTs', 'line': 0.5, 'higher_mult': 2.39, 'lower_mult': None},
])

# KYLE DUGGER
picks.extend([
    {'player': 'Kyle Dugger', 'team': 'PIT', 'pos': 'S', 'stat': 'Sacks', 'line': 0.5, 'higher_mult': 4.33, 'lower_mult': None},
    {'player': 'Kyle Dugger', 'team': 'PIT', 'pos': 'S', 'stat': 'Tackles+Assists', 'line': 4.5, 'higher_mult': 0.86, 'lower_mult': 1.05},
    {'player': 'Kyle Dugger', 'team': 'PIT', 'pos': 'S', 'stat': 'Assists', 'line': 1.5, 'higher_mult': 0.76, 'lower_mult': 1.08},
    {'player': 'Kyle Dugger', 'team': 'PIT', 'pos': 'S', 'stat': 'Solo Tackles', 'line': 2.5, 'higher_mult': 0.87, 'lower_mult': 1.04},
    {'player': 'Kyle Dugger', 'team': 'PIT', 'pos': 'S', 'stat': 'Defensive INTs', 'line': 0.5, 'higher_mult': 2.24, 'lower_mult': None},
])

# GRANT DELPIT
picks.extend([
    {'player': 'Grant Delpit', 'team': 'CLE', 'pos': 'S', 'stat': 'Sacks', 'line': 0.5, 'higher_mult': 5.92, 'lower_mult': None},
    {'player': 'Grant Delpit', 'team': 'CLE', 'pos': 'S', 'stat': 'Tackles+Assists', 'line': 3.5, 'higher_mult': 0.81, 'lower_mult': 1.05},
    {'player': 'Grant Delpit', 'team': 'CLE', 'pos': 'S', 'stat': 'Assists', 'line': 1.5, 'higher_mult': 0.77, 'lower_mult': 1.06},
    {'player': 'Grant Delpit', 'team': 'CLE', 'pos': 'S', 'stat': 'Solo Tackles', 'line': 1.5, 'higher_mult': 0.80, 'lower_mult': 1.07},
    {'player': 'Grant Delpit', 'team': 'CLE', 'pos': 'S', 'stat': 'Defensive INTs', 'line': 0.5, 'higher_mult': 4.09, 'lower_mult': None},
])

def calc_implied_prob(mult):
    """Calculate implied probability from multiplier"""
    if mult is None or mult == 0:
        return None
    # Standard UD: 1.0x = ~50%, higher mult = lower prob
    return round(100 / (1 + mult), 1)

def get_recommendation(h_mult, l_mult):
    """Determine YES/NO and direction based on multipliers"""
    h = h_mult or 0
    l = l_mult or 0
    
    # If higher mult > 1.0, there's value on HIGHER
    # If lower mult > 1.0, there's value on LOWER
    
    if h > 1.05:  # Value on HIGHER
        return ('HIGHER', 'YES', calc_implied_prob(h), f'+{int((h-1)*100)}%')
    elif l > 1.05:  # Value on LOWER  
        return ('LOWER', 'YES', calc_implied_prob(l), f'+{int((l-1)*100)}%')
    elif h == 1.0 and l == 1.0:  # Coin flip
        return ('SKIP', 'NO', 50.0, '0%')
    elif h < 0.85:  # Strong lean to LOWER (they're juicing HIGHER)
        return ('LOWER', 'LEAN', calc_implied_prob(h), 'juice on H')
    elif l < 0.85:  # Strong lean to HIGHER (they're juicing LOWER)
        return ('HIGHER', 'LEAN', calc_implied_prob(l), 'juice on L')
    else:
        return ('SKIP', 'NO', 50.0, 'close')

print('=' * 120)
print('PIT @ CLE - SUNDAY 12:00 PM CST - FULL ANALYSIS WITH RECOMMENDATIONS')
print('=' * 120)

# Build full analysis table
print('\n' + '📊 COMPLETE PICKS ANALYSIS'.center(120))
print('=' * 120)
print(f"{'Player':<25} {'Team':<5} {'Stat':<20} {'Line':<6} {'Dir':<8} {'YES/NO':<8} {'Hit %':<8} {'Edge':<12}")
print('-' * 120)

yes_picks = []
no_picks = []

for p in picks:
    h = p.get('higher_mult') or 0
    l = p.get('lower_mult') or 0
    
    direction, yes_no, hit_pct, edge = get_recommendation(h, l)
    
    row = {
        'player': p['player'],
        'team': p['team'],
        'stat': p['stat'],
        'line': p['line'],
        'direction': direction,
        'yes_no': yes_no,
        'hit_pct': hit_pct,
        'edge': edge,
        'h_mult': h,
        'l_mult': l
    }
    
    if yes_no == 'YES':
        yes_picks.append(row)
    else:
        no_picks.append(row)
    
    hit_str = f'{hit_pct}%' if hit_pct else '-'
    print(f"{p['player']:<25} {p['team']:<5} {p['stat']:<20} {p['line']:<6} {direction:<8} {yes_no:<8} {hit_str:<8} {edge:<12}")

# Summary stats
total = len(picks)
yes_count = len(yes_picks)
no_count = len(no_picks)

print('\n' + '=' * 120)
print('📈 SUMMARY'.center(120))
print('=' * 120)
print(f"\nTotal Props Analyzed: {total}")
print(f"✅ YES (Play): {yes_count} ({round(yes_count/total*100, 1)}%)")
print(f"❌ NO (Skip): {no_count} ({round(no_count/total*100, 1)}%)")

# Top YES picks sorted by edge
print('\n' + '🔥 TOP YES PICKS (Sorted by Value)'.center(120))
print('=' * 120)
yes_sorted = sorted(yes_picks, key=lambda x: x['h_mult'] if x['direction'] == 'HIGHER' else x['l_mult'], reverse=True)
print(f"{'Player':<25} {'Team':<5} {'Stat':<22} {'Line':<6} {'Direction':<10} {'Edge':<12} {'Hit %':<8}")
print('-' * 100)
for p in yes_sorted[:25]:
    hit_str = f'{p["hit_pct"]}%' if p["hit_pct"] else '-'
    print(f"{p['player']:<25} {p['team']:<5} {p['stat']:<22} {p['line']:<6} {p['direction']:<10} {p['edge']:<12} {hit_str:<8}")

# Best bets by category
print('\n' + '🎯 BEST BETS BY CATEGORY'.center(120))
print('=' * 120)

print("""
=== RB TDs ===
✅ Jaylen Warren OVER 0.5 Rush+Rec TDs (+12%) - Lead back, goal line
✅ Dylan Sampson OVER 0.5 Rush+Rec TDs (+10%) - CLE workhorse
✅ Kenneth Gainwell OVER 0.5 Rush+Rec TDs (+23%) - Change of pace

=== QB PLAYS ===
✅ Aaron Rodgers OVER 1.5 Pass TDs (+34%) - Should throw 2+
✅ Shedeur Sanders LOWER 0.5 INTs (+13%) - Rookie but careful
✅ Shedeur Sanders LOWER 0.5 Pass TDs (+4%) - Struggles in red zone

=== RECEIVING ===
✅ Harold Fannin OVER 0.5 Rush+Rec TDs (+47%) - Top CLE target
✅ Isaiah Bond OVER 1.5 Receptions (+28%) - Deep threat
✅ Harold Fannin OVER 5.5 Receptions (+7%) - Volume play

=== DEFENSE ===
✅ Alex Wright OVER 0.5 Sacks (+22%) - Active pass rusher
✅ Myles Garrett OVER 1.5 Sacks (+8%) - Best in game
✅ Jalen Ramsey OVER 2.5 Assists (+12%) - Active in coverage

=== KICKERS ===
✅ Chris Boswell LOWER 1.5 FG Made (+9%) - Expect TDs
✅ Andre Szmyt OVER 1.5 XP Made (+7%) - CLE should score

=== CONTRARIAN ===
✅ Dylan Sampson LOWER 2.5 Receptions (+6%) - RB, not receiver
✅ Malachi Corley LOWER 0.5 1H Receptions (+4%) - Low volume
✅ Kyle Dugger LOWER 4.5 Tackles+Assists (+5%) - Safety, fewer tackles
""")

# Recommended stacks
print('\n' + '🏈 RECOMMENDED STACKS'.center(120))
print('=' * 120)

print("""
STACK 1 - PITTSBURGH OFFENSE
• Aaron Rodgers OVER 1.5 Pass TDs (+34%)
• Jaylen Warren OVER 0.5 Rush+Rec TDs (+12%)
• Harold Fannin OVER 52.5 Rec Yards

STACK 2 - CLEVELAND DEFENSE
• Myles Garrett OVER 1.5 Sacks (+8%)
• Alex Wright OVER 0.5 Sacks (+22%)
• Mason Graham OVER 0.5 Sacks (+55%)

STACK 3 - CLEVELAND OFFENSE
• Shedeur Sanders LOWER 0.5 INTs (+13%)
• Dylan Sampson OVER 0.5 Rush+Rec TDs (+10%)
• Harold Fannin OVER 0.5 Rush+Rec TDs (+47%)

STACK 4 - LOW SCORING GAME
• Chris Boswell LOWER 1.5 FG Made (+9%)
• Shedeur Sanders LOWER 0.5 Pass TDs (+4%)
• Aaron Rodgers LOWER 0.5 INTs (juice on H)
""")
