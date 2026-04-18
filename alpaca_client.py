"""
alpaca_client.py — Alpaca API helper functions.
Uses the requests library to call Alpaca paper or live endpoints.
"""

import requests

PAPER_BASE = "https://paper-api.alpaca.markets"
LIVE_BASE  = "https://api.alpaca.markets"


def _base_url(mode: str) -> str:
    return PAPER_BASE if mode == "paper" else LIVE_BASE


def get_alpaca_client(key_id: str, secret: str, mode: str) -> requests.Session:
    """Return a configured requests.Session with Alpaca auth headers and base URL attached."""
    session = requests.Session()
    session.headers.update({
        "APCA-API-KEY-ID":     key_id,
        "APCA-API-SECRET-KEY": secret,
        "Accept":              "application/json",
    })
    session.base_url = _base_url(mode)
    return session


def get_account(key_id: str, secret: str, mode: str) -> dict:
    """Call GET /v2/account and return the JSON response. Raises on HTTP error."""
    session = get_alpaca_client(key_id, secret, mode)
    r = session.get(f"{session.base_url}/v2/account", timeout=10)
    r.raise_for_status()
    return r.json()


def get_positions(key_id: str, secret: str, mode: str) -> list:
    """Call GET /v2/positions and return the list of positions. Raises on HTTP error."""
    session = get_alpaca_client(key_id, secret, mode)
    r = session.get(f"{session.base_url}/v2/positions", timeout=10)
    r.raise_for_status()
    return r.json()
