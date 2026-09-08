"""
One-command launcher for the Pinnacle Market Dashboard.

Two ways this runs:
1. As a plain Python script (`python3 run_dashboard.py`, or via
   Start Dashboard.command / .bat) — installs any missing dependencies, then
   starts the server.
2. As a PyInstaller-frozen standalone executable — Python and every
   dependency are already sealed inside, so there's nothing to install at
   all; this file just starts the server directly.

Either way it starts the local server and opens your default browser
automatically. Binds to 127.0.0.1 (this machine only) since each person runs
their own standalone copy — no network exposure, no other device involved.
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8420
URL = f"http://{HOST}:{PORT}"

FROZEN = getattr(sys, "frozen", False)
# Under PyInstaller, __file__ / sys.executable point into the temp bundle
# (or the app's own folder for a --onedir build) — either way this resolves
# to wherever the bundled static/ folder actually lives at runtime.
PROJECT_DIR = Path(__file__).resolve().parent


def ensure_dependencies():
    if FROZEN:
        return  # everything is already sealed into the executable
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import yfinance  # noqa: F401
        import bs4  # noqa: F401
        return
    except ImportError:
        pass

    print("First run — installing dependencies (this happens once)...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--quiet",
        "-r", str(PROJECT_DIR / "requirements.txt"),
    ])


def open_browser_when_ready():
    import urllib.request

    for _ in range(60):
        try:
            urllib.request.urlopen(URL, timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    # webbrowser.open() has no reliable way to open a GUI browser from some
    # environments (Termux on Android, headless setups) — it can fail silently
    # or raise. Either way, the URL printed below is the real fallback.
    try:
        opened = webbrowser.open(URL)
    except Exception:
        opened = False
    if not opened:
        print(f"\nCouldn't open a browser automatically — open this URL yourself:\n  {URL}\n")


def main():
    ensure_dependencies()

    import threading
    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    print(f"Starting Pinnacle Market Dashboard — open {URL} in your browser if it doesn't open automatically.")
    print("Leave this window open while using the dashboard. Close it (or Ctrl+C) to stop.")

    import os
    os.chdir(PROJECT_DIR)
    sys.path.insert(0, str(PROJECT_DIR))

    import uvicorn
    # Import the app object directly rather than uvicorn's "app:app" string
    # loader — the string form relies on Python's normal import machinery
    # finding a module named "app" by name, which PyInstaller's frozen
    # environment doesn't reliably support. A direct import always works,
    # frozen or not.
    from app import app as fastapi_app
    uvicorn.run(fastapi_app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
