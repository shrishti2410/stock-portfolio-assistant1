"""
strategy_chat.py — Chat-with-LLM strategy authoring.

Multi-turn conversation that iteratively refines ONE strategy draft. Every
model reply carries the full current draft as a fenced ```json block; we parse
it out, persist a snapshot per assistant turn (strategy_chats table), and the
final draft can be saved into the marketplace registry (source='llm').

ALL model calls go through the cost-controlled gateway (llm.gateway.complete)
with feature="strategy_chat" — never a provider SDK directly.

Public API:
    await chat_turn(session_id, user_message) -> {session_id, reply, draft, usage}
    await get_history(session_id)             -> {messages, draft}
    await save_draft(session_id)              -> slug   (ValueError if no draft)
"""

import json
import re

import aiosqlite

from db.database import _get_db
from llm.gateway import complete

# ── System prompt ──────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert trading-strategy authoring assistant for Indian (NSE/BSE, F&O, MCX) and US markets. You help the user turn ideas into ONE precise, structured strategy draft through conversation.

Rules you MUST follow on every reply:
1. Keep the conversational part SHORT — at most 120 words.
2. THEN always append the full current strategy draft as a fenced json code block (```json ... ```). The json block is always the LAST thing in your message. Exactly one json block per reply.
3. The draft must follow this exact schema:
{"name": str, "description": str, "category": "options|directional|commodity|screening|event", "market": "IN|US|BOTH", "direction": "bullish|bearish|neutral|any", "risk": "low|medium|high", "entry_conditions": [{"indicator": str, "operator": str, "value": any, "note": str}], "exit_conditions": [{"indicator": str, "operator": str, "value": any, "note": str}], "config": {<tunable parameters, e.g. timeframe, stop_loss_pct, position_size>}}
4. "operator" is LIMITED to: gt, lt, gte, lte, eq, between, raw, time_window. Use "between" with value [low, high]; "time_window" for time-of-day rules (e.g. value "15:15"); "raw" only for conditions that don't fit an indicator comparison.
5. Ask at most ONE clarifying question per turn — never more. If details are missing, make sensible assumptions, state them briefly, and put tunables in "config".
6. REFINE the previous draft shown as "Current draft JSON" — apply the user's changes to it. Never restart from scratch unless the user explicitly asks.
7. Output valid JSON only inside the fence: double quotes, no comments, no trailing commas."""

_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)```", re.DOTALL | re.IGNORECASE)


# ── Parsing helpers ────────────────────────────────────────────

def parse_draft(text: str) -> dict | None:
    """Extract + parse the LAST ```json ... ``` block. None if absent/invalid."""
    if not text:
        return None
    matches = list(_JSON_BLOCK_RE.finditer(text))
    if not matches:
        return None
    try:
        draft = json.loads(matches[-1].group(1).strip())
    except (TypeError, ValueError):
        return None
    return draft if isinstance(draft, dict) else None


def _strip_json_blocks(text: str) -> str:
    """Remove all fenced json blocks (used for reply text + history replay)."""
    return _JSON_BLOCK_RE.sub("", text or "").strip()


def _reply_without_last_block(text: str) -> str:
    """Reply text = model output minus its (last) json block, trimmed."""
    if not text:
        return ""
    matches = list(_JSON_BLOCK_RE.finditer(text))
    if not matches:
        return text.strip()
    last = matches[-1]
    return (text[: last.start()] + text[last.end():]).strip()


# ── DB helpers ─────────────────────────────────────────────────

async def _load_rows(session_id: str) -> list[dict]:
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """SELECT role, content, draft, created_at
               FROM strategy_chats WHERE session_id = ?
               ORDER BY created_at, id""",
            (session_id,),
        )
        return [dict(r) for r in rows]


def _latest_draft(rows: list[dict]) -> dict | None:
    """Most recent non-null, parseable draft snapshot in the session."""
    for row in reversed(rows):
        raw = row.get("draft")
        if not raw:
            continue
        try:
            draft = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if isinstance(draft, dict):
            return draft
    return None


def _build_prompt(rows: list[dict], latest_draft: dict | None, user_message: str) -> str:
    """Single prompt string: replayed turns (assistant text sans json blocks),
    the latest draft included ONCE, then the new user message."""
    parts: list[str] = []
    for row in rows:
        if row["role"] == "user":
            parts.append(f"User: {row['content']}")
        else:
            reply = _strip_json_blocks(row["content"])
            if reply:
                parts.append(f"Assistant: {reply}")
    if latest_draft is not None:
        parts.append(
            "Current draft JSON: " + json.dumps(latest_draft, separators=(",", ":"))
        )
    parts.append(f"User: {user_message}")
    return "\n\n".join(parts)


# ── Public API ─────────────────────────────────────────────────

async def chat_turn(session_id: str, user_message: str) -> dict:
    """Run one authoring turn through the LLM gateway and persist it.

    Raises llm.gateway.LLMError subclasses when the call is blocked
    (disabled / budget / rate limit / provider failure) — nothing is
    persisted in that case.
    """
    user_message = (user_message or "").strip()
    if not user_message:
        raise ValueError("message is required")

    rows = await _load_rows(session_id)
    prior_draft = _latest_draft(rows)
    prompt = _build_prompt(rows, prior_draft, user_message)

    res = await complete(
        prompt,
        feature="strategy_chat",
        system=SYSTEM_PROMPT,
        max_tokens=900,
        temperature=0.4,
        allow_cache=False,
    )

    draft = parse_draft(res.text)
    reply_text = _reply_without_last_block(res.text)

    # Persist: user row, then assistant row (draft snapshot on assistant row).
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO strategy_chats (session_id, role, content) VALUES (?, 'user', ?)",
            (session_id, user_message),
        )
        await db.execute(
            "INSERT INTO strategy_chats (session_id, role, content, draft) VALUES (?, 'assistant', ?, ?)",
            (session_id, reply_text or res.text.strip(),
             json.dumps(draft) if draft is not None else None),
        )
        await db.commit()

    return {
        "session_id": session_id,
        "reply": reply_text,
        # If this turn's JSON was malformed, fall back to the previous draft
        # so the UI's draft panel never blanks out mid-session.
        "draft": draft if draft is not None else prior_draft,
        "usage": {
            "model": res.model,
            "provider": res.provider,
            "input_tokens": res.input_tokens,
            "output_tokens": res.output_tokens,
            "cost_usd": res.cost_usd,
            "cached": res.cached,
        },
    }


async def get_history(session_id: str) -> dict:
    """Full message thread + the latest non-null draft for a session."""
    rows = await _load_rows(session_id)
    return {
        "messages": [
            {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
            for r in rows
        ],
        "draft": _latest_draft(rows),
    }


async def save_draft(session_id: str) -> str:
    """Save the session's latest draft into the marketplace registry.

    Returns the new strategy slug. Raises ValueError if the session has no draft.
    """
    from marketplace import registry

    rows = await _load_rows(session_id)
    draft = _latest_draft(rows)
    if draft is None:
        raise ValueError("No strategy draft in this session yet — chat first.")

    tags = draft.get("tags") if isinstance(draft.get("tags"), list) else []
    if "ai" not in tags:
        tags = ["ai", *tags]

    return await registry.create_strategy(
        {
            "name": draft.get("name"),
            "description": draft.get("description"),
            "category": draft.get("category"),
            "market": draft.get("market") or "IN",
            "direction": draft.get("direction"),
            "risk": draft.get("risk"),
            "entry_conditions": draft.get("entry_conditions") or [],
            "exit_conditions": draft.get("exit_conditions") or [],
            "legs": draft.get("legs") or [],
            "config": draft.get("config") or {},
            "source": "llm",
            "tags": tags,
            "is_editable": 1,
        }
    )
