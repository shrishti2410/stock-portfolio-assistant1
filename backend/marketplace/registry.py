"""
registry.py — Unified Strategy Registry (marketplace).

Async CRUD over the strategy_defs table. One row per strategy regardless of
source ('predefined' | 'it_bear' | 'custom' | 'llm'). JSON columns
(entry_conditions, exit_conditions, legs, config, tags) are parsed on read
and serialized on write.

Condition element shape:
    {"indicator": str,
     "operator": "gt|lt|gte|lte|eq|between|raw|time_window",
     "value": any,
     "note": str}
Legacy free-text conditions use operator "raw" with value = the condition text.

Rules enforced here:
    - update_strategy: only rows with is_editable=1 (ValueError otherwise)
    - delete_strategy: only source in ('custom', 'llm') or forked rows
    - missing slug raises KeyError (router maps to 404)
"""

import json
import re

import aiosqlite

from db.database import _get_db

SOURCES = ("predefined", "it_bear", "custom", "llm")

_JSON_LIST_FIELDS = ("entry_conditions", "exit_conditions", "legs", "tags")
_JSON_DICT_FIELDS = ("config",)
_UPDATABLE_FIELDS = {
    "name", "category", "market", "direction", "description",
    "entry_conditions", "exit_conditions", "legs", "config", "risk", "tags",
}


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """'My Mean-Reversion v2' -> 'my-mean-reversion-v2'."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or "strategy"


def _loads(raw, default):
    """Parse a JSON column value, tolerating NULL / already-parsed values."""
    if raw is None or raw == "":
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _dumps(value, default):
    """Serialize a python value for a JSON column; pass through valid JSON strings."""
    if value is None:
        value = default
    if isinstance(value, str):
        try:
            json.loads(value)
            return value  # already serialized JSON — store as-is
        except (TypeError, ValueError):
            return json.dumps(value)
    return json.dumps(value)


def parse_row(row) -> dict:
    """Convert a strategy_defs row to a dict with JSON fields parsed."""
    out = dict(row)
    for field in _JSON_LIST_FIELDS:
        out[field] = _loads(out.get(field), [])
    for field in _JSON_DICT_FIELDS:
        out[field] = _loads(out.get(field), {})
    return out


# ---------------------------------------------------------------------------
# Low-level helpers (operate on an open connection; shared with seeds.py)
# ---------------------------------------------------------------------------

async def _slug_exists(db, slug: str) -> bool:
    rows = await db.execute_fetchall(
        "SELECT 1 FROM strategy_defs WHERE slug = ?", (slug,)
    )
    return bool(rows)


async def _unique_slug(db, base: str) -> str:
    """Return base, or base-2 / base-3 / ... until unused."""
    slug = base
    n = 2
    while await _slug_exists(db, slug):
        slug = f"{base}-{n}"
        n += 1
    return slug


async def _fetch_by_slug(db, slug: str) -> dict | None:
    rows = await db.execute_fetchall(
        "SELECT * FROM strategy_defs WHERE slug = ?", (slug,)
    )
    return dict(rows[0]) if rows else None


async def _insert_row(db, data: dict) -> None:
    """Low-level insert. Expects data['slug'] to be unique already. No commit."""
    await db.execute(
        """INSERT INTO strategy_defs
               (slug, name, source, category, market, direction, description,
                entry_conditions, exit_conditions, legs, config, risk, tags,
                is_editable, forked_from)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["slug"],
            data["name"],
            data.get("source") or "custom",
            data.get("category"),
            data.get("market") or "IN",
            data.get("direction"),
            data.get("description"),
            _dumps(data.get("entry_conditions"), []),
            _dumps(data.get("exit_conditions"), []),
            _dumps(data.get("legs"), []),
            _dumps(data.get("config"), {}),
            data.get("risk"),
            _dumps(data.get("tags"), []),
            1 if data.get("is_editable", 1) else 0,
            data.get("forked_from"),
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def list_strategies(
    source: str | None = None,
    category: str | None = None,
    market: str | None = None,
    q: str | None = None,
) -> list[dict]:
    """List strategies with optional filters. JSON fields come back parsed."""
    conditions: list[str] = []
    params: list = []

    if source:
        conditions.append("source = ?")
        params.append(source)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if market:
        if market in ("IN", "US"):
            # A strategy tagged BOTH applies to either single market.
            conditions.append("(market = ? OR market = 'BOTH')")
        else:
            conditions.append("market = ?")
        params.append(market)
    if q:
        like = f"%{q}%"
        conditions.append(
            "(name LIKE ? OR description LIKE ? OR slug LIKE ? OR tags LIKE ?)"
        )
        params.extend([like, like, like, like])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            f"SELECT * FROM strategy_defs {where} ORDER BY source, name", params
        )
        return [parse_row(r) for r in rows]


