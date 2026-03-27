"""
auth.py — Zerodha Kite Connect authentication helpers

Two-step Zerodha OAuth flow:
  1. Direct the user to get_login_url() in their browser.
  2. Zerodha redirects back with ?request_token=<token>.
  3. Call exchange_token(request_token) to swap it for a persistent access_token.
     The access_token is written back into your .env file automatically.

You will also need ZERODHA_API_SECRET in .env for step 3.
Add it alongside the other keys:
    ZERODHA_API_KEY=...
    ZERODHA_API_SECRET=...
    ZERODHA_ACCESS_TOKEN=   # populated automatically by exchange_token()
"""

import os
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv
from kiteconnect import KiteConnect

load_dotenv()

# Path to the project .env file — one level above /backend/
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def get_login_url() -> str:
    """
    Return the Zerodha login URL for the configured API key.

    Usage:
        from zerodha.auth import get_login_url
        print(get_login_url())
        # Open the URL in a browser. After login Zerodha redirects to your
        # registered redirect URL with ?request_token=<token> in the query string.

    Raises:
        ValueError: if ZERODHA_API_KEY is not set.
    """
    api_key = os.getenv("ZERODHA_API_KEY", "")
    if not api_key:
        raise ValueError(
            "ZERODHA_API_KEY is not set. Add it to your .env file."
        )

    kite = KiteConnect(api_key=api_key)
    return kite.login_url()


def exchange_token(raw_input: str) -> str:
    """
    Exchange a one-time request_token for a reusable access_token.

    Accepts either:
      • The bare token string:  "abc123XYZ"
      • The full redirect URL:  "http://127.0.0.1:8000/api/auth/callback?
                                  action=login&status=success&request_token=abc123XYZ"

    Steps performed:
      1. Re-reads .env with override=True so ZERODHA_API_SECRET is picked up
         even if it was added after the server started.
      2. Extracts the request_token from a URL when necessary.
      3. Prints the token to the backend log for debugging.
      4. Calls kite.generate_session(request_token, api_secret).
      5. Writes ZERODHA_ACCESS_TOKEN back into .env via _write_env_key().

    Returns:
        The access_token string.

    Raises:
        ValueError: if api_key, api_secret, or request_token are missing.
    """
    # ── Re-read .env so freshly added keys (e.g. ZERODHA_API_SECRET) are visible ──
    load_dotenv(override=True)

    api_key    = os.getenv("ZERODHA_API_KEY", "").strip()
    api_secret = os.getenv("ZERODHA_API_SECRET", "").strip()

    if not api_key:
        raise ValueError("ZERODHA_API_KEY is not set in .env.")
    if not api_secret:
        raise ValueError(
            "ZERODHA_API_SECRET is not set in .env. "
            "Add ZERODHA_API_SECRET=<your_secret> to your .env file."
        )

    # ── Extract request_token — handle full URL or bare token ──────────────
    raw_input = raw_input.strip()
    request_token: str

    if raw_input.startswith("http://") or raw_input.startswith("https://"):
        parsed = urlparse(raw_input)
        params = parse_qs(parsed.query)
        tokens = params.get("request_token", [])
        if not tokens:
            raise ValueError(
                f"No 'request_token' query parameter found in URL: {raw_input}"
            )
        request_token = tokens[0]
    else:
        request_token = raw_input

    if not request_token:
        raise ValueError("request_token is empty.")

    print(f"[zerodha.auth] Exchanging request_token: {request_token}")

    # ── Exchange with Zerodha ───────────────────────────────────────────────
    kite = KiteConnect(api_key=api_key)
    session = kite.generate_session(request_token, api_secret=api_secret)
    access_token: str = session["access_token"]

    print(f"[zerodha.auth] Access token obtained, saving to .env")
    _write_env_key("ZERODHA_ACCESS_TOKEN", access_token)

    return access_token


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _write_env_key(key: str, value: str) -> None:
    """
    Update or append a key=value pair in the .env file.

    Reads the file line-by-line; if the key already exists its line is
    replaced in-place, otherwise the key is appended at the end.
    Creates the .env file if it does not exist yet.
    """
    env_path = _ENV_FILE

    if env_path.exists():
        original = env_path.read_text(encoding="utf-8")
        pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
        if pattern.search(original):
            updated = pattern.sub(f"{key}={value}", original)
        else:
            updated = original.rstrip("\n") + f"\n{key}={value}\n"
        env_path.write_text(updated, encoding="utf-8")
    else:
        env_path.write_text(f"{key}={value}\n", encoding="utf-8")
