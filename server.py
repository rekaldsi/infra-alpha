"""
InfraAlpha Portal — server.py
Flask backend for the InfraAlpha stock intelligence portal.
Serves the UI + API for watchlist management, VWAP scanning, and macro data.
"""

import json
import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

PORT = int(os.getenv("PORT", 8083))
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

WATCHLIST_FILE = DATA_DIR / "watchlist.json"
SIGNALS_FILE   = DATA_DIR / "signals.json"

CST = ZoneInfo("America/Chicago")

# ── In-memory quote cache (avoid hammering yfinance) ─────────────────────────
_quote_cache: dict = {}
_vwap_cache:  dict = {}
_macro_cache: dict = {}
QUOTE_TTL  = 60    # seconds
VWAP_TTL   = 300   # 5 minutes
MACRO_TTL  = 120   # 2 minutes

# Frank's complete master watchlist — 27 tickers (Data Center Infra theme)
# Source: InfraAlpha PRD.md + Telegram group calls (2026-04-17)
STARTER_WATCHLIST = [
    # TIER 1 — Highest Conviction (core DC infra)
    {"symbol": "VRT",   "added_by": "Frank", "notes": "TIER 1 — Vertiv. Pure-play power/cooling for DC. $15B backlog, 252% YoY order growth.", "active": True},
    {"symbol": "GEV",   "added_by": "Frank", "notes": "TIER 1 — GE Vernova. $150B backlog, largest turbine base. Grid can't power AI without them.", "active": True},
    {"symbol": "CMI",   "added_by": "Frank", "notes": "TIER 1 — Cummins. #1 EBITDA 22%+, order book locked to 2028. Boring and dominant.", "active": True},
    {"symbol": "ETN",   "added_by": "Frank", "notes": "TIER 1 — Eaton. Power mgmt + liquid cooling (Boyd acquisition). Infrastructure backbone.", "active": True},
    {"symbol": "MOD",   "added_by": "Frank", "notes": "TIER 1 — Modine. Small cap, pure thermal mgmt for DC. Higher R/R vs ETN/VRT.", "active": True},
    {"symbol": "ABB",   "added_by": "Frank", "notes": "TIER 1 — ABB Ltd. Electrification & automation. Deep data center exposure.", "active": True},
    {"symbol": "TT",    "added_by": "Frank", "notes": "TIER 1 — Trane Technologies. HVAC/cooling. $7.8B backlog, 120%+ applied bookings.", "active": True},
    {"symbol": "NVT",   "added_by": "Frank", "notes": "TIER 1 — nVent Electric. Enclosures, thermal mgmt, electrical infra for DC.", "active": True},
    # TIER 2 — Strong but diluted exposure
    {"symbol": "GNRC",  "added_by": "Frank", "notes": "TIER 2 — Generac. DC backlog doubled, C&I +30% 2026. Still has residential DNA.", "active": True},
    {"symbol": "CAT",   "added_by": "Frank", "notes": "TIER 2 — Caterpillar. DC revenue doubling. Diversified = slower upside.", "active": True},
    {"symbol": "HON",   "added_by": "Frank", "notes": "TIER 2 — Honeywell. Building automation + industrial. Steady, not high-beta.", "active": True},
    {"symbol": "JCI",   "added_by": "Frank", "notes": "TIER 2 — Johnson Controls. Building automation, HVAC, fire/security. Solid.", "active": True},
    {"symbol": "FIX",   "added_by": "Frank", "notes": "TIER 2 — Comfort Systems. Under radar mech/electrical contractor. Heavy DC buildout.", "active": True},
    {"symbol": "SBGSF", "added_by": "Frank", "notes": "TIER 2 — Schneider Electric. Energy mgmt. Global DC standard. OTC, watch liquidity.", "active": True},
    {"symbol": "SIE",   "added_by": "Frank", "notes": "TIER 2 — Siemens AG. Building automation, industrial, energy. OTC liquidity friction.", "active": True},
    {"symbol": "ATLKY", "added_by": "Frank", "notes": "TIER 2 — Atlas Copco. Compressors, vacuum tech, power gen. OTC.", "active": True},
    {"symbol": "FTV",   "added_by": "Frank", "notes": "TIER 2 — Fortive. Industrial tech, sensors, facility instrumentation.", "active": True},
    {"symbol": "APG",   "added_by": "Frank", "notes": "TIER 2 — API Group. Fire protection, safety, HVAC services.", "active": True},
    {"symbol": "MSA",   "added_by": "Frank", "notes": "TIER 2 — MSA Safety. Safety equipment, gas detection, facility monitoring.", "active": True},
    # TIER 3 — REIT / Facility services
    {"symbol": "DLR",   "added_by": "Frank", "notes": "TIER 3 — Digital Realty. Frank's primary call. Colocation REIT. Rate cuts = tailwind.", "active": True},
    {"symbol": "CBRE",  "added_by": "Frank", "notes": "TIER 3 — CBRE Group. Largest CRE firm, deep DC portfolio. Indirect diversifier.", "active": True},
    {"symbol": "JLL",   "added_by": "Frank", "notes": "TIER 3 — Jones Lang LaSalle. Facility mgmt for DC operators. Indirect.", "active": True},
    {"symbol": "CWK",   "added_by": "Frank", "notes": "TIER 3 — Cushman & Wakefield. DC facility mgmt. Indirect diversifier.", "active": True},
    # TIER 4 — Watch / mixed
    {"symbol": "CARR",  "added_by": "Frank", "notes": "TIER 4 — Carrier. 50% residential dilution. Thesis diluted. Watch only.", "active": True},
    {"symbol": "SNDK",  "added_by": "Frank", "notes": "TIER 4 — SanDisk. Storage play, post-WD spinoff. Still forming. Watch.", "active": True},
    # Benchmarks
    {"symbol": "SPY",   "added_by": "System", "notes": "Benchmark — S&P 500", "active": True},
    {"symbol": "QQQ",   "added_by": "System", "notes": "Benchmark — Nasdaq 100", "active": True},
]


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))


