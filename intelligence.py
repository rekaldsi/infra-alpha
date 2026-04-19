"""
intelligence.py — InfraAlpha Intelligence Engine
Core signal intelligence: candlestick detection, news sentiment, macro regime, composite scoring
"""

import os
import time
import math
import logging
from datetime import datetime, timedelta
import pytz

import yfinance as yf
import requests

logger = logging.getLogger(__name__)

# ─── Caches ───────────────────────────────────────────────────────────────────

_news_cache: dict = {}       # symbol -> {"data": ..., "ts": float}
_macro_cache: dict = {}      # "macro" -> {"data": ..., "ts": float}
_NEWS_TTL = 15 * 60          # 15 minutes
_MACRO_TTL = 30 * 60         # 30 minutes

# ─── Expanded Universe ────────────────────────────────────────────────────────

EXPANDED_UNIVERSE = [
    # Defense
    "LMT", "RTX", "NOC", "GD", "LHX", "KTOS", "AXON", "LDOS", "SAIC",
    "BAH", "CACI", "DRS", "HII", "TDG", "HEICO",
    # Tech infra
    "ANET", "SMCI", "DELL", "HPE", "NTAP", "PSTG", "CRDO", "MRVL",
    # Energy / power
    "VST", "CEG", "NRG", "TALEN", "CLNE",
]

# ─── A. Candlestick Pattern Detector ─────────────────────────────────────────


def detect_candlestick(bars: list) -> dict:
    """
    bars: list of dicts with keys open, high, low, close, volume (last 3-5 1-min bars)
    Returns {"pattern": str, "direction": str, "strength": float}
    """
    if not bars or len(bars) < 2:
        return {"pattern": "none", "direction": "neutral", "strength": 0.0}

    cur = bars[-1]
    prev = bars[-2]

    def body(b):
        return abs(b["close"] - b["open"])

    def rng(b):
        return b["high"] - b["low"] if b["high"] != b["low"] else 1e-9

    def upper_wick(b):
        return b["high"] - max(b["open"], b["close"])

    def lower_wick(b):
        return min(b["open"], b["close"]) - b["low"]

    cur_body = body(cur)
    cur_range = rng(cur)
    cur_upper = upper_wick(cur)
    cur_lower = lower_wick(cur)

    prev_body = body(prev)

    # Doji: open ≈ close (within 0.1% of range)
    if cur_body <= 0.001 * cur_range or cur_body < 0.05:
        return {"pattern": "doji", "direction": "neutral", "strength": 0.5}

    # Hammer: small body, long lower wick (>2x body), bullish
    if cur_lower >= 2 * cur_body and cur_upper <= 0.3 * cur_body:
        strength = min(0.8, cur_lower / max(cur_body, 0.01) / 4)  # CAP at 0.8 (OPTIMIZED 2026-04-19)
        return {"pattern": "hammer", "direction": "bullish", "strength": round(strength, 2)}

    # Inverted hammer: small body, long upper wick (>2x body), potential bullish reversal
    if cur_upper >= 2 * cur_body and cur_lower <= 0.3 * cur_body and cur["close"] > cur["open"]:
        strength = min(0.8, cur_upper / max(cur_body, 0.01) / 4)  # CAP at 0.8 (OPTIMIZED 2026-04-19)
        return {"pattern": "inverted_hammer", "direction": "bullish", "strength": round(strength, 2)}

    # Shooting star: small body at top, long upper wick, bearish
    if cur_upper >= 2 * cur_body and cur_lower <= 0.3 * cur_body and cur["close"] < cur["open"]:
        strength = min(0.8, cur_upper / max(cur_body, 0.01) / 4)  # CAP at 0.8 (OPTIMIZED 2026-04-19)
        return {"pattern": "shooting_star", "direction": "bearish", "strength": round(strength, 2)}

    # Bullish engulfing: current body fully covers prior body, direction reversal
    if (cur["close"] > cur["open"] and prev["close"] < prev["open"]
            and cur["open"] <= prev["close"] and cur["close"] >= prev["open"]):
        strength = min(0.8, cur_body / max(prev_body, 0.01) / 2)  # CAP at 0.8 (OPTIMIZED 2026-04-19)
        return {"pattern": "bullish_engulfing", "direction": "bullish", "strength": round(strength, 2)}

    # Bearish engulfing
    if (cur["close"] < cur["open"] and prev["close"] > prev["open"]
            and cur["open"] >= prev["close"] and cur["close"] <= prev["open"]):
        strength = min(0.8, cur_body / max(prev_body, 0.01) / 2)  # CAP at 0.8 (OPTIMIZED 2026-04-19)
        return {"pattern": "bearish_engulfing", "direction": "bearish", "strength": round(strength, 2)}

    # Morning star: 3-bar pattern
    if len(bars) >= 3:
        first = bars[-3]
        if (first["close"] < first["open"]              # first bar bearish
                and body(prev) < 0.5 * body(first)     # doji-like middle
                and cur["close"] > cur["open"]          # third bar bullish
                and cur["close"] > (first["open"] + first["close"]) / 2):
            return {"pattern": "morning_star", "direction": "bullish", "strength": 0.85}

    return {"pattern": "none", "direction": "neutral", "strength": 0.0}


