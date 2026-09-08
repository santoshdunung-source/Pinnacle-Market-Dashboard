"""
Market data fetchers for the dashboard.
Sources: Yahoo Finance, NSE, BSE, TradingEconomics, Zerodha Pulse.
Pure data functions — no messaging/notification code here.
"""

import re
import time
from datetime import date, datetime, timedelta

import requests
import yfinance as yf
from bs4 import BeautifulSoup

# ---------------- INDICES ----------------
INDICES = {
    "Nifty 50": "^NSEI",
    "Nifty Bank": "^NSEBANK",
    "Nifty IT": "^CNXIT",
    "Nifty Auto": "^CNXAUTO",
    "Nifty Pharma": "^CNXPHARMA",
    "Nifty FMCG": "^CNXFMCG",
    "Nifty Metal": "^CNXMETAL",
    "Nifty Midcap 150": "NIFTYMIDCAP150.NS",
    "Nifty Smallcap 250": "NIFTYSMLCAP250.NS",
    "Sensex": "^BSESN",
}

NSE_ALLINDICES_MAP = {
    "Nifty 50": "NIFTY 50",
    "Nifty Bank": "NIFTY BANK",
    "Nifty IT": "NIFTY IT",
    "Nifty Auto": "NIFTY AUTO",
    "Nifty Pharma": "NIFTY PHARMA",
    "Nifty FMCG": "NIFTY FMCG",
    "Nifty Metal": "NIFTY METAL",
    "Nifty Midcap 150": "NIFTY MIDCAP 150",
    "Nifty Smallcap 250": "NIFTY SMALLCAP 250",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _first_present(d, keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def fetch_nse_all_indices():
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/market-data/live-market-indices",
    })
    session.get("https://www.nseindia.com", timeout=10)
    time.sleep(1)

    resp = session.get("https://www.nseindia.com/api/allIndices", timeout=10)
    if "application/json" not in resp.headers.get("Content-Type", ""):
        raise RuntimeError(f"NSE allIndices not JSON (status {resp.status_code}).")

    payload = resp.json()
    by_nse_name = {row.get("index"): row for row in payload.get("data", [])}

    results = {}
    for display_name, nse_name in NSE_ALLINDICES_MAP.items():
        row = by_nse_name.get(nse_name)
        if row and row.get("last") is not None:
            results[display_name] = {
                "close": round(float(row["last"]), 2),
                "change": round(float(row.get("variation", 0)), 2),
                "pchange": round(float(row.get("percentChange", 0)), 2),
            }
    return results


def fetch_bse_sensex_live():
    resp = requests.get(
        "https://api.bseindia.com/BseIndiaAPI/api/GetLinknew/w?code=16",
        headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                 "Referer": "https://www.bseindia.com/"},
        timeout=10,
    )
    if "application/json" not in resp.headers.get("Content-Type", ""):
        raise RuntimeError(f"BSE Sensex feed not JSON (status {resp.status_code}).")

    data = resp.json()
    if isinstance(data, list) and data:
        data = data[0]

    last = _first_present(data, ["LTP", "CurrValue", "Last", "LastPrice", "last", "ltp"])
    change = _first_present(data, ["Chg", "Change", "chg", "change", "Chg_prc"])
    pchange = _first_present(data, ["PerChg", "PerChange", "perchange", "ChgPer", "pChange", "per_change"])

    if last is None:
        raise RuntimeError("Couldn't find a recognizable price field in BSE's Sensex response.")

    def _to_float(v):
        if v in (None, ""):
            return 0.0
        return float(str(v).replace(",", ""))

    return {"close": round(_to_float(last), 2), "change": round(_to_float(change), 2),
             "pchange": round(_to_float(pchange), 2)}


def fetch_index_data():
    results = {}
    nse_bulk = {}
    try:
        nse_bulk = fetch_nse_all_indices()
    except Exception as e:
        print(f"NSE allIndices bulk fetch failed, falling back to Yahoo Finance: {e}")

    for name, ticker in INDICES.items():
        if name == "Sensex":
            try:
                results[name] = fetch_bse_sensex_live()
                continue
            except Exception as e:
                print(f"BSE Sensex feed failed, falling back to Yahoo Finance: {e}")
        elif name in nse_bulk:
            results[name] = nse_bulk[name]
            continue

        try:
            t = yf.Ticker(ticker)
            fi = t.fast_info
            last_price = fi.get("lastPrice") or fi.get("last_price")
            prev_close = fi.get("previousClose") or fi.get("previous_close")

            if last_price is None or prev_close is None:
                hist = t.history(period="5d")
                if hist.empty:
                    results[name] = None
                    continue
                last_price = hist["Close"].iloc[-1]
                prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else last_price

            change = last_price - prev_close
            pchange = (change / prev_close) * 100 if prev_close else 0
            results[name] = {
                "close": round(last_price, 2),
                "change": round(change, 2),
                "pchange": round(pchange, 2),
            }
        except Exception as e:
            print(f"Failed to fetch {name} ({ticker}): {e}")
            results[name] = None
    return results


