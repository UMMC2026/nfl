    `` import os
import sys
import json
import time
from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parent
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
STATE_DIR = PROJECT_ROOT / "state"
STATE_DIR.mkdir(exist_ok=True)
STATE_FILE = STATE_DIR / "ocr_processed.json"

# Prefer .venv python (with easyocr installed); fallback to current interpreter
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON_EXE = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

POLL_SECONDS = float(os.getenv("OCR_WATCH_POLL_SECONDS", "3"))
EXTS = {".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG"}


def load_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def save_state(state: dict):
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def list_images():
    files = []
    if not SCREENSHOTS_DIR.exists():
        return files
    for p in SCREENSHOTS_DIR.glob("**/*"):
        if p.is_file() and p.suffix in EXTS:
            files.append(p)
    return sorted(files, key=lambda x: x.stat().st_mtime)


def ocr_image(path: Path):
    print(f"[WATCH] OCR: {path.name}")
    try:
        result = subprocess.run(
            [PYTHON_EXE, str(PROJECT_ROOT / "parse_results_image.py"), str(path)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        
        # Check if OCR output contains tennis match result
        if result.stdout and "def." in result.stdout.lower():
            # Potential tennis match — update Elo
            try:
                tennis_bridge = PROJECT_ROOT / "tennis" / "ocr_to_elo_bridge.py"
                if tennis_bridge.exists():
                    subprocess.run(
                        [PYTHON_EXE, str(tennis_bridge), result.stdout],
                        cwd=str(PROJECT_ROOT)
                    )
            except Exception as e:
                print(f"[WATCH] Elo update skipped: {e}")
                
    except Exception as e:
        print(f"[WATCH] OCR error: {e}")


def main():
    print("\n=== SCREENSHOTS WATCHER (Auto-OCR) ===")
    print(f"Folder: {SCREENSHOTS_DIR}")
    print(f"Poll interval: {POLL_SECONDS}s")
    print("Press Ctrl+C to stop.\n")

    processed = load_state()
    # processed format: {"<filepath>": mtime_float}

    try:
        while True:
            imgs = list_images()
            for img in imgs:
                try:
                    mtime = img.stat().st_mtime
                except FileNotFoundError:
                    continue
                key = str(img.resolve())
                last = processed.get(key)
                if (last is None) or (mtime > last):
                    # New or updated image => OCR it
                    ocr_image(img)
                    processed[key] = mtime
                    save_state(processed)
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\n[WATCH] Stopped.")


if __name__ == "__main__":
    main()
