"""
service.py — multi-user auth + per-user settings (async, aiosqlite-backed).

Covers:
  - user CRUD (create/list/delete, password change)
  - authentication (username + password -> user dict)
  - session tokens (create / resolve / delete, with expiry)
  - per-user key/value settings, optionally Fernet-encrypted at rest
    (used for storing per-user Zerodha broker credentials)

All functions are async and use the same aiosqlite connection pattern as
db/database.py (`async with _get_db() as db: db.row_factory = aiosqlite.Row`).
"""

from datetime import datetime, timedelta, timezone

import aiosqlite

from db.database import _get_db

from .crypto import decrypt_str, encrypt_str
from .security import hash_password, new_session_token, verify_password

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_user(row: aiosqlite.Row) -> dict:
    """Project a `users` row (or a join that includes all its columns) to a
    safe public dict — password_hash is intentionally never included."""
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "is_admin": bool(row["is_admin"]),
        "created_at": row["created_at"],
    }


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


async def create_user(
    username: str,
    password: str,
    display_name: str | None = None,
    is_admin: bool = False,
) -> dict:
    """Create a new user. Raises ValueError if the username already exists."""
    username = (username or "").strip()
    if not username:
        raise ValueError("username is required")
    if not password:
        raise ValueError("password is required")

    password_hash = hash_password(password)

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(
                """INSERT INTO users (username, password_hash, display_name, is_admin)
                   VALUES (?, ?, ?, ?)""",
                (username, password_hash, display_name, 1 if is_admin else 0),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            raise ValueError(f"Username '{username}' already exists")

        rows = await db.execute_fetchall("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,))
        return _row_to_user(rows[0])


async def authenticate(username: str, password: str) -> dict | None:
    """Return the user dict if username/password are valid, else None."""
    if not username or not password:
        return None

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        )
        if not rows:
            return None
        row = rows[0]
        if not verify_password(password, row["password_hash"]):
            return None
        return _row_to_user(row)


async def list_users() -> list[dict]:
    """List all users (no password hashes)."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM users ORDER BY id")
        return [_row_to_user(r) for r in rows]


async def delete_user(user_id: int) -> bool:
    """
    Delete a user (cascades to their sessions + user_settings).

    Refuses to delete the last remaining admin (raises ValueError) so the
    app never ends up with zero admins able to manage other users.
    Returns False if the user doesn't exist, True if deleted.
    """
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM users WHERE id = ?", (user_id,))
        if not rows:
            return False

        target = rows[0]
        if target["is_admin"]:
            admin_rows = await db.execute_fetchall(
                "SELECT COUNT(*) AS cnt FROM users WHERE is_admin = 1"
            )
            if admin_rows[0]["cnt"] <= 1:
                raise ValueError("Cannot delete the last remaining admin user")

        cursor = await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0


async def change_password(user_id: int, new_password: str) -> bool:
    """Set a new password for a user. Returns True if a row was updated."""
    if not new_password:
        raise ValueError("new_password is required")

    password_hash = hash_password(new_password)
    async with _get_db() as db:
        cursor = await db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


async def create_session(user_id: int, days: int = 30) -> str:
    """Create a new session for a user, returning the opaque token."""
    token = new_session_token()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    async with _get_db() as db:
        await db.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )
        await db.commit()

    return token


async def get_session_user(token: str | None) -> dict | None:
    """
    Resolve a session token to its user. Returns None (and deletes the row)
    if the token doesn't exist or has expired.
    """
    if not token:
        return None

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """SELECT u.*, s.expires_at AS session_expires_at
               FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token = ?""",
            (token,),
        )
        if not rows:
            return None

        row = rows[0]
        expires_at = _parse_iso(row["session_expires_at"])
        if expires_at is not None and expires_at < datetime.now(timezone.utc):
            await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
            await db.commit()
            return None

        return _row_to_user(row)


async def delete_session(token: str | None) -> None:
    """Delete a session (logout). No-op if the token doesn't exist."""
    if not token:
        return
    async with _get_db() as db:
        await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await db.commit()


# ---------------------------------------------------------------------------
# Per-user settings (broker credentials, etc.)
# ---------------------------------------------------------------------------


async def set_user_setting(user_id: int, key: str, value: str, encrypt: bool = False) -> None:
    """Upsert a per-user setting. If encrypt=True, `value` is Fernet-encrypted at rest."""
    stored_value = encrypt_str(value) if encrypt else value

    async with _get_db() as db:
        await db.execute(
            """INSERT INTO user_settings (user_id, key, value, encrypted, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, key) DO UPDATE SET
                   value = excluded.value,
                   encrypted = excluded.encrypted,
                   updated_at = CURRENT_TIMESTAMP""",
            (user_id, key, stored_value, 1 if encrypt else 0),
        )
        await db.commit()


async def get_user_setting(user_id: int, key: str) -> str | None:
    """Get a per-user setting's decrypted value, or None if not set."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT value, encrypted FROM user_settings WHERE user_id = ? AND key = ?",
            (user_id, key),
        )
        if not rows or rows[0]["value"] is None:
            return None
        row = rows[0]
        return decrypt_str(row["value"]) if row["encrypted"] else row["value"]


async def get_user_settings_meta(user_id: int) -> list[dict]:
    """
    List all settings for a user WITHOUT exposing full secret values.

    Returns [{key, encrypted, updated_at, preview}]:
      - encrypted values: preview is masked, showing only the last 4 chars
        (e.g. "••••1234"), or "••••" if shorter than 4 chars.
      - non-encrypted values: preview is the raw value (not considered sensitive).
    """
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT key, value, encrypted, updated_at FROM user_settings WHERE user_id = ? ORDER BY key",
            (user_id,),
        )
        result = []
        for row in rows:
            encrypted = bool(row["encrypted"])
            raw_value = row["value"]

            if encrypted:
                decrypted = decrypt_str(raw_value) if raw_value else ""
                decrypted = decrypted or ""
                preview = f"••••{decrypted[-4:]}" if len(decrypted) >= 4 else ("••••" if decrypted else "")
            else:
                preview = raw_value or ""

            result.append({
                "key": row["key"],
                "encrypted": encrypted,
                "updated_at": row["updated_at"],
                "preview": preview,
            })
        return result


async def delete_user_setting(user_id: int, key: str) -> bool:
    """Delete a single per-user setting. Returns True if a row was removed."""
    async with _get_db() as db:
        cursor = await db.execute(
            "DELETE FROM user_settings WHERE user_id = ? AND key = ?", (user_id, key)
        )
        await db.commit()
        return cursor.rowcount > 0
