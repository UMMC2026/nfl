"""
FREE-TIER 20-MINUTE DELAY — ACTIVATION CHECKLIST
=================================================

This feature creates natural upgrade urgency by showing FREE tier users
signals with a 20-minute delay + upgrade CTA, while STARTER+ see all
signals immediately.

## 1️⃣ ARCHITECTURE READINESS

### Code Components ✓

- [x] `SignalShaper.should_delay_for_free_tier()` — Checks signal age vs 20-min threshold
- [x] `SignalShaper.shape(signal, PlanTier.FREE)` — Returns delayed payload for recent signals
- [x] `SignalOut` model — Has `delayed`, `delayed_until`, `message` fields
- [x] `format_signal_for_tier()` — Passes delay fields through to SignalOut
- [x] Endpoint `/signals` — Uses `format_signal_for_tier()`, calls `SignalShaper.shape()`

### Implementation Status

**Complete**: All code wired. Delay logic is **already in place** and active.

---

## 2️⃣ SIGNAL DATA REQUIREMENTS

### published_at Field

**Requirement**: Every signal in `signals_latest.json` MUST have `published_at` field.

**Format**: ISO 8601 with Z suffix
```json
{
  "player": "LeBron James",
  "stat": "points",
  "published_at": "2025-12-30T13:15:30Z",
  ...
}
```

**Check**:
```bash
# Verify signals have published_at
python -c "
import json
signals = json.load(open('output/signals_latest.json'))
print(f'Total signals: {len(signals)}')
missing = [s for s in signals if 'published_at' not in s]
print(f'Missing published_at: {len(missing)}')
if missing:
    print('First missing:', missing[0])
"
```

**Action**: If signals missing `published_at`:
1. Add field to signal generation code
2. Set to datetime.utcnow().isoformat() + "Z"
3. Regenerate signals_latest.json

---

## 3️⃣ ENDPOINT BEHAVIOR (NOW ACTIVE)

### FREE Tier

**Old Signal** (≥ 20 min ago):
```json
GET /signals?user_id=123 (FREE tier)

{
  "player": "LeBron James",
  "stat": "points",
  "line": 24.5,
  "direction": "higher",
  "tier": "SLAM",
  "delayed": false
}
```

**Recent Signal** (< 20 min ago):
```json
{
  "player": "LeBron James",
  "stat": "points",
  "line": 24.5,
  "direction": "higher",
  "delayed": true,
  "delayed_until": "2025-12-30T14:15:30Z",
  "message": "Upgrade to see signals within 20 minutes"
}
```

### STARTER+ Tiers

**All Signals** (all ages):
```json
{
  "player": "LeBron James",
  "stat": "points",
  "line": 24.5,
  "direction": "higher",
  "tier": "SLAM",
  "probability": 0.75,
  "stability_score": 0.82,
  "edge": 0.12,
  "delayed": false
}
```

Never delayed, always full fields.

---

## 4️⃣ TESTING BEFORE PRODUCTION

### Unit Verification

```bash
# Test delay logic
python verify_free_tier_delay.py

# Expected output: ✅ ALL FREE-TIER DELAY TESTS PASSED
```

### Endpoint Test (Manual)

1. Start API:
```bash
python -m uvicorn ufa.api.main:app --reload --port 8000
```

2. Register FREE user:
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"free@test.com", "password":"test123", "display_name":"FreeUser"}'
```

3. Get signals (recent):
```bash
# Ensure signals_latest.json has signals with published_at = now
curl -X GET http://localhost:8000/signals \
  -H "Authorization: Bearer <FREE_USER_TOKEN>"

# Should show: delayed=true, delayed_until, message
```

4. Register STARTER user:
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"paid@test.com", "password":"test123", "display_name":"PaidUser"}'

# Manually upgrade tier in DB:
# UPDATE subscriptions SET plan_tier='starter' WHERE user_id=<id>
```

5. Get signals (same recent signals):
```bash
curl -X GET http://localhost:8000/signals \
  -H "Authorization: Bearer <STARTER_TOKEN>"

# Should show: delayed=false, probability visible, message absent
```

---

## 5️⃣ DEPLOYMENT CHECKLIST

- [ ] Verify signals have `published_at` field
- [ ] Run `python verify_free_tier_delay.py` → ✅ PASS
- [ ] Test endpoint with FREE user → signals delayed correctly
- [ ] Test endpoint with STARTER user → signals NOT delayed
- [ ] Verify `delayed_until` timestamp is valid ISO 8601
- [ ] Verify upgrade CTA message is present for recent signals
- [ ] Spot-check old signals (30+ min) are NOT delayed
- [ ] Monitor logs for any exceptions in delay logic
- [ ] Deploy to staging, notify QA team

---

## 6️⃣ MONITORING & METRICS

### Key Metrics to Track

1. **Delay Exposure Rate**
   ```sql
   SELECT 
     COUNT(*) as signal_calls,
     ROUND(100 * SUM(CASE WHEN delayed THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_delayed
   FROM signal_views
   WHERE user_tier = 'free' AND created_at >= DATE_SUB(NOW(), INTERVAL 1 DAY);
   ```

2. **Upgrade Trigger by Delay**
   ```sql
   SELECT 
     'free_to_starter' as upgrade_path,
     COUNT(DISTINCT user_id) as upgraded,
     ROUND(AVG(DAYS_TO_UPGRADE), 1) as avg_days
   FROM upgrade_events
   WHERE from_tier = 'free' AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY);
   ```

3. **CTA Click Rate** (if tracking via Segment/GA)
   - How many users click "Upgrade to see signals" message
   - Expected: 5–15% of delayed signal exposures

### Success Criteria

- **Week 1**: ≥ 10% of FREE users see ≥ 1 delayed signal
- **Week 2**: 2–5% of FREE users upgrade to STARTER
- **Week 4**: Cumulative upgrade rate: 8–15%
- **No regression**: Paid tier churn unchanged

---

## 7️⃣ TROUBLESHOOTING

### Problem: Signals not delayed (all showing delayed=false)

**Check**:
1. Are signals in DB/file recent (< 20 min old)?
2. Does signal have `published_at` field?
3. Is `published_at` in ISO 8601 format with Z?
4. Is datetime.utcnow() working correctly?

**Debug**:
```python
from ufa.signals.shaper import SignalShaper
signal = {..., "published_at": "2025-12-30T13:15:30Z"}
print(SignalShaper.should_delay_for_free_tier(signal))  # Should be True if recent
```

### Problem: Incorrect delayed_until timestamp

**Root cause**: datetime arithmetic error in shaper

**Check**: 
```python
from datetime import datetime, timedelta
published = datetime.fromisoformat("2025-12-30T13:15:30Z".replace("Z", "+00:00"))
delayed_until = published + timedelta(minutes=20)
print(delayed_until.isoformat() + "Z")
```

**Solution**: Verify timedelta(minutes=20) is correct; adjust if needed

### Problem: STARTER tier still seeing delayed signals

**Root cause**: Tier detection not working

**Check**:
```python
from ufa.models.user import PlanTier
print(PlanTier.STARTER)  # Should print "starter"
print(PlanTier.STARTER == PlanTier.STARTER)  # Should be True
```

**Solution**: Verify tier enum values in user.py match PlanTier checks in shaper.py

---

## 8️⃣ NEXT STEPS AFTER DEPLOYMENT

### Week 1–2 (Post-Launch)
- Monitor upgrade rates daily
- Check for any exceptions in delay logic
- Verify published_at field is being set correctly on new signals

### Week 3–4
- Analyze cohort: users who saw delayed signals vs. control
- Measure upgrade funnel
- Consider A/B testing: 15-min vs. 20-min vs. 30-min delay

### Later
- Tier 3: Telegram mirroring (apply same shaper)
- Tier 4: Add confidence caps to Telegram output
- Tier 5: A/B test different upgrade CTA messages

---

## 9️⃣ PSYCHOLOGY & DESIGN NOTES

**Why This Works:**

* **Free tier sees activity** (not blocked) → stays engaged
* **Free tier sees conviction gap** (no "ELITE" confidence) → feels exclusion
* **Free tier sees time gap** (20-min delay) → feels time pressure
* **No manipulation** (all truthful, just withheld resolution) → maintains trust

**User Journey:**

```
Day 1: Sees first signal (old, not delayed) → "What's this?"
Day 2: Sees recent signal (delayed) → "I'm waiting 20 min? ...OK"
Day 3: Sees another delayed signal → "This is annoying"
Day 4–5: Clicks "Upgrade to see signals" → Converts
Day 6+: Enjoys full signals immediately → Retention
```

---

## ✅ READY FOR PRODUCTION

All code is **in place and active**.
Signals endpoint **already returns delayed payloads** for FREE users with recent signals.

**Last step before deployment**: Ensure signals have `published_at` field.

Then deploy and monitor upgrade rates.