def init_data():
    if not WATCHLIST_FILE.exists():
        now = datetime.now(CST).isoformat()
        wl = [{**s, "added_at": now} for s in STARTER_WATCHLIST]
        save_json(WATCHLIST_FILE, wl)
    if not SIGNALS_FILE.exists():
        save_json(SIGNALS_FILE, [])


init_data()


# ── yfinance helpers ──────────────────────────────────────────────────────────

def fetch_quote(symbol: str) -> dict:
    now = time.time()
    if symbol in _quote_cache and now - _quote_cache[symbol].get("_ts", 0) < QUOTE_TTL:
        return _quote_cache[symbol]
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        hist = t.history(period="5d")
        if hist is None or len(hist) < 2:
            return {"symbol": symbol, "error": "no data"}
        last  = float(hist["Close"].iloc[-1])
        prev  = float(hist["Close"].iloc[-2])
        chg   = round(last - prev, 2)
        chgPct = round((chg / prev) * 100, 2) if prev else 0
        result = {
            "symbol": symbol,
            "price": round(last, 2),
            "change": chg,
            "changePct": chgPct,
            "_ts": now,
        }
        _quote_cache[symbol] = result
        return result
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def fetch_vwap_setup(symbol: str) -> dict:
    now = time.time()
    if symbol in _vwap_cache and now - _vwap_cache[symbol].get("_ts", 0) < VWAP_TTL:
        return _vwap_cache[symbol]
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period="1d", interval="5m")
        if df is None or len(df) < 10:
            return {"symbol": symbol, "setup": False, "grade": "NONE", "_ts": now}

        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        vwap = (typical * df["Volume"]).cumsum() / df["Volume"].cumsum()

        last_close = float(df["Close"].iloc[-1])
        last_vwap  = float(vwap.iloc[-1])
        last_open  = float(df["Open"].iloc[-1])
        last_vol   = float(df["Volume"].iloc[-1])
        avg_vol    = float(df["Volume"].iloc[-20:].mean()) if len(df) >= 20 else float(df["Volume"].mean())

        above_vwap = last_close > last_vwap
        if not above_vwap:
            result = {"symbol": symbol, "setup": False, "grade": "NONE",
                      "vwap": round(last_vwap, 2), "price": round(last_close, 2),
                      "reason": "price below VWAP", "_ts": now}
            _vwap_cache[symbol] = result
            return result

        # Pullback — any of last 3 bars touched within 0.3% of VWAP
        recent_lows = list(df["Low"].iloc[-4:-1])
        recent_vwaps = [float(vwap.iloc[-(4 - i)]) for i in range(len(recent_lows))]
        touched = any(
            abs(low - v) / v < 0.003
            for low, v in zip(recent_lows, recent_vwaps)
        )
        if not touched:
            result = {"symbol": symbol, "setup": False, "grade": "NONE",
                      "vwap": round(last_vwap, 2), "price": round(last_close, 2),
                      "reason": "no pullback to VWAP", "_ts": now}
            _vwap_cache[symbol] = result
            return result

        # Rejection candle
        if last_close <= last_open:
            result = {"symbol": symbol, "setup": False, "grade": "NONE",
                      "vwap": round(last_vwap, 2), "price": round(last_close, 2),
                      "reason": "no bullish rejection candle", "_ts": now}
            _vwap_cache[symbol] = result
            return result

        # Volume confirmation
        vol_spike = last_vol / avg_vol if avg_vol > 0 else 0
        if vol_spike < 1.5:
            result = {"symbol": symbol, "setup": False, "grade": "NONE",
                      "vwap": round(last_vwap, 2), "price": round(last_close, 2),
                      "reason": f"volume too low ({vol_spike:.1f}x baseline)", "_ts": now}
            _vwap_cache[symbol] = result
            return result

        grade = "HIGH" if vol_spike >= 3.0 else "MEDIUM"
        pct_above = round(((last_close - last_vwap) / last_vwap) * 100, 2)
        result = {
            "symbol": symbol,
            "setup": True,
            "grade": grade,
            "price": round(last_close, 2),
            "vwap": round(last_vwap, 2),
            "pct_above_vwap": pct_above,
            "vol_spike": round(vol_spike, 1),
            "_ts": now,
        }
        _vwap_cache[symbol] = result
        return result
    except Exception as e:
        return {"symbol": symbol, "setup": False, "grade": "NONE", "error": str(e), "_ts": time.time()}


