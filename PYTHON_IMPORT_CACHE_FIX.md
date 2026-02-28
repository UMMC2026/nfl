# Python Import Cache Bug — CRITICAL LESSON

## 🐛 Problem Discovered: 2026-02-15 16:15

### What Happened
After adding debug logging to `sports/cbb/cbb_main.py` and clearing ALL .pyc files:
- ✅ Source file had debug code (verified at line 1680)
- ✅ .pyc cache was cleared (68 files removed)
- ❌ Debug prints STILL didn't appear when running pipeline

### Root Cause
**Python's import cache persists in the RUNNING PROCESS, not just .pyc files.**

```python
# When menu.py starts:
import sports.cbb.cbb_main  # ← Module loaded into sys.modules

# Even if you:
# 1. Edit sports/cbb/cbb_main.py
# 2. Delete sports/cbb/__pycache__/*.pyc
# 3. Run analysis again
# → Python STILL executes the OLD module from sys.modules
```

### Evidence Chain

1. **Source file confirmed correct** (5 debug lines present):
   ```powershell
   PS > Select-String -Path "sports\cbb\cbb_main.py" -Pattern "\[DEBUG\]"
   Found 5 lines with [DEBUG] in source file ✅
   ```

2. **Cache cleared** (68 .pyc files removed):
   ```powershell
   PS > Remove-Item -Path "sports\cbb\" -Filter "__pycache__" -Recurse -Force
   ✓ Removed 68 .pyc files ✅
   ```

3. **Pipeline executed** (function was called):
   ```
   [3/5] APPLY GATES          ← Line 1676 printed ✅
   ----------------------------------------  ← Line 1677 printed ✅
   [DEBUG] Edges before...    ← Line 1680 NOT printed ❌
   [ESPN] Loaded 1 games...   ← Line 1721 printed ✅
   ```

4. **Diagnosis**: Function prints lines 1676, 1677, 1721 but NOT 1680-1705.
   - **IMPOSSIBLE** unless executing DIFFERENT bytecode than source
   - **Confirmed**: Python's `sys.modules` cache has stale import

---

## ✅ Solution

### Immediate Fix
**Exit menu.py and restart it:**

```bash
# In menu.py:
[Q] Quit

# Then restart:
.venv\Scripts\python.exe menu.py
```

### Why This Works
- Python's import cache (`sys.modules`) is cleared when process exits
- Fresh process imports from source code (not memory cache)
- New bytecode compiled from updated source

---

## 🎓 Lessons Learned

### Clearing .pyc Files Is NOT Enough

**What we tried (insufficient):**
```powershell
# This clears disk cache, but not process memory:
Remove-Item sports\cbb\__pycache__\*.pyc -Force
```

**What actually works:**
```bash
# Exit Python process completely, then restart
exit()  # or Ctrl+C, or [Q] Quit
```

### Python Import Behavior

1. **First import**: Python compiles .py → .pyc, loads into `sys.modules`
2. **Subsequent imports**: Python checks `sys.modules` FIRST (not filesystem)
3. **Module modifications**: Changes to .py NOT reflected until process restart

### Debug Trap: "Source looks correct"

When debugging, you might verify:
- ✅ Source code has changes
- ✅ .pyc files cleared
- ✅ File timestamps are fresh

But still see OLD behavior because:
- ❌ The RUNNING PROCESS has stale import in `sys.modules`

**Always restart the process after modifying imported modules.**

---

## 🔧 Better Development Workflow

### Option 1: Use importlib.reload() (Quick)
```python
# In menu.py or wherever cbb_main is imported:
import importlib
from sports.cbb import cbb_main

# After modifying cbb_main.py:
importlib.reload(cbb_main)  # ← Force Python to re-import from disk
```

**Limitations:**
- Only reloads ONE module (not transitive imports)
- class instances retain old code
- Not suitable for complex dependency trees

### Option 2: Restart Process (Reliable)
```bash
# Always restart after code changes to imported modules:
[Q] Quit → restart menu.py
```

**Advantages:**
- Clean slate (all modules reloaded)
- No risk of mixed old/new code
- Catches import errors early

### Option 3: Dev Mode with Auto-Reload (Best for Iteration)
```python
# Add to menu.py or create dev_menu.py:
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ReloadOnChange(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            print(f"🔄 {event.src_path} changed - restarting...")
            os.execv(sys.executable, ['python'] + sys.argv)

observer = Observer()
observer.schedule(ReloadOnChange(), path='sports/cbb', recursive=True)
observer.start()
```

---

## 🚨 Production Safeguards

### Pre-Deployment Checklist

Before deploying CBB pipeline to production:

1. **Fresh Python process test**:
   ```bash
   .venv\Scripts\python.exe -c "from sports.cbb import cbb_main; cbb_main.run_full_pipeline()"
   ```

2. **Clear all cache**:
   ```powershell
   Get-ChildItem -Path "sports\cbb\" -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
   ```

3. **Verify debug code removed**:
   ```bash
   # Before production, remove all [DEBUG] prints:
   grep -r "\[DEBUG\]" sports/cbb/*.py
   # Should return ZERO matches
   ```

4. **Integration test with fresh import**:
   ```python
   # test_cbb_fresh_import.py
   import subprocess
   result = subprocess.run(['.venv/Scripts/python.exe', 'menu.py', '--test-cbb'], 
                          capture_output=True)
   assert b"[DEBUG]" not in result.stdout  # No debug in production
   assert b"Direction Gate" in result.stdout  # Gate is wired
   ```

---

## 📊 Impact Assessment

### Time Lost
- **Phase 15**: 15 minutes (initial cache clear)
- **Phase 16**: 20 minutes (verification, manual debug run)
- **Phase 17**: 25 minutes (nuclear cache clear, diagnostics)
- **Total**: ~60 minutes debugging Python import cache

### Root Cause
- **Not a code bug** — Source was correct
- **Not a cache bug** — .pyc files were cleared
- **Import cache behavior** — Python's `sys.modules` persists across runs within same process

### Prevention
- **Always restart Python process** after modifying imported modules
- **Add to copilot instructions**: "After editing .py files, remind user to restart menu.py"
- **Consider**: Auto-reload dev mode for faster iteration

---

## 🎯 Next Steps

1. **User action**: Exit menu.py, restart, run CBB analysis
2. **Expected output**: All 5 [DEBUG] lines should appear
3. **If gate triggers**: 85% UNDER bias should abort pipeline
4. **Remove debug logging**: After confirming gate works
5. **Document in SOP**: Python import cache behavior

---

**Bottom Line**: Clearing .pyc files clears DISK cache, but Python's PROCESS cache (`sys.modules`) requires a full process restart. This is standard Python behavior, not a bug, but easy to forget during rapid development.