# ---------------- NIFTY CHART ----------------
NIFTY_CHART_PERIODS = {
    "1d": {"period": "1d", "interval": "5m"},
    "5d": {"period": "5d", "interval": "15m"},
    "1mo": {"period": "1mo", "interval": "1d"},
}


def fetch_nifty_chart(period="1d"):
    """Returns {"labels": [...], "values": [...]} of Nifty 50 close prices from
    Yahoo Finance for the given period — one of "1d", "5d", "1mo"."""
    cfg = NIFTY_CHART_PERIODS.get(period, NIFTY_CHART_PERIODS["1d"])
    hist = yf.Ticker("^NSEI").history(period=cfg["period"], interval=cfg["interval"])
    if hist.empty:
        return {"labels": [], "values": []}

    if period == "1mo":
        labels = [ts.strftime("%d %b") for ts in hist.index]
    else:
        labels = [ts.strftime("%d %b %H:%M") for ts in hist.index]

    values = [round(float(v), 2) for v in hist["Close"]]
    return {"labels": labels, "values": values}


# ---------------- FII/DII ----------------
def fetch_fii_dii_data():
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/reports/fii-dii",
    })
    session.get("https://www.nseindia.com", timeout=10)
    time.sleep(1)
    session.get("https://www.nseindia.com/reports/fii-dii", timeout=10)
    time.sleep(1)

    resp = session.get("https://www.nseindia.com/api/fiidiiTradeReact", timeout=10)
    if "application/json" not in resp.headers.get("Content-Type", ""):
        raise RuntimeError(f"NSE did not return JSON for FII/DII data (status {resp.status_code}).")

    rows = resp.json()
    result = {}
    for row in rows:
        category = row.get("category", "")
        entry = {
            "date": row.get("date"),
            "buy": float(row.get("buyValue", 0)),
            "sell": float(row.get("sellValue", 0)),
            "net": float(row.get("netValue", 0)),
        }
        if "DII" in category.upper():
            result["DII"] = entry
        elif "FII" in category.upper() or "FPI" in category.upper():
            result["FII"] = entry
    return result


def _parse_flexible_date(date_str):
    if not date_str:
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt).date()
        except ValueError:
            continue
    return None


def is_fii_dii_data_fresh(data):
    today = date.today()
    for label in ("FII", "DII"):
        row = data.get(label)
        if row and _parse_flexible_date(row.get("date")) == today:
            return True
    return False


# ---------------- SLBM ----------------
SLBM_MIN_YIELD_PCT = 4
SLBM_MIN_VOLUME = 1000
SLBM_MIN_OPEN_POSITIONS = 10000
SLBM_MONTHS_AHEAD = 2


def _slbm_target_months(months_ahead=SLBM_MONTHS_AHEAD):
    today = date.today()
    targets = []
    for i in range(1, months_ahead + 1):
        m = today.month + i
        y = today.year
        while m > 12:
            m -= 12
            y += 1
        targets.append((m, y))
    return targets


def fetch_slbm_series_codes(session):
    resp = session.get("https://www.nseindia.com/api/live-analysis-slb-series-master", timeout=10)
    if "application/json" not in resp.headers.get("Content-Type", ""):
        raise RuntimeError(f"NSE didn't return JSON for SLB series master (status {resp.status_code}).")
    payload = resp.json()
    series_b = payload.get("data", {}).get("Series B", [])
    mapping = {}
    for entry in series_b:
        label = entry.get("value", "")
        if "**" in label:
            continue
        mapping[label] = entry.get("key")
    return mapping


