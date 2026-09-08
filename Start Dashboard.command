#!/bin/bash
# Double-click this file to start the Pinnacle Market Dashboard.
# It installs dependencies on first run, starts the local server, and opens
# your browser automatically. Runs entirely on this Mac — no other device needed.

cd "$(dirname "$0")"

PYTHON_BIN="python3"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 isn't installed on this Mac."
  echo "Install it from https://www.python.org/downloads/ (or 'brew install python3'), then run this again."
  read -p "Press Return to close..."
  exit 1
fi

"$PYTHON_BIN" run_dashboard.py

echo ""
read -p "Dashboard stopped. Press Return to close this window..."
