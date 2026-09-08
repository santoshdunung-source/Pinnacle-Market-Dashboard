# Market Dashboard

A live dashboard for Indian market data — index levels, FII/DII cash-market
flows, currency rates, commodities, market news, 52-week/all-time highs,
earnings calendar, Nifty chart, and SLBM opportunities.

Runs entirely on your own computer. Nothing is hosted centrally, nothing is
shared with any other device, and no account or API key is needed.

## Use it — nothing to install

**Mac:** run **`dist/Pinnacle Dashboard`**.
**Windows:** run **`dist/Pinnacle Dashboard.exe`** (see "Building the Windows
version" below — it has to be built once on a Windows machine first).

That's it — Python and every dependency are sealed inside this one file.
Double-click it, wait a few seconds, your browser opens the dashboard
automatically. Leave that window open while using it; closing it stops the
server.

**First launch, your OS will warn you** — this is an unsigned program (no
Apple/Microsoft developer certificate attached), so:
- **Mac:** right-click the file → **Open** → confirm. (Double-clicking
  normally will just refuse silently the very first time — right-click once,
  then it opens normally from then on.)
- **Windows:** click **"More info"** on the SmartScreen popup → **"Run
  anyway"**.

This warning is expected for any app outside the App Store/Microsoft Store
without a paid code-signing certificate — it isn't a sign anything is wrong.

## Sharing this with someone else

Send them the one file — `Pinnacle Dashboard` (Mac) or
`Pinnacle Dashboard.exe` (Windows), whichever matches their computer. They
run it the same way. No setup on your end, no dependency on your machine.

## Building the Windows version

PyInstaller (the tool that seals Python into that one file) has to actually
run on the target OS — it can't cross-build a Windows .exe from a Mac. Two
ways to get it:

1. **On any Windows PC, once:**
   ```
   pip install -r requirements.txt pyinstaller
   pyinstaller dashboard.spec --noconfirm
   ```
   Produces `dist/Pinnacle Dashboard.exe`. Copy that file anywhere — it's the
   same zero-install single file described above.

2. **Automatically, via GitHub Actions** (no Windows PC needed at all): push
   this project to a GitHub repo — `.github/workflows/build-windows.yml` is
   already set up to build it on a free Microsoft-hosted Windows runner.
   Trigger it from the Actions tab, then download the resulting `.exe` from
   the finished run.

Either way, it only needs to be built once — from then on it's just a file
you copy and share.

## Live updates

Once open, the dashboard refreshes itself automatically — indices, FII/DII,
currency, commodities and news every 30 seconds; the slower scans (52-week-high,
earnings calendar, SLBM) every 5 minutes. There's nothing to manually refresh;
"Refresh now" is only there as an on-demand override.

## Why it needs a backend at all

NSE, BSE, TradingEconomics, and Zerodha Pulse all block direct requests from
browser JavaScript (no CORS headers, and NSE/BSE additionally require a
cookie handshake to get past bot-detection). That's enforced by the browser
itself — no amount of HTML/JS can route around it. Something has to make
these requests server-side; that backend is what's sealed inside the
executable above.

## Project files

**What you actually run:**
- `dist/Pinnacle Dashboard` — the standalone Mac app (built, ready now)
- `dist/Pinnacle Dashboard.exe` — the standalone Windows app (build once, see above)

**Source / build recipe** (only needed if you're changing the dashboard or
rebuilding it — not needed to just use it):
- `app.py`, `market_data.py` — the backend (FastAPI + the NSE/BSE/Yahoo/
  TradingEconomics/Zerodha fetchers)
- `static/index.html`, `static/logo.png` — the dashboard page and logo
- `run_dashboard.py` — the entry point PyInstaller bundles; also runnable
  directly with a plain Python install (see below)
- `dashboard.spec` — PyInstaller's build recipe
- `requirements.txt` — Python packages needed to run from source or rebuild
- `.github/workflows/build-windows.yml` — cloud Windows build, see above

**Alternative: running from source instead of the executable** — if you'd
rather not run an unsigned binary and already have Python 3.9+ installed,
`Start Dashboard.command` (Mac) / `Start Dashboard.bat` (Windows) do the same
thing by running the Python source directly, installing dependencies on
first run. Functionally identical to the executable; the difference is
purely "one file with nothing pre-installed" vs. "needs Python already on
the machine."

## Notes

- All data is fetched live from public sources (Yahoo Finance, NSE, BSE,
  TradingEconomics, Zerodha Pulse) — nothing is stored, and there's nothing to
  configure per-user.
- NSE/BSE occasionally rate-limit or block requests; if a panel shows an error,
  it usually resolves on the next refresh.
- The 52-week-high and SLBM scans are slow (they check many stocks one by one) and
  are cached for 15 minutes; other panels refresh every 30 seconds.