def fetch_slbm_data():
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/market-data/securities-lending-and-borrowing",
    })
    session.get("https://www.nseindia.com", timeout=10)
    time.sleep(1)
    session.get("https://www.nseindia.com/market-data/securities-lending-and-borrowing", timeout=10)
    time.sleep(1)

    all_rows = []
    warnings = []

    try:
        series_map = fetch_slbm_series_codes(session)
    except Exception as e:
        return [], [f"Couldn't fetch SLB series list from NSE: {e}"]
    time.sleep(1)

    for month, year in _slbm_target_months():
        expected_label = date(year, month, 1).strftime("%b-%Y")
        code = series_map.get(expected_label)

        if not code:
            warnings.append(f"No series code found for {expected_label} in NSE's master list.")
            continue

        url = f"https://www.nseindia.com/api/live-analysis-slb?series={code}"
        try:
            resp = session.get(url, timeout=10)
        except Exception as e:
            warnings.append(f"{expected_label} (series {code}): request failed — {e}")
            continue

        if "application/json" not in resp.headers.get("Content-Type", ""):
            warnings.append(f"{expected_label} (series {code}): NSE didn't return JSON (status {resp.status_code})")
            continue

        payload = resp.json()
        actual_label = payload.get("meta", "")
        if actual_label and actual_label != expected_label:
            warnings.append(f"Series code {code} returned '{actual_label}', expected '{expected_label}'.")

        for row in payload.get("data", []):
            row["_expiry_label"] = actual_label or expected_label
            all_rows.append(row)

        time.sleep(1)

    return all_rows, warnings


def filter_slbm_opportunities(rows):
    matches = []
    for row in rows:
        try:
            yield_pct = float(row.get("annualisedYieldPer") or 0)
            volume = float(row.get("volume") or 0)
            open_positions = float(row.get("openPositions") or 0)
        except (TypeError, ValueError):
            continue
        if (yield_pct > SLBM_MIN_YIELD_PCT and volume > SLBM_MIN_VOLUME
                and open_positions > SLBM_MIN_OPEN_POSITIONS):
            matches.append(row)
    matches.sort(key=lambda r: float(r.get("annualisedYieldPer") or 0), reverse=True)
    return matches


# ---------------- 52-WEEK HIGH / ALL-TIME HIGH ----------------
def fetch_52_week_high_candidates():
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/market-data/52-week-high-equity-market",
    })
    session.get("https://www.nseindia.com", timeout=10)
    time.sleep(1)
    session.get("https://www.nseindia.com/market-data/52-week-high-equity-market", timeout=10)
    time.sleep(1)

    resp = session.get("https://www.nseindia.com/api/live-analysis-data-52weekhighstock", timeout=10)
    if "application/json" not in resp.headers.get("Content-Type", ""):
        raise RuntimeError(f"NSE did not return JSON for 52-week-high data (status {resp.status_code}).")

    payload = resp.json()
    return [row for row in payload.get("data", []) if row.get("series") == "EQ"]


def is_all_time_high(symbol, day_high):
    try:
        hist = yf.Ticker(f"{symbol}.NS").history(period="max")
        if hist.empty:
            return None
        historical_max = hist["High"].max()
        return float(day_high) >= historical_max - 0.01
    except Exception:
        return None


def scan_52_week_high():
    list_52wh = fetch_52_week_high_candidates()
    list_ath = []
    for row in list_52wh:
        ath = is_all_time_high(row.get("symbol"), row.get("new52WHL"))
        if ath:
            list_ath.append(row)
        time.sleep(0.3)
    return list_52wh, list_ath


# ---------------- CURRENCY ----------------
CURRENCY_YF_TICKERS = {
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "GBP/USD": "GBPUSD=X",
    "USD/CHF": "CHF=X",
    "USD/INR": "INR=X",
}


def fetch_currency_rates():
    results = {}
    for pair, ticker in CURRENCY_YF_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            fi = t.fast_info
            last = fi.get("lastPrice") or fi.get("last_price")
            prev = fi.get("previousClose") or fi.get("previous_close")
            if last is None or prev is None:
                results[pair] = None
                continue
            chg = last - prev
            pchg = (chg / prev) * 100 if prev else 0
            results[pair] = {"last": round(last, 4), "chg": round(chg, 4), "pchg": round(pchg, 2)}
        except Exception as e:
            print(f"[/currency] Failed to fetch {pair} ({ticker}): {e}")
            results[pair] = None
    return results


# ---------------- NEWS (Zerodha Pulse) ----------------
NEWS_MAX_AGE_MINUTES = 120
NEWS_MAX_ITEMS = 15
NEWS_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "is", "are", "at", "by",
    "as", "with", "after", "before", "from", "its", "it's", "that", "this", "will",
    "has", "have", "had", "be", "was", "were", "up", "down", "over", "under", "amid",
    "says", "said", "not", "into", "than", "but", "how", "why", "who", "what",
}
NEWS_DEDUPE_THRESHOLD = 0.5


