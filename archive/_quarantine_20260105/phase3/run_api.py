"""Programmatic API runner to surface startup errors and avoid reload issues.

Adds Windows event loop policy and robust exception reporting so we can see
precise tracebacks when startup fails.
"""
import os
import sys
import asyncio
import traceback
import uvicorn
from ufa.api.main import app

def main():
    # Ensure a compatible event loop policy on Windows
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            # Older Python versions may not have this policy; ignore if unavailable
            pass

    # Run uvicorn and surface any exceptions cleanly
    try:
        host = os.getenv("API_HOST", "127.0.0.1")
        port = int(os.getenv("API_PORT", "8000"))
        level = os.getenv("API_LOG_LEVEL", "debug")

        os.makedirs("outputs", exist_ok=True)
        with open("outputs/run_api_debug.txt", "w", encoding="utf-8") as fh:
            fh.write(f"[run_api] Preparing uvicorn server on http://{host}:{port} (log={level})\n")
            fh.flush()

            config = uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level=level,
                reload=False,
                loop="asyncio",
                http="h11",
                lifespan="off",
                workers=1,
            )
            server = uvicorn.Server(config)
            fh.write("[run_api] Starting server.run()...\n")
            fh.flush()
            ok = server.run()
            fh.write(f"[run_api] server.run() returned: {ok}\n")
            fh.flush()
    except Exception as exc:
        with open("outputs/run_api_debug.txt", "a", encoding="utf-8") as fh:
            fh.write(f"[run_api] Uvicorn failed to start: {exc}\n")
            fh.write("\n" + traceback.format_exc() + "\n")
        print("[run_api] Uvicorn failed to start:", exc)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
