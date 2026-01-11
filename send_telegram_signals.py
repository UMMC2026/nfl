import os
import time
from pathlib import Path
import sys
from utils.io import load_json
from engine.render_gate import render_gate, RenderGateError


OUTPUT_FILE = Path("outputs/validated_primary_edges.json")
MAX_AGE_SECONDS = 120 * 60  # 2 hours (allow picks from earlier today to send)


class TelegramSendError(Exception):
    pass


def _assert_file_exists():
    if not OUTPUT_FILE.exists():
        raise TelegramSendError("Validated output file missing.")


def _assert_freshness():
    from datetime import datetime
    age = time.time() - OUTPUT_FILE.stat().st_mtime
    ts = datetime.fromtimestamp(OUTPUT_FILE.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    print(f"✅ File timestamp: {ts} (age: {int(age/60)} min)")
    if age > MAX_AGE_SECONDS:
        raise TelegramSendError(
            f"❌ Validated output is stale ({int(age/60)} min old, max {int(MAX_AGE_SECONDS/60)} min)."
        )


def _load_validated_picks():
    picks = load_json(OUTPUT_FILE)

    if not isinstance(picks, list) or len(picks) == 0:
        raise TelegramSendError("Validated output empty or invalid.")

    return picks


def _audit_failure(msg: str):
    """Record a short audit log for Telegram failures."""
    try:
        from datetime import datetime
        logdir = OUTPUT_FILE.parents[0] / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        logfile = logdir / "telegram_failures.log"
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} - {msg}\n")
    except Exception:
        # Best-effort only
        pass


def run(dry_run: bool = False):
    """Send validated primary signals to Telegram.

    dry_run: if True, do not import/send via bot; just print formatted messages.
    """
    print("📤 TELEGRAM SEND START")

    # Ensure project root is on sys.path so local packages (Telegram/, ufa/) import reliably
    ROOT = Path(__file__).resolve().parents[0]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    print(f"[TELEGRAM] Using validated file: {OUTPUT_FILE.resolve()}")
    try:
        mtime = OUTPUT_FILE.stat().st_mtime
        from datetime import datetime
        print(f"[TELEGRAM] Last modified: {datetime.fromtimestamp(mtime)}")
    except Exception:
        pass

    _assert_file_exists()
    _assert_freshness()

    picks = _load_validated_picks()

    # 🔒 ABSOLUTE SAFETY: re-run render gate
    try:
        picks = render_gate(picks)
    except RenderGateError as e:
        raise TelegramSendError(f"Render gate failed: {e}")

    # Lazy import of telegram helpers to avoid import-time failures when deps missing
    if dry_run:
        def _format_signal(p):
            # best-effort simple formatter
            return (
                f"📊 {p.get('player','UNKNOWN')} | {p.get('direction','?').upper()} {p.get('line','?')} {p.get('stat','?')} "
                f"| Prob: {int(p.get('probability',0)*100)}% | Tier: {p.get('confidence_tier','?')}"
            )

        def _send_message(msg):
            print("[DRY SEND]", msg)
    else:
        try:
            from telegram.formatter import format_signal as _format_signal
            from telegram.bot import send_message as _send_message
        except Exception as e:
            # If the site-package telegram is not usable (missing stdlib modules like imghdr
            # or vendor bundles), fall back to the project's transport and shaper if present.
            print(f"[TELEGRAM] site-package import failed: {e}. Attempting project fallback...")
            try:
                from ufa.services.telegram_shaper import format_signal_for_telegram as _format_signal
                from Telegram.transport import send_message as _send_message
            except Exception as e2:
                # Provide clear error and a helpful hint instead of crashing on import
                raise TelegramSendError(
                    f"Telegram libraries not available or failed to import: {e} / {e2}.\n"
                    "Install python-telegram-bot in the virtualenv or run with dry_run=True."
                )

    sent = 0

    for p in picks:
        if not p.get("is_primary", False):
            continue

        msg = _format_signal(p)
        try:
            _send_message(msg)
            sent += 1
        except Exception as e:
            print(f"❌ Failed to send for {p.get('player')}: {e}")
            # continue with others

    if sent == 0:
        raise TelegramSendError("Zero signals sent — aborting.")

    print(f"✅ TELEGRAM SENT: {sent} signals")


if __name__ == "__main__":
    try:
        run(dry_run=False)
    except Exception as e:
        print(f"❌ TELEGRAM SEND FAILED: {e}")
        _audit_failure(str(e))
        raise
