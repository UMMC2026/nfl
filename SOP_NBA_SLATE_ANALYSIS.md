# NBA Slate Analysis SOP: Stat Cache Verification

**Step: Always verify stat cache before running analysis!**

---

## 1. After pasting your slate, but BEFORE running analysis:

- Locate the stat cache file for the current date:
  - `outputs/stats_cache/nba_mu_sigma_L10_L5_blend0.65_auto_<YYYY-MM-DD>.json`
  - Example: `outputs/stats_cache/nba_mu_sigma_L10_L5_blend0.65_auto_2026-01-19.json`


## 2. For each player in your slate:
- Confirm the player is listed as **Active**
- Confirm L5, L10, SEASON stats are present (PTS, REB, AST, 3PM, STL, BLK, PRA)
- Ensure no ❌ (OUT) or ⚠️ (Questionable) status unless you intend to include them
- **If any player or stat is missing from the cache:**
  - **You MUST run the stat cache update script or menu option** to fetch stats for all slate players for today’s date.
  - Example:
    ```
    python scripts/update_nba_stat_cache.py --date YYYY-MM-DD --teams PHI,IND
    ```
    or use `[Update Stat Cache]` in the menu.
  - Only proceed to analysis after confirming all stat values are present for every slate player.

## 3. If a player is missing stats or marked OUT after update:
- Double-check spelling and team assignment in both the slate and cache.
- If still missing, investigate for new players, trades, or API issues.

## 4. Only proceed to analysis/entry building after confirming all slate players have up-to-date stats in the cache.

---

**Summary:**
> Always check the stat cache file for your slate’s date and roster before running analysis. This ensures you’re using the most accurate, up-to-date player stats and avoids “NO DATA” or “SKIP” results in your output.
