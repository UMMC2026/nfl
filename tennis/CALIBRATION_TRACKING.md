# Tennis Calibration Tracking — Quick Reference

## Status: ✅ ACTIVE (Wired 2026-02-15)

Tennis picks are now automatically saved to the unified calibration system after passing the direction gate.

---

## Automatic Tracking

**When picks are saved:**
- After successful analysis in paste mode (`_run_props_analysis`)
- Only SLAM, STRONG, and LEAN picks are tracked
- Only picks that pass the direction gate (<65% bias)

**What gets saved:**
```python
{
    "pick_id": "tennis_2026-02-15_Medvedev_sets_played_2.5_Higher",
    "date": "2026-02-15",
    "sport": "tennis",
    "player": "Daniil Medvedev",
    "stat": "sets_played",
    "line": 2.5,
    "direction": "Higher",
    "probability": 99.0,
    "tier": "SLAM",
    "team": "N/A",
    "opponent": "TBD",
    "model_version": "calibrated_props_v1"
}
```

---

## Viewing Calibration Data

### Check what's tracked:
```bash
python -m calibration.unified_tracker --report --sport tennis
```

### View CSV directly:
```bash
# All picks across sports
cat calibration_history.csv | grep "tennis"

# Tennis picks only
python -c "import csv; [print(r) for r in csv.DictReader(open('calibration_history.csv')) if r.get('league')=='tennis']"
```

---

## Resolving Results (Manual Process - TODO)

Currently, Tennis results must be resolved manually:

1. **After matches complete**, open `calibration_history.csv`
2. **Find Tennis picks** (look for `sport=tennis` or `league=tennis`)
3. **Look up actual stats** from:
   - Tennis Abstract (tennis-abstract.com)
   - ATP/WTA official sites
   - Flashscore or similar
4. **Fill columns**:
   - `actual_value`: The actual stat value (e.g., 3 sets played)
   - `outcome`: "hit" or "miss"

### Example:
```csv
# Before
tennis_2026-02-15_Medvedev_sets_played_2.5_Higher,2026-02-15,tennis,Medvedev,sets_played,2.5,Higher,99.0,SLAM,,,

# After (match ended 3 sets)
tennis_2026-02-15_Medvedev_sets_played_2.5_Higher,2026-02-15,tennis,Medvedev,sets_played,2.5,Higher,99.0,SLAM,3.0,hit,
```

---

## Automatic Resolution (Future)

**TODO**: Implement `resolve_tennis_results()` with:
- Tennis Abstract API integration
- Match result lookup by date + player name
- Automatic stat extraction
- CSV update

---

## Integration Points

### tennis_main.py
```python
# Line ~312: After direction gate passes
from tennis.calibration_saver import save_picks_to_calibration
save_picks_to_calibration(results)
```

### calibration_saver.py
```python
def save_picks_to_calibration(results: dict) -> int:
    """Extracts picks from tiers and saves to UnifiedCalibration"""
```

---

## Known Issues

1. **Direction Gate blocks all picks**: If gate triggers (>65% bias), NO picks are saved to calibration
   - This is correct behavior (don't track picks you didn't bet)
   - But means calibration data only comes from "clean" slates

2. **No opponent tracking**: Tennis picks currently show `opponent="TBD"`
   - Match context not passed through yet
   - Would need parse player1 vs player2 format

3. **Manual resolution required**: No automated stat lookup yet
   - Need Tennis Abstract API integration
   - Or web scraping solution

---

## Calibration Analysis Commands

Once you have resolved picks (manual CSV updates):

```bash
# Overall Tennis accuracy
python -m calibration.unified_tracker --report --sport tennis

# Brier score breakdown
python quant_modules/calibration_analysis.py --sport tennis

# Tier accuracy
python -m calibration.unified_tracker --by-tier --sport tennis
```

---

## Testing Calibration

To verify the system is working:

1. Run Tennis analysis that passes direction gate
2. Check console for: `📊 Calibration: Saved X Tennis picks for tracking`
3. Open `calibration_history.csv`
4. Search for today's date + "tennis"
5. Verify picks are listed

---

## See Also

- [calibration/unified_tracker.py](../calibration/unified_tracker.py) — Core tracking system
- [soccer/soccer_menu.py](../soccer/soccer_menu.py#L278) — Soccer implementation (reference)
- [NBA calibration](../risk_first_analyzer.py#L2273) — NBA implementation (reference)
- [CBB calibration](../sports/cbb/models/calibration.py) — CBB implementation (reference)
