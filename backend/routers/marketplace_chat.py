"""
routers/marketplace_chat.py — Chat-with-LLM strategy authoring API.

Endpoints:
    POST /api/marketplace/chat                one chat turn
                                              body {session_id?, message}
                                              (session_id auto-generated if absent)
    GET  /api/marketplace/chat/{session_id}   full thread + latest draft
    POST /api/marketplace/chat/{session_id}/save
                                              save latest draft to the
                                              marketplace registry -> {slug}

LLM cost-guard failures (budget/rate-limit/disabled/provider) surface as
HTTP 400 with detail {status, message} so the UI can render budget blocks
distinctly from generic errors.
"""

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from llm import strategy_chat
from llm.gateway import LLMError

router = APIRouter(prefix="/api/marketplace/chat", tags=["marketplace-chat"])


@router.post("")
async def post_chat_turn(body: dict):
    """Run one authoring turn. Generates a session_id when the body omits one."""
    body = body or {}
    message = str(body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    session_id = str(body.get("session_id") or "").strip() or uuid4().hex

    try:
        return await strategy_chat.chat_turn(session_id, message)
    except LLMError as e:
        # Machine-readable status lets the UI distinguish budget blocks
        # (budget_blocked / rate_limited / disabled) from plain errors.
        raise HTTPException(
            status_code=400, detail={"status": e.status, "message": str(e)}
        )


@router.get("/{session_id}")
async def get_chat_history(session_id: str):
    """Message thread + latest non-null draft for a session."""
    return await strategy_chat.get_history(session_id)


@router.post("/{session_id}/save")
async def save_chat_draft(session_id: str):
    """Persist the session's latest draft as a marketplace strategy (source=llm)."""
    try:
        slug = await strategy_chat.save_draft(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"slug": slug}