async def get_strategy(slug: str) -> dict | None:
    """Fetch one strategy by slug (JSON fields parsed), or None."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        row = await _fetch_by_slug(db, slug)
        return parse_row(row) if row else None


async def create_strategy(data: dict) -> str:
    """Insert a new strategy. Slug derived from name, uniquified with -2, -3, ...

    Returns the new slug. Raises ValueError if name is missing.
    """
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")

    source = data.get("source") if data.get("source") in SOURCES else "custom"

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        slug = await _unique_slug(db, _slugify(name))
        payload = dict(data)
        payload.update({"slug": slug, "name": name, "source": source})
        payload.setdefault("is_editable", 1)
        await _insert_row(db, payload)
        await db.commit()

    return slug


async def update_strategy(slug: str, updates: dict) -> dict:
    """Update an editable strategy. Returns the updated (parsed) row.

    Raises KeyError if slug missing, ValueError if the row is not editable.
    """
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        row = await _fetch_by_slug(db, slug)
        if row is None:
            raise KeyError(f"strategy '{slug}' not found")
        if not row.get("is_editable"):
            raise ValueError(
                f"strategy '{slug}' is not editable — fork it to make changes"
            )

        fields = {k: v for k, v in (updates or {}).items() if k in _UPDATABLE_FIELDS}
        if fields:
            sets: list[str] = []
            params: list = []
            for key, value in fields.items():
                if key in _JSON_LIST_FIELDS:
                    value = _dumps(value, [])
                elif key in _JSON_DICT_FIELDS:
                    value = _dumps(value, {})
                sets.append(f"{key} = ?")
                params.append(value)
            params.append(slug)
            await db.execute(
                f"UPDATE strategy_defs SET {', '.join(sets)}, "
                f"updated_at = CURRENT_TIMESTAMP WHERE slug = ?",
                params,
            )
            await db.commit()

        row = await _fetch_by_slug(db, slug)
        return parse_row(row)


async def delete_strategy(slug: str) -> bool:
    """Delete a strategy. Only allowed for source custom/llm or forked rows.

    Raises KeyError if slug missing, ValueError if deletion is not allowed.
    """
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        row = await _fetch_by_slug(db, slug)
        if row is None:
            raise KeyError(f"strategy '{slug}' not found")
        if row.get("source") not in ("custom", "llm") and not row.get("forked_from"):
            raise ValueError(
                f"strategy '{slug}' is a built-in ({row.get('source')}) and cannot "
                f"be deleted — only custom, llm or forked strategies can be removed"
            )
        await db.execute("DELETE FROM strategy_defs WHERE slug = ?", (slug,))
        await db.commit()
    return True


async def fork_strategy(slug: str, new_name: str | None = None) -> str:
    """Copy a strategy into an editable custom row. Returns the new slug.

    New row: source='custom', is_editable=1, forked_from=<orig slug>,
    slug = '<orig>-fork' (uniquified with -2, -3, ... on collision).
    Raises KeyError if the original slug is missing.
    """
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        orig = await _fetch_by_slug(db, slug)
        if orig is None:
            raise KeyError(f"strategy '{slug}' not found")

        new_slug = await _unique_slug(db, f"{slug}-fork")
        payload = {
            "slug": new_slug,
            "name": (new_name or "").strip() or f"{orig['name']} (Fork)",
            "source": "custom",
            "category": orig.get("category"),
            "market": orig.get("market"),
            "direction": orig.get("direction"),
            "description": orig.get("description"),
            "entry_conditions": orig.get("entry_conditions"),
            "exit_conditions": orig.get("exit_conditions"),
            "legs": orig.get("legs"),
            "config": orig.get("config"),
            "risk": orig.get("risk"),
            "tags": orig.get("tags"),
            "is_editable": 1,
            "forked_from": slug,
        }
        await _insert_row(db, payload)
        await db.commit()

    return new_slug