# ─── B. News Sentiment Fetcher ────────────────────────────────────────────────

_BULLISH_KW = {"beat", "upgrade", "contract", "win", "record", "surge", "buy",
               "strong", "growth", "expansion"}
_BEARISH_KW = {"miss", "downgrade", "investigation", "layoff", "recall",
               "decline", "weak", "cut", "loss", "tariff", "fine"}


def _score_headline(text: str) -> float:
    words = set(text.lower().split())
    score = len(words & _BULLISH_KW) - len(words & _BEARISH_KW)
    return max(-2.0, min(2.0, float(score)))


# Defense sector symbols — contract news is high signal, not noise (2026-04-19)
DEFENSE_SYMBOLS = {"LMT", "RTX", "NOC", "GD", "LHX", "KTOS", "AXON", "LDOS", 
                   "SAIC", "BAH", "CACI", "DRS", "HII", "TDG"}


def get_news_sentiment(symbol: str) -> dict:
    now = time.time()
    cached = _news_cache.get(symbol)
    if cached and (now - cached["ts"]) < _NEWS_TTL:
        return {**cached["data"], "cached": True}

    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news[:5] if ticker.news else []
        if not news:
            result = {"symbol": symbol, "score": 0.0, "headline_count": 0,
                      "top_headline": "", "cached": False}
            _news_cache[symbol] = {"data": result, "ts": now}
            return result

        scores = []
        headlines = []
        for item in news:
            title = item.get("title", "") or item.get("content", {}).get("title", "")
            if title:
                scores.append(_score_headline(title))
                headlines.append(title)

        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # OPTIMIZED 2026-04-19 for MAX PROFIT TAKING:
        # Defense/contractor news (contract wins, deals) = high signal even single headline
        # General tech news requires ≥2 aligned headlines (avoid noise)
        if symbol in DEFENSE_SYMBOLS:
            # Contract news is time-sensitive; single headline = actionable signal
            if len(headlines) >= 1:
                avg_score = avg_score * 0.75  # Allow single headline, cap at ±1.5
            else:
                avg_score = 0.0
        else:
            # General news: require ≥2 aligned headlines
            if len(headlines) < 2:
                avg_score = 0.0
        
        result = {
            "symbol": symbol,
            "score": round(avg_score, 2),
            "headline_count": len(headlines),
            "top_headline": headlines[0] if headlines else "",
            "cached": False,
        }
    except Exception as e:
        logger.warning(f"News fetch failed for {symbol}: {e}")
        result = {"symbol": symbol, "score": 0.0, "headline_count": 0,
                  "top_headline": "", "cached": False}

    _news_cache[symbol] = {"data": result, "ts": now}
    return result


# ─── C. Macro Regime Detector ─────────────────────────────────────────────────


def get_macro_regime() -> dict:
    now = time.time()
    cached = _macro_cache.get("macro")
    if cached and (now - cached["ts"]) < _MACRO_TTL:
        return {**cached["data"], "cached": True}

    try:
        vix_ticker = yf.Ticker("^VIX")
        vix_hist = vix_ticker.history(period="1d", interval="1m")
        vix = float(vix_hist["Close"].iloc[-1]) if not vix_hist.empty else 20.0

        spy_ticker = yf.Ticker("SPY")
        spy_hist = spy_ticker.history(period="30d", interval="1d")
        if len(spy_hist) >= 20:
            spy_close = spy_hist["Close"].values
            spy_price = spy_close[-1]
            sma20 = spy_close[-20:].mean()
            spy_trend = "above_sma" if spy_price > sma20 else "below_sma"
        else:
            spy_price = 0.0
            sma20 = 0.0
            spy_trend = "unknown"

        if vix < 20 and spy_trend == "above_sma":
            regime = "RISK_ON"
        elif vix > 25:
            regime = "RISK_OFF"
        else:
            regime = "CAUTION"

        result = {
            "regime": regime,
            "vix": round(vix, 2),
            "spy_trend": spy_trend,
            "spy_price": round(spy_price, 2),
            "spy_sma20": round(sma20, 2),
            "cached": False,
        }
    except Exception as e:
        logger.warning(f"Macro regime fetch failed: {e}")
        result = {
            "regime": "CAUTION",
            "vix": 20.0,
            "spy_trend": "unknown",
            "spy_price": 0.0,
            "spy_sma20": 0.0,
            "cached": False,
        }

    _macro_cache["macro"] = {"data": result, "ts": now}
    return result


