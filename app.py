"""
FastAPI backend for the market data dashboard.
Wraps market_data.py fetchers with simple in-memory caching (so the frontend can
poll frequently without hammering NSE/BSE/Yahoo) and serves the static frontend.
"""

import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import market_data as md

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Market Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- simple TTL cache ----------------
_cache = {}
_locks = {}


def _get_lock(key):
    if key not in _locks:
        _locks[key] = threading.Lock()
    return _locks[key]


def cached(key, ttl_seconds, fn):
    """Returns {"data": ..., "error": None, "stale": bool, "fetched_at": ts} using a
    per-key lock so concurrent requests don't trigger duplicate slow fetches."""
    now = time.time()
    entry = _cache.get(key)
    if entry and now - entry["fetched_at"] < ttl_seconds:
        return entry

    with _get_lock(key):
        entry = _cache.get(key)
        if entry and time.time() - entry["fetched_at"] < ttl_seconds:
            return entry
        try:
            data = fn()
            entry = {"data": data, "error": None, "fetched_at": time.time()}
        except Exception as e:
            if entry:
                entry = {**entry, "error": str(e), "stale": True}
            else:
                entry = {"data": None, "error": str(e), "fetched_at": time.time()}
        _cache[key] = entry
        return entry


def envelope(entry):
    return {
        "data": entry.get("data"),
        "error": entry.get("error"),
        "fetched_at": entry.get("fetched_at"),
    }


# ---------------- endpoints ----------------
@app.get("/api/indices")
def api_indices():
    return envelope(cached("indices", 30, md.fetch_index_data))


@app.get("/api/nifty-chart")
def api_nifty_chart(period: str = "1d"):
    if period not in md.NIFTY_CHART_PERIODS:
        period = "1d"
    return envelope(cached(f"nifty_chart_{period}", 60, lambda: md.fetch_nifty_chart(period)))


@app.get("/api/fii-dii")
def api_fii_dii():
    entry = cached("fii_dii", 300, md.fetch_fii_dii_data)
    result = envelope(entry)
    if result["data"]:
        result["fresh"] = md.is_fii_dii_data_fresh(result["data"])
    return result


@app.get("/api/currency")
def api_currency():
    return envelope(cached("currency", 30, md.fetch_currency_rates))


@app.get("/api/commodities")
def api_commodities():
    def fetch():
        data, warning = md.fetch_commodities_data()
        return {"items": data, "warning": warning}
    return envelope(cached("commodities", 60, fetch))


@app.get("/api/news")
def api_news():
    return envelope(cached("news", 120, md.fetch_pulse_news))


@app.get("/api/52-week-high")
def api_52wh():
    def fetch():
        list_52wh, list_ath = md.scan_52_week_high()
        return {"week52": list_52wh, "all_time": list_ath}
    return envelope(cached("52wh", 900, fetch))


@app.get("/api/results-calendar")
def api_results():
    def fetch():
        rows, warning = md.scan_results_calendar()
        today_str, tomorrow_str = md._target_result_dates()
        return {"rows": rows, "warning": warning, "today": today_str, "tomorrow": tomorrow_str}
    return envelope(cached("results", 900, fetch))


@app.get("/api/slbm")
def api_slbm():
    def fetch():
        rows, warnings = md.fetch_slbm_data()
        matches = md.filter_slbm_opportunities(rows)
        return {"matches": matches, "warnings": warnings}
    return envelope(cached("slbm", 900, fetch))


@app.get("/api/status")
def api_status():
    return {"is_trading_day": md.is_trading_day()}


# ---------------- static frontend ----------------
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
