"""
crypto.py — symmetric encryption for stored secrets (per-user broker credentials).

Encryption key is derived from the APP_SECRET_KEY environment variable
(sha256 -> urlsafe-base64), so it stays stable across restarts as long as
APP_SECRET_KEY doesn't change. Falls back to "dev-secret-change-me" if unset
(fine for local dev — set a real APP_SECRET_KEY in production).

If the `cryptography` package is unavailable for any reason, this module
falls back to a PLAINTEXT passthrough (with a loud printed warning) rather
than crashing the app — encrypted-at-rest storage is best-effort in that
degraded scenario, not a hard requirement for local/dev usage.
"""

import base64
import hashlib
import os

_KEY_ENV = "APP_SECRET_KEY"
_DEFAULT_SECRET = "dev-secret-change-me"


def _fernet_key() -> bytes:
    secret = os.getenv(_KEY_ENV, _DEFAULT_SECRET) or _DEFAULT_SECRET
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())


try:
    from cryptography.fernet import Fernet

    _FERNET = Fernet(_fernet_key())
    CRYPTO_AVAILABLE = True
except Exception as _exc:  # pragma: no cover — only hit when `cryptography` is missing/broken
    _FERNET = None
    CRYPTO_AVAILABLE = False
    print(
        "=" * 70 + "\n"
        "[auth.crypto] WARNING: 'cryptography' package unavailable "
        f"({_exc}).\n"
        "[auth.crypto] Falling back to PLAINTEXT storage for 'encrypted' "
        "user settings.\n"
        "[auth.crypto] Install `cryptography` (pip install cryptography) "
        "before relying on this in production.\n" + "=" * 70
    )


def encrypt_str(value: str | None) -> str | None:
    """Encrypt a string. Passes through unchanged if cryptography is unavailable."""
    if value is None:
        return None
    if not CRYPTO_AVAILABLE:
        return value
    return _FERNET.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_str(token: str | None) -> str | None:
    """
    Decrypt a string produced by encrypt_str().

    Falls back to returning the input unchanged if cryptography is
    unavailable, or if the value isn't a valid Fernet token (e.g. it was
    written while running in the plaintext-fallback mode) — this keeps the
    dev fallback path fully non-crashing in both directions.
    """
    if token is None:
        return None
    if not CRYPTO_AVAILABLE:
        return token
    try:
        return _FERNET.decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:
        return token