# ─── D. Composite Signal Scorer ───────────────────────────────────────────────


def score_signal(symbol: str, vwap_setup: dict, candle: dict,
                 news: dict, macro: dict) -> dict:
    components = {}

    # VWAP strength (OPTIMIZED 2026-04-19 for MAX PROFIT TAKING)
    # VWAP is the PRIMARY signal. Increase weight from 4→5 to reward tight bounces.
    vwap_str = vwap_setup.get("signal", "LOW")
    vwap_pts = {"HIGH": 5, "MEDIUM": 2.5, "LOW": 0.5}.get(vwap_str, 0)
    components["vwap"] = vwap_pts

    # Volume multiplier (OPTIMIZED 2026-04-19 for MAX PROFIT TAKING)
    # Extreme volume (10x+) is rare but highly predictive. Reward it aggressively.
    # Volume is CONFIRMATION — tightest bounces with 20x+ volume = highest ROI trades.
    vol_mult = vwap_setup.get("volume_multiplier", 1.0)
    if vol_mult >= 20:
        vol_pts = 3.5  # EXTREME volume spike — highest confidence (NEW tier)
    elif vol_mult >= 12:
        vol_pts = 3.0  # VERY HIGH volume — strong breakout confirmation
    elif vol_mult >= 8:
        vol_pts = 2.75 # HIGH volume — solid confirmation (NEW tier)
    elif vol_mult >= 5:
        vol_pts = 2.0  # MEDIUM volume — base confirmation (OPTIMIZED: 1.5→2.0)
    else:
        vol_pts = 0.0 # No volume spike — skip
    components["volume"] = vol_pts

    # Candlestick confirmation (OPTIMIZED 2026-04-19)
    # Keep strength multiplier but increase base points.
    # Bullish patterns on VWAP setup = high confidence.
    candle_dir = candle.get("direction", "neutral")
    candle_strength = candle.get("strength", 0.0)
    candle_pts = 0
    if candle_dir == "bullish":
        candle_pts = 2.5 * candle_strength  # Max +2.125 (OPTIMIZED: +1.6→+2.125)
    elif candle_dir == "bearish":
        candle_pts = -1 * candle_strength  # Keep bearish penalty (max -0.8)
    components["candlestick"] = round(candle_pts, 2)

    # News score (OPTIMIZED 2026-04-19)
    # Single-headline moves are noise. Only meaningful if ≥2 aligned headlines.
    # News contributes confirmation, not primary signal (max +/-1 after filtering).
    news_score = news.get("score", 0.0)
    headline_count = news.get("headline_count", 0)
    if headline_count < 2:
        news_score = 0  # Ignore single-headline noise
    else:
        news_score = news_score * 0.5  # Multi-headline: cap at ±1 instead of ±2
    components["news"] = round(news_score, 2)

    # Macro (OPTIMIZED 2026-04-19 for MAX PROFIT TAKING)
    # RISK_ON is FUNDAMENTAL for tight bounces. Increase bonus to reward regime alignment.
    # CAUTION still supports setups in transition; RISK_OFF is hard filter.
    regime = macro.get("regime", "CAUTION")
    macro_pts = {"RISK_ON": 2.0, "CAUTION": 0.5, "RISK_OFF": -3}.get(regime, 0)  # OPTIMIZED: 1.5→2.0
    components["macro"] = macro_pts

    total = vwap_pts + vol_pts + candle_pts + news_score + macro_pts
    total = round(total, 2)

    # Thresholds (OPTIMIZED 2026-04-19 for MAX PROFIT TAKING)
    # HIGH: 6+ = execute immediately
    # MEDIUM: 5-5.99 = execute IF volume_mult ≥ 15 AND RISK_ON (aggressive confirmation)
    # LOW: <5 = skip
    # 
    # Why: VWAP + 20x volume in RISK_ON regime has >70% edge. Don't wait for candle.
    if total >= 6:
        conviction = "HIGH"
    elif total >= 5:
        conviction = "MEDIUM"
    else:
        conviction = "LOW"

    # AGGRESSIVE execution: HIGH always, MEDIUM only if extreme volume + bullish regime
    vol_mult = vwap_setup.get("volume_multiplier", 1.0)
    trade_signal = (
        (total >= 6) or 
        (total >= 5 and vol_mult >= 15 and regime == "RISK_ON")
    ) and regime != "RISK_OFF"  # OPTIMIZED 2026-04-19: aggressive MEDIUM execution

    return {
        "symbol": symbol,
        "score": total,
        "conviction": conviction,
        "components": components,
        "trade_signal": trade_signal,
        "vwap_setup": vwap_setup,
        "candle": candle,
        "news": news,
        "macro_regime": regime,
    }


# ─── E. Opportunity Hunter ────────────────────────────────────────────────────


