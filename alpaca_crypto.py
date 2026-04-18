"""
alpaca_crypto.py — Fernet symmetric encryption for Alpaca API keys.
Key is read from env var ALPACA_ENCRYPTION_KEY.
If not set, generates one at startup and prints it (local dev only).
"""

import os
from cryptography.fernet import Fernet

_fernet = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    key = os.getenv("ALPACA_ENCRYPTION_KEY")
    if not key:
        key = Fernet.generate_key().decode()
        print(f"[alpaca_crypto] WARNING: No ALPACA_ENCRYPTION_KEY set. Generated ephemeral key: {key}")
        print("[alpaca_crypto] Set ALPACA_ENCRYPTION_KEY in your environment to persist encrypted keys across restarts.")
    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt(value: str) -> str:
    """Encrypt a plaintext string and return a base64-encoded ciphertext string."""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a base64-encoded ciphertext string and return plaintext."""
    return _get_fernet().decrypt(value.encode()).decode()
