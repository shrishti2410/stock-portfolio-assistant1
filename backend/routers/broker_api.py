"""
broker_api.py — per-user Zerodha broker credential management (prefix /api/broker).

  GET    /api/broker/status  -> is Zerodha configured for the current user, and how
  PUT    /api/broker/zerodha -> set (partial-update) the current user's Zerodha creds
  DELETE /api/broker/zerodha -> remove the current user's Zerodha creds
  POST   /api/broker/test    -> attempt a real holdings fetch with current creds

Credentials are stored per-user (auth/service.py user_settings, Fernet-encrypted
at rest) rather than in a shared .env file, so each user can connect their own
Zerodha account from the Settings UI.
"""

import asyncio
import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import service
from routers.auth_api import get_current_user
from zerodha.client import _get_holdings_via_console, _resolve_creds_for_user

router = APIRouter(prefix="/api/broker", tags=["broker"])

_ZERODHA_KEYS = ("zerodha_user_id", "zerodha_password", "zerodha_totp_secret")


class ZerodhaCredsRequest(BaseModel):
    # Accept BOTH the frontend's field names (zerodha_*) and the internal
    # short names so the UI and any script both work.
    user_id_field: str | None = None
    password: str | None = None
    totp_secret: str | None = None
    zerodha_user_id: str | None = None
    zerodha_password: str | None = None
    zerodha_totp_secret: str | None = None

    def resolved(self) -> dict:
        """Merge the two naming styles → {user_id, password, totp_secret}."""
        return {
            "user_id": self.zerodha_user_id or self.user_id_field,
            "password": self.zerodha_password or self.password,
            "totp_secret": self.zerodha_totp_secret or self.totp_secret,
        }


def _env_configured() -> bool:
    return bool(
        os.getenv("ZERODHA_USER_ID", "").strip()
        and os.getenv("ZERODHA_PASSWORD", "").strip()
        and os.getenv("ZERODHA_TOTP_SECRET", "").strip()
    )


async def _zerodha_fields(user_id: int) -> list[dict]:
    meta = await service.get_user_settings_meta(user_id)
    return [m for m in meta if m["key"] in _ZERODHA_KEYS]


@router.get("/status")
async def broker_status(user: dict = Depends(get_current_user)):
    """
    Whether Zerodha is configured for the current user, and from where.

    source:
      "user"      -> the user has their own complete credential set
      "env-admin" -> admin user, falling back to legacy .env credentials
      "none"      -> not configured at all
    """
    fields = await _zerodha_fields(user["id"])
    configured_keys = {f["key"] for f in fields}
    user_configured = all(k in configured_keys for k in _ZERODHA_KEYS)

    if user_configured:
        return {"configured": True, "fields": fields, "source": "user"}

    if user.get("is_admin") and _env_configured():
        return {"configured": True, "fields": fields, "source": "env-admin"}

    return {"configured": False, "fields": fields, "source": "none"}


@router.put("/zerodha")
async def set_zerodha_creds(body: ZerodhaCredsRequest, user: dict = Depends(get_current_user)):
    """Set (partial-update) the current user's Zerodha credentials. Only non-empty fields overwrite."""
    vals = body.resolved()
    key_map = {
        "user_id": "zerodha_user_id",
        "password": "zerodha_password",
        "totp_secret": "zerodha_totp_secret",
    }
    updated: list[str] = []
    for field, setting_key in key_map.items():
        v = vals.get(field)
        if v and v.strip():
            await service.set_user_setting(user["id"], setting_key, v.strip(), encrypt=True)
            updated.append(setting_key)

    fields = await _zerodha_fields(user["id"])
    return {"status": "updated", "updated_fields": updated, "fields": fields}


@router.delete("/zerodha")
async def delete_zerodha_creds(user: dict = Depends(get_current_user)):
    """Remove all three Zerodha credential settings for the current user."""
    for key in _ZERODHA_KEYS:
        await service.delete_user_setting(user["id"], key)
    return {"status": "deleted"}


@router.post("/test")
async def test_zerodha_connection(user: dict = Depends(get_current_user)):
    """
    Attempt a real holdings fetch using the current user's resolved credentials
    (own settings, or admin env fallback). Unlike get_holdings_for_user(), this
    does NOT silently fall back to dummy data — failures are surfaced so the
    "Test Connection" button reflects reality. 30s max, never raises.
    """
    async def _run_test() -> dict:
        creds = await _resolve_creds_for_user(user)
        if creds is None:
            return {"ok": False, "error": "Zerodha credentials not configured for this user"}
        holdings = await asyncio.to_thread(_get_holdings_via_console, *creds)
        return {"ok": True, "holdings_count": len(holdings or [])}

    try:
        return await asyncio.wait_for(_run_test(), timeout=30.0)
    except asyncio.TimeoutError:
        return {"ok": False, "error": "Connection test timed out after 30 seconds"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