def fetch_macro() -> dict:
    now = time.time()
    if _macro_cache.get("_ts", 0) and now - _macro_cache["_ts"] < MACRO_TTL:
        return _macro_cache

    result = {}

    # Fear & Greed
    try:
        r = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        d = r.json()["data"][0]
        result["fg_score"] = int(d["value"])
        result["fg_label"] = d["value_classification"]
    except Exception:
        result["fg_score"] = None
        result["fg_label"] = "Unknown"

    # VIX + SPY + QQQ via yfinance
    try:
        import yfinance as yf
        for sym, key in [("^VIX", "vix"), ("SPY", "spy"), ("QQQ", "qqq")]:
            hist = yf.Ticker(sym).history(period="5d")
            if hist is not None and len(hist) >= 2:
                last = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                if key == "vix":
                    result["vix"] = round(last, 2)
                else:
                    result[f"{key}_pct"] = round(((last - prev) / prev) * 100, 2)
    except Exception:
        pass

    # BTC dominance
    try:
        r = httpx.get("https://api.coingecko.com/api/v3/global", timeout=8)
        d = r.json()["data"]
        result["btc_dom"] = round(d["market_cap_percentage"]["btc"], 1)
        result["mcap_change_24h"] = round(d["market_cap_change_percentage_24h_usd"], 2)
    except Exception:
        pass

    # Today's bias
    vix   = result.get("vix", 20)
    fg    = result.get("fg_score", 50)
    mcap  = result.get("mcap_change_24h", 0)
    btcdom = result.get("btc_dom", 55)

    score = 0
    if vix < 18:   score += 2
    elif vix < 22: score += 1
    elif vix > 28: score -= 2
    elif vix > 24: score -= 1
    if fg and fg > 60:   score += 2
    elif fg and fg > 45: score += 1
    elif fg and fg < 25: score -= 2
    elif fg and fg < 35: score -= 1
    if mcap > 3:   score += 2
    elif mcap > 1: score += 1
    elif mcap < -3: score -= 2
    elif mcap < -1: score -= 1
    if btcdom > 60: score -= 1
    elif btcdom < 50: score += 1

    if score >= 3:    result["bias"] = "MEMECOINS 🚀"
    elif score >= 1:  result["bias"] = "MIXED — Lean Crypto"
    elif score == 0:  result["bias"] = "BALANCED"
    elif score >= -2: result["bias"] = "MIXED — Lean Stocks"
    else:             result["bias"] = "STOCKS / CASH 🛡️"

    result["_ts"] = now
    _macro_cache.update(result)
    return result


