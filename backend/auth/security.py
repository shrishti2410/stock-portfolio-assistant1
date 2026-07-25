"""
security.py — password hashing + session token generation.

Password storage format (users.password_hash):
    pbkdf2$<iterations>$<salt_b64>$<hash_b64>

Uses only the stdlib (hashlib.pbkdf2_hmac, sha256) — no external dependency
required to hash/verify passwords. 200,000 iterations + a fresh 16-byte
random salt per password, per OWASP guidance for PBKDF2-HMAC-SHA256.
"""

import base64
import hashlib
import hmac
import os
import secrets

_ALGO = "sha256"
_ITERATIONS = 200_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash a plaintext password. Returns 'pbkdf2$<iters>$<salt_b64>$<hash_b64>'."""
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")

    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)

    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(digest).decode("ascii")
    return f"pbkdf2${_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, stored: str) -> bool:
    """
    Verify a plaintext password against a stored 'pbkdf2$iters$salt$hash' string.

    Returns False (never raises) for malformed/empty input so callers can
    always safely branch on the boolean result.
    """
    if not password or not stored:
        return False

    try:
        algo, iterations_str, salt_b64, hash_b64 = stored.split("$", 3)
        if algo != "pbkdf2":
            return False
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def new_session_token() -> str:
    """Generate a new opaque, URL-safe session token (256 bits of entropy)."""
    return secrets.token_urlsafe(32)