def _parse_relative_age_minutes(text):
    m = re.search(r'\b(a|an|\d+(?:\.\d+)?)\s*(minute|minutes|hour|hours|day|days)\s+ago', text, re.I)
    if not m:
        return None
    raw_value = m.group(1).lower()
    value = 1.0 if raw_value in ("a", "an") else float(raw_value)
    unit = m.group(2).lower()
    if unit.startswith("minute"):
        return value
    if unit.startswith("hour"):
        return value * 60
    if unit.startswith("day"):
        return value * 60 * 24
    return None


def _significant_words(title):
    words = re.findall(r"[a-zA-Z0-9]+", title.lower())
    return {w for w in words if w not in NEWS_STOPWORDS and len(w) > 2}


def _headline_overlap(words_a, words_b):
    if not words_a or not words_b:
        return 0.0
    smaller = min(len(words_a), len(words_b))
    return len(words_a & words_b) / smaller


def _dedupe_similar_headlines(items):
    kept, kept_words = [], []
    for item in items:
        words = _significant_words(item["title"])
        is_dup = any(_headline_overlap(words, kw) >= NEWS_DEDUPE_THRESHOLD for kw in kept_words)
        if not is_dup:
            kept.append(item)
            kept_words.append(words)
    return kept


def fetch_pulse_news():
    resp = requests.get(
        "https://pulse.zerodha.com/",
        headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    all_items = []
    for li in soup.find_all("li"):
        title_tag = li.find(["h1", "h2", "h3"])
        link_tag = (title_tag.find("a") if title_tag else None) or li.find("a")
        if not link_tag:
            continue
        title = link_tag.get_text(strip=True)
        url = link_tag.get("href")
        if not title or not url or len(title) < 8:
            continue

        li_text = li.get_text(" ", strip=True)
        age_min = _parse_relative_age_minutes(li_text)
        if age_min is None:
            continue

        source_match = re.search(r'ago\s*[—\-–]\s*([A-Za-z0-9 .&\']{2,40})', li_text)
        source = source_match.group(1).strip() if source_match else "Unknown"

        all_items.append({"title": title, "url": url, "age_min": age_min, "source": source})

    recent = [item for item in all_items if item["age_min"] <= NEWS_MAX_AGE_MINUTES]
    recent.sort(key=lambda x: x["age_min"])
    deduped = _dedupe_similar_headlines(recent)
    return deduped[:NEWS_MAX_ITEMS]


# ---------------- COMMODITIES ----------------
COMMODITY_NAMES = ["Crude Oil", "Brent", "Gold", "Silver", "Copper"]


def fetch_commodities_te():
    resp = requests.get(
        "https://tradingeconomics.com/commodities",
        headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    target_lower = {name.lower() for name in COMMODITY_NAMES}
    results = {}
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        link = cells[0].find("a")
        if not link:
            continue
        name = link.get_text(strip=True)
        if name.lower() not in target_lower:
            continue
        try:
            price = float(cells[1].get_text(strip=True).replace(",", ""))
            chg = float(cells[2].get_text(strip=True).replace(",", ""))
            pchg = float(cells[3].get_text(strip=True).replace(",", "").replace("%", ""))
            results[name] = {"price": price, "chg": chg, "pchg": pchg}
        except ValueError:
            continue
    return results


def fetch_commodities_data():
    warning = None
    try:
        te_data = fetch_commodities_te()
    except Exception as e:
        return {name: None for name in COMMODITY_NAMES}, f"TradingEconomics fetch failed: {e}"

    results = {}
    missing = []
    for name in COMMODITY_NAMES:
        results[name] = te_data.get(name)
        if results[name] is None:
            missing.append(name)
    if missing:
        warning = f"Not found on TradingEconomics: {', '.join(missing)}."
    return results, warning


# ---------------- EARNINGS RESULTS CALENDAR ----------------
RESULTS_MARKET_CAP_MIN_CR = 5000


def _target_result_dates():
    today = date.today()
    tomorrow = today + timedelta(days=1)
    return today.strftime("%d-%b-%Y"), tomorrow.strftime("%d-%b-%Y")


def fetch_nse_results_candidates():
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-event-calendar",
    })
    session.get("https://www.nseindia.com", timeout=10)
    time.sleep(1)

    today = date.today()
    tomorrow = today + timedelta(days=1)
    from_date = today.strftime("%d-%m-%Y")
    to_date = tomorrow.strftime("%d-%m-%Y")
    url = (f"https://www.nseindia.com/api/event-calendar"
           f"?index=equities&from_date={from_date}&to_date={to_date}")

    resp = session.get(url, timeout=10)
    if "application/json" not in resp.headers.get("Content-Type", ""):
        raise RuntimeError(f"NSE did not return JSON for event calendar (status {resp.status_code}).")

    today_str, tomorrow_str = _target_result_dates()
    rows = resp.json()
    candidates = []
    for row in rows:
        purpose = (row.get("purpose") or "").lower()
        row_date = row.get("date", "")
        if "financial results" in purpose and row_date in (today_str, tomorrow_str):
            candidates.append({
                "symbol": row.get("symbol"),
                "company": row.get("company"),
                "date": row_date,
            })
    return candidates


