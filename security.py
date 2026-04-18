"""
security.py — InfraAlpha Portal security helpers
Centralizes auth, rate limiting, input validation, and key masking.
"""

import os
import re
import time
import threading
from functools import wraps

from flask import request, jsonify

# ── Config ────────────────────────────────────────────────────────────────────

PORTAL_API_TOKEN = os.getenv("PORTAL_API_TOKEN")
if not PORTAL_API_TOKEN:
    raise RuntimeError("PORTAL_API_TOKEN env var is required")

VALID_USERS = {"jerry", "frank"}

# ── Auth decorator ────────────────────────────────────────────────────────────

def require_auth(f):
    """Decorator: require valid Bearer token in Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        token = auth_header[len("Bearer "):]
        if token != PORTAL_API_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ── Rate limiting ─────────────────────────────────────────────────────────────

_rate_limit_lock = threading.Lock()
_rate_limit: dict = {}  # key -> list of timestamps


def rate_limit(user_name: str, action: str, max_calls: int = 5, window_sec: int = 60) -> bool:
    """
    Returns True if the call is allowed, False if rate limit exceeded.
    Thread-safe in-memory rate limiter using a sliding window.
    """
    key = f"{user_name}:{action}"
    now = time.time()
    with _rate_limit_lock:
        timestamps = _rate_limit.get(key, [])
        # Drop timestamps outside the window
        timestamps = [t for t in timestamps if now - t < window_sec]
        if len(timestamps) >= max_calls:
            _rate_limit[key] = timestamps
            return False
        timestamps.append(now)
        _rate_limit[key] = timestamps
        return True

# ── Input validation ──────────────────────────────────────────────────────────

def validate_user(user_name: str) -> bool:
    """Return True if user_name is in the allowed set."""
    return user_name in VALID_USERS


def sanitize_symbol(symbol: str) -> str:
    """Strip everything except alphanumeric and dots/carets (ticker symbols)."""
    return re.sub(r"[^A-Za-z0-9.\^]", "", symbol).upper()

# ── Key masking ───────────────────────────────────────────────────────────────

def mask_key(key_id: str) -> str:
    """Return a masked key like 'PK****ABCD'."""
    if not key_id or len(key_id) < 6:
        return "****"
    return key_id[:2] + "****" + key_id[-4:]
