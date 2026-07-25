"""
seed.py — one-time (idempotent) startup bootstrap for multi-user auth.

Called from main.py's startup event, after init_db():

  1. If the `users` table is empty, create a default admin from
     APP_ADMIN_USER / APP_ADMIN_PASSWORD env vars (falling back to
     "admin" / "admin" — printing a loud warning to change it).
  2. Migrate legacy env-based Zerodha credentials (ZERODHA_USER_ID,
     ZERODHA_PASSWORD, ZERODHA_TOTP_SECRET) into the admin user's
     encrypted user_settings, if present and not already migrated.
     This runs on every startup but is a no-op once migrated (or once
     the admin has configured their own credentials via the UI).
"""

import os

from dotenv import load_dotenv

from . import service

# Load .env directly (rather than relying on import order/side-effects from
# other modules) so this module behaves correctly however it's invoked.
load_dotenv()


async def ensure_admin() -> dict | None:
    """
    Ensure at least one admin user exists, and migrate legacy env Zerodha
    credentials into that admin's settings if applicable.

    Returns the newly-created admin user dict, or None if an admin already
    existed (no user was created this call).
    """
    created_admin: dict | None = None
    users = await service.list_users()

    if not users:
        admin_username = (os.getenv("APP_ADMIN_USER", "admin") or "admin").strip() or "admin"
        admin_password = (os.getenv("APP_ADMIN_PASSWORD", "admin") or "admin").strip() or "admin"

        created_admin = await service.create_user(
            username=admin_username,
            password=admin_password,
            display_name="Administrator",
            is_admin=True,
        )

        print("=" * 70)
        print("[auth.seed] No users found — created default admin account:")
        print(f"[auth.seed]   username: {admin_username}")
        print(f"[auth.seed]   password: {admin_password}")
        print("[auth.seed] *** CHANGE THIS PASSWORD BEFORE USING IN PRODUCTION ***")
        print("[auth.seed] (set APP_ADMIN_USER / APP_ADMIN_PASSWORD in .env to customize)")
        print("=" * 70)

        users = [created_admin]

    admin = created_admin or next((u for u in users if u["is_admin"]), None)
    if admin:
        await _migrate_env_zerodha_creds(admin["id"])

    return created_admin


async def _migrate_env_zerodha_creds(admin_user_id: int) -> None:
    """
    One-time migration: if legacy ZERODHA_USER_ID/PASSWORD/TOTP_SECRET env
    vars are set and the admin doesn't already have a 'zerodha_user_id'
    setting, copy all three into the admin's encrypted user_settings.
    """
    already_migrated = await service.get_user_setting(admin_user_id, "zerodha_user_id")
    if already_migrated:
        return

    env_user_id = os.getenv("ZERODHA_USER_ID", "").strip()
    env_password = os.getenv("ZERODHA_PASSWORD", "").strip()
    env_totp_secret = os.getenv("ZERODHA_TOTP_SECRET", "").strip()

    if not (env_user_id and env_password and env_totp_secret):
        return

    await service.set_user_setting(admin_user_id, "zerodha_user_id", env_user_id, encrypt=True)
    await service.set_user_setting(admin_user_id, "zerodha_password", env_password, encrypt=True)
    await service.set_user_setting(admin_user_id, "zerodha_totp_secret", env_totp_secret, encrypt=True)

    print(
        "[auth.seed] Migrated legacy .env Zerodha credentials "
        "(ZERODHA_USER_ID / ZERODHA_PASSWORD / ZERODHA_TOTP_SECRET) into the "
        "admin account's encrypted per-user settings. You can now manage "
        "these from the Broker settings UI."
    )