def fetch_bse_results_candidates():
    resp = requests.get(
        "https://api.bseindia.com/BseIndiaAPI/api/Corpforthresults/w",
        headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                 "Referer": "https://www.bseindia.com/"},
        timeout=10,
    )
    if "application/json" not in resp.headers.get("Content-Type", ""):
        raise RuntimeError(f"BSE did not return JSON for results calendar (status {resp.status_code}).")

    payload = resp.json()
    rows = payload if isinstance(payload, list) else payload.get("Table", payload.get("data", []))

    SYMBOL_KEYS = ["scrip_Code", "scrip_code", "SCRIP_CD", "ScripCode"]
    COMPANY_KEYS = ["Long_Name", "short_name", "Short_Name", "SC_NAME"]
    DATE_KEYS = ["meeting_date", "Meeting_Date", "MEETING_DATE"]

    today_str, tomorrow_str = _target_result_dates()
    candidates = []
    for row in rows:
        raw_date = _first_present(row, DATE_KEYS)
        if not raw_date:
            continue
        parsed = None
        for fmt in ("%d %b %Y", "%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(str(raw_date).strip(), fmt).date()
                break
            except ValueError:
                continue
        if not parsed:
            continue
        if parsed.strftime("%d-%b-%Y") not in (today_str, tomorrow_str):
            continue
        candidates.append({
            "symbol": _first_present(row, SYMBOL_KEYS),
            "company": _first_present(row, COMPANY_KEYS),
            "date": parsed.strftime("%d-%b-%Y"),
        })
    return candidates


def _normalize_company_name(name):
    if not name:
        return ""
    name = name.upper()
    name = re.sub(r"[.,'&]", "", name)
    for suffix in (" LIMITED", " LTD", " PVT", " PRIVATE"):
        name = name.replace(suffix, "")
    return re.sub(r"\s+", " ", name).strip()


def get_market_cap_cr(ticker_symbol):
    try:
        t = yf.Ticker(ticker_symbol)
        mcap = None
        try:
            mcap = t.fast_info.get("marketCap") or t.fast_info.get("market_cap")
        except Exception:
            pass
        if not mcap:
            mcap = (t.info or {}).get("marketCap")
        if not mcap:
            return None
        return mcap / 1e7
    except Exception:
        return None


def scan_results_calendar():
    nse_candidates = fetch_nse_results_candidates()

    bse_candidates = []
    bse_warning = None
    try:
        bse_candidates = fetch_bse_results_candidates()
    except Exception as e:
        bse_warning = f"Couldn't fetch BSE results calendar: {e}"

    seen_names = set()
    merged = []
    for row in nse_candidates:
        norm = _normalize_company_name(row.get("company"))
        if norm and norm not in seen_names:
            seen_names.add(norm)
            merged.append({**row, "exchange": "NSE"})

    for row in bse_candidates:
        norm = _normalize_company_name(row.get("company"))
        if norm and norm not in seen_names:
            seen_names.add(norm)
            merged.append({**row, "exchange": "BSE"})

    final = []
    for row in merged:
        ticker = f"{row['symbol']}.NS" if row["exchange"] == "NSE" else f"{row['symbol']}.BO"
        mcap = get_market_cap_cr(ticker)
        time.sleep(0.3)
        if mcap is not None and mcap > RESULTS_MARKET_CAP_MIN_CR:
            row["market_cap_cr"] = mcap
            final.append(row)

    return final, bse_warning


# ---------------- TRADING DAY CHECK ----------------
TRADING_HOLIDAYS_2026 = {
    "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31", "2026-04-03",
    "2026-04-14", "2026-05-01", "2026-05-28", "2026-06-26", "2026-09-14",
    "2026-10-02", "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25",
}


def is_trading_day():
    today = date.today()
    if today.weekday() >= 5:
        return False
    if today.isoformat() in TRADING_HOLIDAYS_2026:
        return False
    return True