# ── API Routes ────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok", "ts": datetime.now(CST).isoformat()})


@app.route("/api/watchlist", methods=["GET"])
def get_watchlist():
    wl = load_json(WATCHLIST_FILE, [])
    active = [s for s in wl if s.get("active", True)]
    return jsonify(active)


@app.route("/api/watchlist", methods=["POST"])
def add_to_watchlist():
    data = request.get_json() or {}
    symbol = (data.get("symbol") or "").strip().upper()
    if not symbol:
        return jsonify({"error": "symbol required"}), 400

    wl = load_json(WATCHLIST_FILE, [])
    # Check if already exists
    existing = next((s for s in wl if s["symbol"] == symbol and s.get("active")), None)
    if existing:
        return jsonify({"error": f"{symbol} already in watchlist"}), 409

    entry = {
        "symbol":   symbol,
        "added_by": data.get("added_by", "Frank"),
        "added_at": datetime.now(CST).isoformat(),
        "notes":    data.get("notes", ""),
        "active":   True,
    }
    wl.append(entry)
    save_json(WATCHLIST_FILE, wl)

    # Log to signals
    signals = load_json(SIGNALS_FILE, [])
    signals.insert(0, {
        "ts":      datetime.now(CST).isoformat(),
        "symbol":  symbol,
        "type":    "watchlist_add",
        "message": f"{entry['added_by']} added {symbol} to watchlist" + (f" — {entry['notes']}" if entry['notes'] else ""),
        "source":  entry["added_by"],
    })
    save_json(SIGNALS_FILE, signals[:200])  # keep last 200

    return jsonify({"ok": True, "entry": entry})


@app.route("/api/watchlist/<symbol>", methods=["DELETE"])
def remove_from_watchlist(symbol):
    symbol = symbol.upper()
    wl = load_json(WATCHLIST_FILE, [])
    found = False
    for s in wl:
        if s["symbol"] == symbol and s.get("active"):
            s["active"] = False
            found = True
    if not found:
        return jsonify({"error": f"{symbol} not found"}), 404
    save_json(WATCHLIST_FILE, wl)
    return jsonify({"ok": True})


@app.route("/api/quote/<symbol>")
def get_quote(symbol):
    return jsonify(fetch_quote(symbol.upper()))


@app.route("/api/quotes")
def get_quotes():
    """Batch quotes for the entire watchlist"""
    wl = load_json(WATCHLIST_FILE, [])
    symbols = [s["symbol"] for s in wl if s.get("active")]
    results = []
    for sym in symbols:
        q = fetch_quote(sym)
        vwap = fetch_vwap_setup(sym)
        q["vwap_setup"] = vwap.get("setup", False)
        q["vwap_grade"] = vwap.get("grade", "NONE")
        q["vwap_price"] = vwap.get("vwap")
        results.append(q)
    return jsonify(results)


@app.route("/api/vwap-scan")
def vwap_scan():
    wl = load_json(WATCHLIST_FILE, [])
    symbols = [s["symbol"] for s in wl if s.get("active")]
    setups = []
    for sym in symbols:
        v = fetch_vwap_setup(sym)
        if v.get("setup"):
            setups.append(v)
    setups.sort(key=lambda x: x.get("vol_spike", 0), reverse=True)
    return jsonify(setups)


@app.route("/api/macro")
def get_macro():
    return jsonify(fetch_macro())


@app.route("/api/signals", methods=["GET"])
def get_signals():
    limit = int(request.args.get("limit", 50))
    signals = load_json(SIGNALS_FILE, [])
    return jsonify(signals[:limit])


@app.route("/api/signals", methods=["POST"])
def add_signal():
    data = request.get_json() or {}
    signals = load_json(SIGNALS_FILE, [])
    entry = {
        "ts":      data.get("ts", datetime.now(CST).isoformat()),
        "symbol":  data.get("symbol", ""),
        "type":    data.get("type", "info"),
        "message": data.get("message", ""),
        "source":  data.get("source", "bot"),
    }
    signals.insert(0, entry)
    save_json(SIGNALS_FILE, signals[:200])
    return jsonify({"ok": True})


@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


if __name__ == "__main__":
    print(f"[InfraAlpha] Starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
