# Soccer Cache Directory

**Created:** 2026-02-04
**Purpose:** Isolated cache for Soccer module data

## Contents
- Player shot/goal data by league
- xG (Expected Goals) statistics
- Team form data (L5/L10)
- Competition-specific caching

## Supported Leagues
- Premier League
- La Liga
- Serie A
- Bundesliga
- Ligue 1

## Rules
- Data keyed by: {league}_{team}_{player}
- Form data expires after each matchday
- No cross-contamination with other sports
