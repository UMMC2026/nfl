# Roster File Requirements and Update Process

## Purpose
To ensure backup roster validation works for all sports (NBA, NFL, CFB, CBB), all roster CSVs must follow a standard format. This enables the pipeline to always use local roster files if API sources fail.

## Required CSV Headers
- player_id
- player_name
- team
- status
- game_id
- updated_utc

**Each player row must have a unique `player_id`.**

## Update Process
1. When adding or updating a roster file (NBA, NFL, CFB, CBB):
    - Ensure all required headers are present (see above).
    - Assign a unique `player_id` to each player row.
    - Save the file in `data_center/rosters/` as `[LEAGUE]_active_roster_current.csv` or similar.
2. If you add new players, increment the `player_id` (can be any unique integer or string).
3. Always keep the format consistent for all leagues.

## Developer Note
- This process is now documented in each roster file as a comment at the top.
- If you automate roster updates, ensure the script writes the correct headers and unique IDs.

## Prototype Example
```
player_id,player_name,team,status,game_id,updated_utc
1,John Doe,CFBTEAM,ACTIVE,CFBTEAM-OPP-20260110,2026-01-10T12:00:00Z
2,Jane Smith,CBBTEAM,ACTIVE,CBBTEAM-OPP-20260110,2026-01-10T12:00:00Z
```

## Summary
- All roster files for NBA, NFL, CFB, CBB must use this format.
- This guarantees backup validation always works, regardless of league.