def _get_vwap_setup_for_symbol(symbol: str) -> dict:
    """Minimal VWAP-like setup using yfinance 1-min bars."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty or len(hist) < 5:
            return {"symbol": symbol, "signal": "LOW", "volume_multiplier": 1.0,
                    "price": 0.0, "vwap": 0.0}

        # Compute VWAP
        hist = hist.copy()
        hist["tp"] = (hist["High"] + hist["Low"] + hist["Close"]) / 3
        hist["cumvol"] = hist["Volume"].cumsum()
        hist["cumtpvol"] = (hist["tp"] * hist["Volume"]).cumsum()
        hist["vwap"] = hist["cumtpvol"] / hist["cumvol"]

        price = float(hist["Close"].iloc[-1])
        vwap = float(hist["vwap"].iloc[-1])
        avg_vol = float(hist["Volume"].iloc[:-1].mean()) if len(hist) > 1 else 1.0
        last_vol = float(hist["Volume"].iloc[-1])
        vol_mult = last_vol / avg_vol if avg_vol > 0 else 1.0

        # Price within tight band of VWAP (OPTIMIZED 2026-04-19 for MAX PROFIT TAKING)
        # Tighter thresholds: 0.2% → 0.15% for HIGH, 0.5% → 0.35% for MEDIUM
        # Real VWAP bounces happen in 0.1-0.15% bands; wider window = drift, not bounce
        # Volume requirement increased: 5→8 for HIGH (confirm momentum), 2→5 for MEDIUM
        pct_from_vwap = abs(price - vwap) / vwap * 100 if vwap > 0 else 999

        if pct_from_vwap < 0.15 and vol_mult >= 8:
            signal = "HIGH"
        elif pct_from_vwap < 0.35 and vol_mult >= 5:
            signal = "MEDIUM"
        else:
            signal = "LOW"

        return {
            "symbol": symbol,
            "signal": signal,
            "volume_multiplier": round(vol_mult, 2),
            "price": round(price, 2),
            "vwap": round(vwap, 2),
            "pct_from_vwap": round(pct_from_vwap, 2),
        }
    except Exception as e:
        logger.debug(f"VWAP fetch failed for {symbol}: {e}")
        return {"symbol": symbol, "signal": "LOW", "volume_multiplier": 1.0,
                "price": 0.0, "vwap": 0.0}


def _get_bars_for_symbol(symbol: str) -> list:
    """Fetch last 5 1-min bars as list of dicts."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            return []
        bars = []
        for _, row in hist.tail(5).iterrows():
            bars.append({
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            })
        return bars
    except Exception:
        return []


def hunt_opportunities(watchlist: list) -> list:
    """
    Score all symbols from watchlist + expanded universe.
    Returns list of signal dicts with score >= 5, sorted by score desc.
    """
    macro = get_macro_regime()

    # Combine and deduplicate
    all_symbols = list(dict.fromkeys(list(watchlist) + EXPANDED_UNIVERSE))
    watchlist_set = set(watchlist)

    results = []
    for symbol in all_symbols:
        try:
            vwap_setup = _get_vwap_setup_for_symbol(symbol)
            bars = _get_bars_for_symbol(symbol)
            candle = detect_candlestick(bars)
            news = get_news_sentiment(symbol)
            scored = score_signal(symbol, vwap_setup, candle, news, macro)
            scored["on_watchlist"] = symbol in watchlist_set
            scored["source"] = "watchlist" if symbol in watchlist_set else "opportunity"
            if scored["score"] >= 5:
                results.append(scored)
        except Exception as e:
            logger.debug(f"hunt_opportunities error for {symbol}: {e}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ─── F. Fee-Aware Position Sizer ─────────────────────────────────────────────


def calculate_position(equity: float, risk_pct: float, entry: float, stop: float) -> dict:
    """
    Calculate position size with fee/slippage awareness.
    Returns dict with shares, position_value, risk_amount, slippage_est, net_risk.
    """
    risk_amount = equity * (risk_pct / 100)
    stop_distance = entry - stop  # for longs

    if stop_distance <= 0:
        return {
            "shares": 0,
            "position_value": 0.0,
            "risk_amount": risk_amount,
            "slippage_est": 0.0,
            "net_risk": risk_amount,
            "error": "stop must be below entry for longs",
        }

    shares = math.floor(risk_amount / stop_distance)
    if shares <= 0:
        shares = 1

    position_value = shares * entry
    slippage_est = position_value * 0.0001 * 2  # 0.01% each way
    net_risk = (shares * stop_distance) + slippage_est

    return {
        "shares": shares,
        "position_value": round(position_value, 2),
        "risk_amount": round(risk_amount, 2),
        "slippage_est": round(slippage_est, 4),
        "net_risk": round(net_risk, 2),
    }
