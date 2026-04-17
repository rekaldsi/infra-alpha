"""
InfraAlpha Portal — server.py
Flask backend for the InfraAlpha stock intelligence portal.
Persistence: Supabase (infra_watchlist + infra_signals tables)
Same Supabase project as Solana Sniper: uxtlxgjuccodrxhoiswf
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
CST  = ZoneInfo("America/Chicago")

# ── Supabase config ───────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://uxtlxgjuccodrxhoiswf.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV4dGx4Z2p1Y2NvZHJ4aG9pc3dmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjM3MzAyOSwiZXhwIjoyMDkxOTQ5MDI5fQ.qy9XlOPd4QArqt581w6gsz4D3QIKgByR66rZq_ZHy8s")
SB_HEADERS   = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}

def sb_get(path, params=""):
    r = httpx.get(f"{SUPABASE_URL}/rest/v1/{path}{params}", headers=SB_HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()

def sb_post(path, data):
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/{path}", headers=SB_HEADERS, json=data, timeout=10)
    r.raise_for_status()
    return r.json()

def sb_patch(path, data):
    r = httpx.patch(f"{SUPABASE_URL}/rest/v1/{path}", headers=SB_HEADERS, json=data, timeout=10)
    r.raise_for_status()
    return r.json()

def sb_delete(path):
    r = httpx.delete(f"{SUPABASE_URL}/rest/v1/{path}", headers=SB_HEADERS, timeout=10)
    r.raise_for_status()

# ── Seed watchlist if empty ───────────────────────────────────────────────────
STARTER_WATCHLIST = [
    # TIER 1 — Highest Conviction
    {"symbol":"VRT",   "added_by":"Frank",  "notes":"TIER 1 — Vertiv. Pure-play power/cooling for DC. $15B backlog, 252% YoY order growth."},
    {"symbol":"GEV",   "added_by":"Frank",  "notes":"TIER 1 — GE Vernova. $150B backlog, largest turbine base. Grid cannot power AI without them."},
    {"symbol":"CMI",   "added_by":"Frank",  "notes":"TIER 1 — Cummins. #1 EBITDA 22%+, order book locked to 2028. Boring and dominant."},
    {"symbol":"ETN",   "added_by":"Frank",  "notes":"TIER 1 — Eaton. Power mgmt + liquid cooling (Boyd acquisition). Infrastructure backbone."},
    {"symbol":"MOD",   "added_by":"Frank",  "notes":"TIER 1 — Modine. Small cap, pure thermal mgmt for DC. Higher R/R vs ETN/VRT."},
    {"symbol":"ABBNY", "added_by":"Frank",  "notes":"TIER 1 — ABB Ltd ADR (ABBNY). Electrification & automation. Deep data center exposure. US-tradeable ADR."},
    {"symbol":"TT",    "added_by":"Frank",  "notes":"TIER 1 — Trane Technologies. HVAC/cooling. $7.8B backlog, 120%+ applied bookings."},
    {"symbol":"NVT",   "added_by":"Frank",  "notes":"TIER 1 — nVent Electric. Enclosures, thermal mgmt, electrical infra for DC."},
    # TIER 2 — Strong but diluted
    {"symbol":"GNRC",  "added_by":"Frank",  "notes":"TIER 2 — Generac. DC backlog doubled, C&I +30% 2026. Still has residential DNA."},
    {"symbol":"CAT",   "added_by":"Frank",  "notes":"TIER 2 — Caterpillar. DC revenue doubling. Diversified = slower upside."},
    {"symbol":"HON",   "added_by":"Frank",  "notes":"TIER 2 — Honeywell. Building automation + industrial. Steady, not high-beta."},
    {"symbol":"JCI",   "added_by":"Frank",  "notes":"TIER 2 — Johnson Controls. Building automation, HVAC, fire/security. Solid."},
    {"symbol":"FIX",   "added_by":"Frank",  "notes":"TIER 2 — Comfort Systems. Under radar mech/electrical contractor. Heavy DC buildout."},
    {"symbol":"SBGSF", "added_by":"Frank",  "notes":"TIER 2 — Schneider Electric. Energy mgmt. Global DC standard. OTC, watch liquidity."},
    {"symbol":"SIEGY", "added_by":"Frank",  "notes":"TIER 2 — Siemens AG ADR (SIEGY). Building automation, industrial, energy. US-tradeable ADR of SIE.DE."},
    {"symbol":"ATLKY", "added_by":"Frank",  "notes":"TIER 2 — Atlas Copco. Compressors, vacuum tech, power gen. OTC."},
    {"symbol":"FTV",   "added_by":"Frank",  "notes":"TIER 2 — Fortive. Industrial tech, sensors, facility instrumentation."},
    {"symbol":"APG",   "added_by":"Frank",  "notes":"TIER 2 — API Group. Fire protection, safety, HVAC services."},
    {"symbol":"MSA",   "added_by":"Frank",  "notes":"TIER 2 — MSA Safety. Safety equipment, gas detection, facility monitoring."},
    # TIER 3 — REIT / Facility
    {"symbol":"DLR",   "added_by":"Frank",  "notes":"TIER 3 — Digital Realty. Colocation REIT. Rate cuts = tailwind."},
    {"symbol":"CBRE",  "added_by":"Frank",  "notes":"TIER 3 — CBRE Group. Largest CRE firm, deep DC portfolio."},
    {"symbol":"JLL",   "added_by":"Frank",  "notes":"TIER 3 — Jones Lang LaSalle. Facility mgmt for DC operators."},
    {"symbol":"CWK",   "added_by":"Frank",  "notes":"TIER 3 — Cushman & Wakefield. DC facility mgmt. Indirect."},
    # TIER 4 — Watch
    {"symbol":"CARR",  "added_by":"Frank",  "notes":"TIER 4 — Carrier. 50% residential dilution. Watch only."},
    {"symbol":"SNDK",  "added_by":"Frank",  "notes":"TIER 4 — SanDisk. Post-WD spinoff. Still forming. Watch."},
    # Frank's Portfolio
    {"symbol":"COIN",  "added_by":"Frank",  "notes":"Frank's Portfolio — Coinbase. Crypto exchange."},
    # ABBNY already listed under TIER 1 above
    {"symbol":"UROY",  "added_by":"Frank",  "notes":"Frank's Portfolio — Uranium Royalty Corp. Nuclear energy."},
    {"symbol":"BP",    "added_by":"Frank",  "notes":"Frank's Portfolio — BP plc. Oil major. Energy macro hedge."},
    {"symbol":"ANET",  "added_by":"Frank",  "notes":"Frank's Portfolio — Arista Networks. AI networking infra."},
    {"symbol":"ICHR",  "added_by":"Frank",  "notes":"Frank's Portfolio — Ichor Holdings. Chip fab supply chain."},
    {"symbol":"SII",   "added_by":"Frank",  "notes":"Frank's Portfolio — Sprott Inc. Precious metals/uranium funds."},
    {"symbol":"VOO",   "added_by":"Frank",  "notes":"Frank's Portfolio — Vanguard S&P 500 ETF."},
    {"symbol":"VIG",   "added_by":"Frank",  "notes":"Frank's Portfolio — Vanguard Dividend Appreciation ETF."},
    {"symbol":"AGG",   "added_by":"Frank",  "notes":"Frank's Portfolio — iShares US Aggregate Bond ETF."},
    {"symbol":"AMD",   "added_by":"Frank",  "notes":"Frank's Portfolio — Advanced Micro Devices. AI chips, GPU."},
    {"symbol":"ET",    "added_by":"Frank",  "notes":"Frank's Portfolio — Energy Transfer LP. Midstream pipeline."},
    {"symbol":"NVDA",  "added_by":"Frank",  "notes":"Frank's Portfolio — NVIDIA. AI chips, GPU compute bellwether."},
    {"symbol":"ONDS",  "added_by":"Frank",  "notes":"Frank's Portfolio — Ondas Holdings. Autonomous drone/rail tech."},
    {"symbol":"RNMBY", "added_by":"Frank",  "notes":"Frank's Portfolio — Rheinmetall AG ADR. German defense/auto."},
    {"symbol":"GLD",   "added_by":"Frank",  "notes":"Frank's Portfolio — SPDR Gold Trust. Gold hedge."},
    {"symbol":"UEC",   "added_by":"Frank",  "notes":"Frank's Portfolio — Uranium Energy Corp. Nuclear energy."},
    {"symbol":"BNS",   "added_by":"Frank",  "notes":"Frank's Portfolio — Bank of Nova Scotia. Dividend income."},
    {"symbol":"VTI",   "added_by":"Frank",  "notes":"Frank's Portfolio — Vanguard US Total Stock Market ETF."},
    # Benchmarks
    {"symbol":"SPY",   "added_by":"System", "notes":"Benchmark — S&P 500"},
    {"symbol":"QQQ",   "added_by":"System", "notes":"Benchmark — Nasdaq 100"},
]

def seed_watchlist_if_empty():
    """Seed Supabase with starter stocks if the table is empty."""
    try:
        existing = sb_get("infra_watchlist", "?select=symbol&active=eq.true")
        if existing:
            print(f"[InfraAlpha] Watchlist has {len(existing)} stocks — skipping seed")
            return
        print(f"[InfraAlpha] Seeding {len(STARTER_WATCHLIST)} stocks into Supabase...")
        now = datetime.now(CST).isoformat()
        rows = [{**s, "active": True, "added_at": now} for s in STARTER_WATCHLIST]
        # Upsert in batches of 20
        for i in range(0, len(rows), 20):
            batch = rows[i:i+20]
            headers_upsert = {**SB_HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"}
            httpx.post(f"{SUPABASE_URL}/rest/v1/infra_watchlist",
                       headers=headers_upsert, json=batch, timeout=15).raise_for_status()
        print(f"[InfraAlpha] Seeded {len(rows)} stocks ✓")
    except Exception as e:
        print(f"[InfraAlpha] Seed warning: {e}")

# ── Quote cache ───────────────────────────────────────────────────────────────
_quote_cache: dict = {}
_vwap_cache:  dict = {}
_macro_cache: dict = {}
QUOTE_TTL = 60
VWAP_TTL  = 300
MACRO_TTL = 120


def fetch_quote(symbol: str) -> dict:
    now = time.time()
    if symbol in _quote_cache and now - _quote_cache[symbol].get("_ts", 0) < QUOTE_TTL:
        return _quote_cache[symbol]
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period="5d")
        if hist is None or len(hist) < 2:
            return {"symbol": symbol, "error": "no data"}
        last  = float(hist["Close"].iloc[-1])
        prev  = float(hist["Close"].iloc[-2])
        chg   = round(last - prev, 2)
        chgPct = round((chg / prev) * 100, 2) if prev else 0
        result = {"symbol": symbol, "price": round(last, 2), "change": chg,
                  "changePct": chgPct, "_ts": now}
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
        vwap    = (typical * df["Volume"]).cumsum() / df["Volume"].cumsum()
        last_close = float(df["Close"].iloc[-1])
        last_vwap  = float(vwap.iloc[-1])
        last_open  = float(df["Open"].iloc[-1])
        last_vol   = float(df["Volume"].iloc[-1])
        avg_vol    = float(df["Volume"].iloc[-20:].mean()) if len(df) >= 20 else float(df["Volume"].mean())
        if last_close <= last_vwap:
            result = {"symbol": symbol, "setup": False, "grade": "NONE",
                      "vwap": round(last_vwap, 2), "price": round(last_close, 2),
                      "reason": "price below VWAP", "_ts": now}
            _vwap_cache[symbol] = result
            return result
        recent_lows  = list(df["Low"].iloc[-4:-1])
        recent_vwaps = [float(vwap.iloc[-(4 - i)]) for i in range(len(recent_lows))]
        touched = any(abs(low - v) / v < 0.003 for low, v in zip(recent_lows, recent_vwaps))
        if not touched or last_close <= last_open:
            result = {"symbol": symbol, "setup": False, "grade": "NONE",
                      "vwap": round(last_vwap, 2), "price": round(last_close, 2),
                      "reason": "no pullback/rejection", "_ts": now}
            _vwap_cache[symbol] = result
            return result
        vol_spike = last_vol / avg_vol if avg_vol > 0 else 0
        if vol_spike < 1.5:
            result = {"symbol": symbol, "setup": False, "grade": "NONE",
                      "vwap": round(last_vwap, 2), "price": round(last_close, 2),
                      "reason": f"volume too low ({vol_spike:.1f}x)", "_ts": now}
            _vwap_cache[symbol] = result
            return result
        grade = "HIGH" if vol_spike >= 3.0 else "MEDIUM"
        pct_above = round(((last_close - last_vwap) / last_vwap) * 100, 2)
        result = {"symbol": symbol, "setup": True, "grade": grade,
                  "price": round(last_close, 2), "vwap": round(last_vwap, 2),
                  "pct_above_vwap": pct_above, "vol_spike": round(vol_spike, 1), "_ts": now}
        _vwap_cache[symbol] = result
        return result
    except Exception as e:
        return {"symbol": symbol, "setup": False, "grade": "NONE", "error": str(e), "_ts": time.time()}


def fetch_macro() -> dict:
    now = time.time()
    if _macro_cache.get("_ts", 0) and now - _macro_cache["_ts"] < MACRO_TTL:
        return _macro_cache
    result = {}
    try:
        r = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        d = r.json()["data"][0]
        result["fg_score"] = int(d["value"])
        result["fg_label"] = d["value_classification"]
    except Exception:
        result["fg_score"] = None; result["fg_label"] = "Unknown"
    try:
        import yfinance as yf
        for sym, key in [("^VIX","vix"),("SPY","spy"),("QQQ","qqq")]:
            hist = yf.Ticker(sym).history(period="5d")
            if hist is not None and len(hist) >= 2:
                last = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                if key == "vix": result["vix"] = round(last, 2)
                else: result[f"{key}_pct"] = round(((last - prev) / prev) * 100, 2)
    except Exception:
        pass
    try:
        r = httpx.get("https://api.coingecko.com/api/v3/global", timeout=8)
        d = r.json()["data"]
        result["btc_dom"] = round(d["market_cap_percentage"]["btc"], 1)
        result["mcap_change_24h"] = round(d["market_cap_change_percentage_24h_usd"], 2)
    except Exception:
        pass
    vix = result.get("vix", 20); fg = result.get("fg_score", 50)
    mcap = result.get("mcap_change_24h", 0); btcdom = result.get("btc_dom", 55)
    score = 0
    if vix < 18: score += 2
    elif vix < 22: score += 1
    elif vix > 28: score -= 2
    elif vix > 24: score -= 1
    if fg and fg > 60: score += 2
    elif fg and fg > 45: score += 1
    elif fg and fg < 25: score -= 2
    elif fg and fg < 35: score -= 1
    if mcap > 3: score += 2
    elif mcap > 1: score += 1
    elif mcap < -3: score -= 2
    elif mcap < -1: score -= 1
    if btcdom > 60: score -= 1
    elif btcdom < 50: score += 1
    if score >= 3: result["bias"] = "MEMECOINS 🚀"
    elif score >= 1: result["bias"] = "MIXED — Lean Crypto"
    elif score == 0: result["bias"] = "BALANCED"
    elif score >= -2: result["bias"] = "MIXED — Lean Stocks"
    else: result["bias"] = "STOCKS / CASH 🛡️"
    result["_ts"] = now
    _macro_cache.update(result)
    return result


# ── API Routes ────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok", "ts": datetime.now(CST).isoformat(), "backend": "supabase"})


@app.route("/api/watchlist", methods=["GET"])
def get_watchlist():
    try:
        rows = sb_get("infra_watchlist", "?select=*&active=eq.true&order=sort_order.asc,added_at.asc")
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist", methods=["POST"])
def add_to_watchlist():
    data = request.get_json() or {}
    symbol = (data.get("symbol") or "").strip().upper()
    if not symbol:
        return jsonify({"error": "symbol required"}), 400
    try:
        # Check if already active
        existing = sb_get("infra_watchlist", f"?symbol=eq.{symbol}&active=eq.true")
        if existing:
            return jsonify({"error": f"{symbol} already in watchlist"}), 409
        entry = {
            "symbol":   symbol,
            "added_by": data.get("added_by", "Frank"),
            "added_at": datetime.now(CST).isoformat(),
            "notes":    data.get("notes", ""),
            "active":   True,
        }
        result = sb_post("infra_watchlist", entry)
        # Log to signals
        _log_signal(symbol, "watchlist_add",
                    f"{entry['added_by']} added {symbol}" + (f" — {entry['notes']}" if entry['notes'] else ""),
                    entry["added_by"])
        return jsonify({"ok": True, "entry": result[0] if result else entry})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist/reorder", methods=["POST"])
def reorder_watchlist():
    """Persist drag-and-drop order. Body: {order: ['VRT','GEV',...]} """
    data = request.get_json() or {}
    order = data.get("order", [])
    if not order:
        return jsonify({"error": "order list required"}), 400
    try:
        for i, symbol in enumerate(order):
            sb_patch(f"infra_watchlist?symbol=eq.{symbol}&active=eq.true",
                     {"sort_order": i})
        return jsonify({"ok": True, "count": len(order)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist/<symbol>", methods=["DELETE"])
def remove_from_watchlist(symbol):
    symbol = symbol.upper()
    try:
        sb_patch(f"infra_watchlist?symbol=eq.{symbol}&active=eq.true", {"active": False})
        _log_signal(symbol, "watchlist_remove", f"Removed {symbol} from watchlist", "user")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _log_signal(symbol, sig_type, message, source="bot"):
    try:
        sb_post("infra_signals", {
            "ts":      datetime.now(CST).isoformat(),
            "symbol":  symbol,
            "type":    sig_type,
            "message": message,
            "source":  source,
        })
    except Exception:
        pass


@app.route("/api/quote/<symbol>")
def get_quote(symbol):
    return jsonify(fetch_quote(symbol.upper()))


@app.route("/api/quotes")
def get_quotes():
    try:
        wl = sb_get("infra_watchlist", "?select=symbol,notes,added_by&active=eq.true&order=sort_order.asc,added_at.asc")
        results = []
        for row in wl:
            sym = row["symbol"]
            q = fetch_quote(sym)
            v = fetch_vwap_setup(sym)
            q["vwap_setup"] = v.get("setup", False)
            q["vwap_grade"] = v.get("grade", "NONE")
            q["vwap_price"] = v.get("vwap")
            q["notes"]      = row.get("notes", "")
            q["added_by"]   = row.get("added_by", "")
            results.append(q)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/vwap-scan")
def vwap_scan():
    try:
        wl = sb_get("infra_watchlist", "?select=symbol&active=eq.true")
        setups = [v for sym in [r["symbol"] for r in wl]
                  if (v := fetch_vwap_setup(sym)).get("setup")]
        setups.sort(key=lambda x: x.get("vol_spike", 0), reverse=True)
        return jsonify(setups)
    except Exception as e:
        return jsonify([])


@app.route("/api/macro")
def get_macro():
    return jsonify(fetch_macro())


@app.route("/api/signals", methods=["GET"])
def get_signals():
    limit = int(request.args.get("limit", 50))
    try:
        rows = sb_get("infra_signals", f"?select=*&order=ts.desc&limit={limit}")
        return jsonify(rows)
    except Exception as e:
        return jsonify([])


@app.route("/api/signals", methods=["POST"])
def add_signal():
    data = request.get_json() or {}
    try:
        entry = {
            "ts":      data.get("ts", datetime.now(CST).isoformat()),
            "symbol":  data.get("symbol", ""),
            "type":    data.get("type", "info"),
            "message": data.get("message", ""),
            "source":  data.get("source", "bot"),
        }
        sb_post("infra_signals", entry)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


if __name__ == "__main__":
    print(f"[InfraAlpha] Starting on port {PORT} — Supabase backend")
    # Seed on startup if table empty
    try:
        seed_watchlist_if_empty()
    except Exception as e:
        print(f"[InfraAlpha] Seed error (non-fatal): {e}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
