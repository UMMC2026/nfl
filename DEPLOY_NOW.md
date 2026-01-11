"""
IMMEDIATE NEXT ACTIONS — Copy/Paste Ready
===========================================

## Step 1: Verify Feature is Live (2 min)

Run this to confirm all delay logic is working:

```powershell
cd "C:\Users\hiday\UNDERDOG ANANLYSIS"
python verify_free_tier_delay.py
```

Expected output:
```
✅ ALL FREE-TIER DELAY TESTS PASSED
```

If you see ✅, proceed to Step 2.
If you see ✗, check the error and reply with the output.

---

## Step 2: Verify Signals Have published_at (2 min)

Check that your signal data has the required `published_at` field:

```powershell
python -c "
import json
signals = json.load(open('output/signals_latest.json'))
print(f'Total signals: {len(signals)}')
missing = [s for s in signals if 'published_at' not in s]
print(f'Missing published_at: {len(missing)}')
if missing:
    print('First missing:', missing[0].get('player', 'Unknown'))
else:
    print('✓ All signals have published_at')
"
```

Expected: `✓ All signals have published_at`

If signals are missing `published_at`:
- You need to add this field to your signal generation code
- Set it to: `datetime.utcnow().isoformat() + "Z"`
- Then regenerate `output/signals_latest.json`

---

## Step 3: Start API and Test Live (5 min)

### 3a. Start the API

```powershell
cd "C:\Users\hiday\UNDERDOG ANANLYSIS"
python -m uvicorn ufa.api.main:app --reload --port 8000
```

Wait for: `Uvicorn running on http://127.0.0.1:8000`

### 3b. In a NEW terminal, register a FREE user

```powershell
$body = @{
    email = "free_test_$(Get-Random)@example.com"
    password = "testpass123"
    display_name = "FreeTestUser"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://localhost:8000/auth/register" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$token = $response.access_token
echo "Token: $token"
```

Save the token (you'll use it next).

### 3c. Call /signals endpoint with FREE user token

```powershell
$token = "YOUR_TOKEN_FROM_STEP_3b"

$headers = @{
    "Authorization" = "Bearer $token"
}

$signals = Invoke-RestMethod `
    -Uri "http://localhost:8000/signals" `
    -Method GET `
    -Headers $headers

$signals | ConvertTo-Json | Write-Host
```

**Expected behavior:**

If signals are **recent** (< 20 min old):
```json
{
  "delayed": true,
  "delayed_until": "2025-12-30T14:15:30Z",
  "message": "Upgrade to see signals within 20 minutes",
  "player": "LeBron James",
  ...
}
```

If signals are **old** (≥ 20 min):
```json
{
  "delayed": false,
  "player": "LeBron James",
  ...
}
```

If you see `delayed=true` with `delayed_until` and `message`, **feature is working** ✓

---

## Step 4: Test STARTER Tier (3 min)

### 4a. Register a STARTER user

```powershell
$body = @{
    email = "starter_test_$(Get-Random)@example.com"
    password = "testpass123"
    display_name = "StarterTestUser"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://localhost:8000/auth/register" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$starter_user_id = $response.user_id
echo "User ID: $starter_user_id"
```

### 4b. Manually upgrade tier in database (or via admin endpoint if you have one)

If you have an admin endpoint to set tier:
```powershell
$admin_token = "YOUR_ADMIN_TOKEN"
Invoke-RestMethod `
    -Uri "http://localhost:8000/admin/users/$starter_user_id/tier" `
    -Method PUT `
    -Headers @{ "Authorization" = "Bearer $admin_token" } `
    -ContentType "application/json" `
    -Body (@{ tier = "starter" } | ConvertTo-Json)
```

Or use SQLite directly:
```powershell
# Open SQLite
sqlite3 underdog.db

# Update tier
UPDATE subscriptions SET plan_tier = 'starter' WHERE user_id = 2;
.exit
```

### 4c. Call /signals with STARTER token

```powershell
$starter_token = "STARTER_USER_TOKEN_FROM_4a"

$headers = @{ "Authorization" = "Bearer $starter_token" }

$signals = Invoke-RestMethod `
    -Uri "http://localhost:8000/signals" `
    -Method GET `
    -Headers $headers

$signals | ConvertTo-Json | Write-Host
```

**Expected behavior:**

```json
{
  "delayed": false,
  "probability": 0.75,
  "stability_score": 0.82,
  "edge": 0.12,
  "player": "LeBron James",
  ...
}
```

Notice:
- `delayed` is `false` (never delayed for paid users)
- `probability` is visible (not in FREE response)
- No `delayed_until` or `message`

If you see this, **feature is working correctly** ✓

---

## Step 5: Deploy to Staging (Immediate)

Once tests pass (Steps 1–4):

```powershell
# 1. Commit code
git add -A
git commit -m "feat: free-tier 20-min signal delay + confidence caps

- Implement time-based urgency for free users
- Apply confidence capping (ELITE→STRONG for free tier)
- Field visibility by tier (FREE: basic, STARTER: prob, PRO: notes, WHALE: internals)
- No breaking changes, all tests pass"

# 2. Push to staging branch
git push origin main

# 3. Deploy (depends on your CD pipeline)
# If using GitHub Actions:
# - Merge to staging branch
# - GHA deploys automatically

# If manual:
# - SSH to staging server
# - git pull
# - restart service
```

---

## Step 6: Monitor (First 24 Hours)

Watch these metrics:

```sql
-- 1. How many FREE users are seeing delayed signals?
SELECT 
  COUNT(*) as total_calls,
  SUM(CASE WHEN delayed THEN 1 ELSE 0 END) as delayed_calls,
  ROUND(100 * SUM(CASE WHEN delayed THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_delayed
FROM signal_views
WHERE user_tier = 'free' AND created_at >= NOW() - INTERVAL '1 day';

-- 2. Are any users upgrading from FREE to STARTER?
SELECT 
  COUNT(*) as upgrades,
  AVG(EXTRACT(EPOCH FROM (upgraded_at - first_seen_at)) / 3600) as avg_hours_to_upgrade
FROM user_upgrades
WHERE from_tier = 'free' AND upgraded_at >= NOW() - INTERVAL '1 day';

-- 3. Are there any errors in delay logic?
SELECT * FROM logs 
WHERE level = 'ERROR' AND message LIKE '%delay%' AND timestamp >= NOW() - INTERVAL '1 day';
```

Success criteria:
- 20–40% of FREE users see ≥ 1 delayed signal
- 1–3% of exposed FREE users upgrade within 24 hours
- 0 errors in logs

---

## Troubleshooting (If Something's Wrong)

### Q: Signals not being delayed (all showing delayed=false)

A: Check if `published_at` field is recent:
```powershell
python -c "
import json
from datetime import datetime, timedelta
signals = json.load(open('output/signals_latest.json'))
for s in signals[:3]:
    published = datetime.fromisoformat(s['published_at'].replace('Z', '+00:00'))
    age_min = (datetime.now(published.tzinfo) - published).total_seconds() / 60
    print(f\"{s['player']}: {age_min:.1f} min old\")
"
```

If all signals are > 20 min old, they won't be delayed (correct behavior).

**Solution**: Generate fresh signals with `published_at = now()`.

### Q: TypeError about published_at

A: Ensure `published_at` is ISO 8601 format with Z suffix:
```
✓ 2025-12-30T13:15:30Z
✗ 2025-12-30 13:15:30
✗ 2025-12-30T13:15:30  (missing Z)
```

**Solution**: Fix signal generation to include Z suffix.

### Q: STARTER tier still seeing delayed payloads

A: Tier detection issue. Check:
```python
from ufa.models.user import PlanTier
print(PlanTier.STARTER.value)  # Should print 'starter'
```

If wrong, update `ufa/models/user.py` PlanTier enum.

---

## What to Do If Tests Pass ✅

Reply with:
- **"Tests pass, deploying to staging"** → Proceed with Step 5
- **"Tests fail with [ERROR]"** → Share the error output and I'll fix it
- **"Feature working, waiting for data"** → Great! Proceed to monitor (Step 6)

You're ready. Go.
"""
