"""
paper_trader.py — Paper Trade Executor
Executes paper trades via Alpaca, logs to Supabase, sends Telegram alerts.
"""

import os
import logging
from datetime import datetime
import pytz
import requests

logger = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")

ALPACA_BASE = "https://paper-api.alpaca.markets"


def _is_market_hours() -> bool:
    now_et = datetime.now(ET)
    if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now_et <= market_close


def _alpaca_headers(api_key: str, api_secret: str) -> dict:
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret,
        "Content-Type": "application/json",
    }


def _place_order(api_key: str, api_secret: str, payload: dict) -> dict:
    url = f"{ALPACA_BASE}/v2/orders"
    resp = requests.post(url, json=payload, headers=_alpaca_headers(api_key, api_secret), timeout=10)
    resp.raise_for_status()
    return resp.json()


def execute_paper_trade(user_name: str, signal: dict, account: dict) -> dict:
    """
    Execute a paper trade if conviction is HIGH and account is enabled.
    account dict should have: api_key, api_secret, enabled, telegram_chat_id (optional)
    signal dict from score_signal() with position sizing (shares, stop_price) included.
    Returns execution result dict.
    """
    if not account.get("enabled", False):
        return {"executed": False, "reason": "account disabled"}

    if signal.get("conviction") != "HIGH":
        return {"executed": False, "reason": f"conviction not HIGH: {signal.get('conviction')}"}

    if signal.get("macro_regime") == "RISK_OFF":
        return {"executed": False, "reason": "RISK_OFF macro regime"}

    if not _is_market_hours():
        return {"executed": False, "reason": "outside market hours"}

    api_key = account.get("api_key", "")
    api_secret = account.get("api_secret", "")
    if not api_key or not api_secret:
        return {"executed": False, "reason": "missing API credentials"}

    symbol = signal["symbol"]
    shares = signal.get("shares", 1)
    stop_price = signal.get("stop_price") or signal.get("vwap_setup", {}).get("vwap")

    # Place market buy order
    order_payload = {
        "symbol": symbol,
        "qty": shares,
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
    }

    try:
        order = _place_order(api_key, api_secret, order_payload)
        order_id = order.get("id", "")

        # Place stop-loss bracket if we have a stop price
        if stop_price and stop_price > 0:
            entry_price = signal.get("vwap_setup", {}).get("price", 0)
            if entry_price <= 0:
                entry_price = float(order.get("filled_avg_price") or
                                    order.get("limit_price") or 0)
            if stop_price <= 0:
                if entry_price > 0:
                    stop_price = round(entry_price * 0.985, 2)  # -1.5%

            try:
                stop_payload = {
                    "symbol": symbol,
                    "qty": shares,
                    "side": "sell",
                    "type": "stop",
                    "time_in_force": "gtc",
                    "stop_price": str(round(stop_price, 2)),
                }
                _place_order(api_key, api_secret, stop_payload)
            except Exception as se:
                logger.warning(f"Stop-loss order failed for {symbol}: {se}")

        result = {
            "executed": True,
            "order_id": order_id,
            "symbol": symbol,
            "shares": shares,
            "side": "buy",
            "stop_price": stop_price,
        }

        # Log to Supabase
        try:
            _log_trade_to_supabase(user_name, signal, result)
        except Exception as e:
            logger.error(f"Supabase trade log failed: {e}")

        # Send Telegram alert
        try:
            chat_id = account.get("telegram_chat_id", "")
            if chat_id:
                send_trade_alert(user_name, signal, result, chat_id)
        except Exception as e:
            logger.warning(f"Telegram alert failed: {e}")

        return result

    except Exception as e:
        logger.error(f"Trade execution failed for {symbol}: {e}")
        return {"executed": False, "reason": str(e), "symbol": symbol}


def send_trade_alert(user_name: str, signal: dict, order: dict, chat_id: str):
    """Send Telegram trade alert."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or not chat_id:
        return

    symbol = signal.get("symbol", "")
    vwap_setup = signal.get("vwap_setup", {})
    price = vwap_setup.get("price", 0)
    shares = order.get("shares", 0)
    position_value = price * shares
    score = signal.get("score", 0)
    conviction = signal.get("conviction", "")
    news_score = signal.get("news", {}).get("score", 0)
    pattern = signal.get("candle", {}).get("pattern", "none")
    stop_price = order.get("stop_price", vwap_setup.get("vwap", 0))
    slippage_est = signal.get("slippage_est", 0)
    net_risk = signal.get("net_risk", 0)

    stop_label = f"${stop_price:.2f} (VWAP)" if stop_price else "N/A"
    news_label = f"+{news_score:.1f}" if news_score >= 0 else f"{news_score:.1f}"
    news_dir = "bullish" if news_score > 0 else ("bearish" if news_score < 0 else "neutral")

    text = (
        f"\U0001F3AF PAPER TRADE \u2014 {user_name}\n"
        f"\U0001F4C8 BUY {symbol} @ ${price:.2f}\n"
        f"\U0001F4CA {shares} shares | ${position_value:,.2f}\n"
        f"\U0001F3AF Score: {score}/10 | {conviction} conviction\n"
        f"\U0001F4F0 News: {news_label} ({news_dir})\n"
        f"\U0001F56F\uFE0F Pattern: {pattern.replace('_', ' ').title()}\n"
        f"\U0001F6D1 Stop: {stop_label}\n"
        f"\U0001F4B0 Risk: ${net_risk:.2f} | Est. slippage: ${slippage_est:.2f}"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=5)
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")


def _log_trade_to_supabase(user_name: str, signal: dict, order: dict):
    """Log a trade to Supabase infra_trades table."""
    from server import sb_post  # import here to avoid circular imports

    vwap_setup = signal.get("vwap_setup", {})
    candle = signal.get("candle", {})
    news = signal.get("news", {})

    row = {
        "user_name": user_name,
        "symbol": signal.get("symbol", ""),
        "side": order.get("side", "buy"),
        "shares": order.get("shares", 0),
        "entry_price": vwap_setup.get("price"),
        "stop_price": order.get("stop_price"),
        "score": signal.get("score"),
        "conviction": signal.get("conviction"),
        "pattern": candle.get("pattern"),
        "news_score": news.get("score"),
        "macro_regime": signal.get("macro_regime"),
        "order_id": order.get("order_id"),
        "status": "open",
        "slippage_est": signal.get("slippage_est"),
    }
    sb_post("infra_trades", row)


def log_signal_to_supabase(user_name: str, signal: dict, executed: bool = False):
    """Log a MEDIUM/HIGH signal observation (no execution) to Supabase."""
    try:
        from server import sb_post

        vwap_setup = signal.get("vwap_setup", {})
        candle = signal.get("candle", {})
        news = signal.get("news", {})

        row = {
            "user_name": user_name,
            "symbol": signal.get("symbol", ""),
            "side": "signal_only",
            "shares": 0,
            "entry_price": vwap_setup.get("price"),
            "score": signal.get("score"),
            "conviction": signal.get("conviction"),
            "pattern": candle.get("pattern"),
            "news_score": news.get("score"),
            "macro_regime": signal.get("macro_regime"),
            "status": "signal_only",
        }
        sb_post("infra_trades", row)
    except Exception as e:
        logger.warning(f"Signal log to Supabase failed: {e}")
