"""
gateway.py — the SINGLE entry point for every LLM call in the app.

Nothing should call an LLM provider directly. This gateway enforces:
  • master enable switch
  • per-call max output tokens cap
  • daily + monthly USD budget caps (HARD cutoff — call is refused, not just logged)
  • rate limiting (calls/min)
  • response caching (identical prompt → no second charge)
  • full usage logging (tokens, cost, latency, status) for observability

Usage:
    from llm.gateway import complete, LLMError
    res = await complete("Summarize…", feature="strategy_chat", max_tokens=400)
    print(res.text, res.cost_usd, res.input_tokens, res.output_tokens)
"""
import asyncio
import hashlib
import os
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import date

from .pricing import cost_usd, estimate_tokens, price_for, provider_for_model


# ── Exceptions ─────────────────────────────────────────────────
class LLMError(Exception):
    """Base — carries a machine status code for the API layer."""
    status = "error"

class LLMDisabled(LLMError):
    status = "disabled"

class BudgetExceeded(LLMError):
    status = "budget_blocked"

class RateLimited(LLMError):
    status = "rate_limited"

class ProviderError(LLMError):
    status = "error"


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cached: bool
    latency_ms: int
    status: str = "ok"

    def to_dict(self):
        return asdict(self)


# ── In-process rate limiter (single uvicorn worker) ────────────
_call_times: deque = deque(maxlen=240)


# ── Config ─────────────────────────────────────────────────────
async def get_config() -> dict:
    from db.database import _get_db
    import aiosqlite
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute("INSERT OR IGNORE INTO llm_config (id) VALUES (1)")
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM llm_config WHERE id = 1")
        return dict(rows[0]) if rows else {}


async def update_config(updates: dict) -> dict:
    from db.database import _get_db
    allowed = {
        "enabled", "provider", "default_model", "daily_limit_usd",
        "monthly_limit_usd", "per_call_max_tokens", "calls_per_min", "cache_enabled",
    }
    fields = {k: (1 if isinstance(v, bool) and v else 0 if isinstance(v, bool) else v)
              for k, v in updates.items() if k in allowed}
    if not fields:
        return await get_config()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    async with _get_db() as db:
        await db.execute("INSERT OR IGNORE INTO llm_config (id) VALUES (1)")
        await db.execute(
            f"UPDATE llm_config SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            list(fields.values()),
        )
        await db.commit()
    return await get_config()


# ── Spend tracking ─────────────────────────────────────────────
async def _spend(period: str) -> float:
    """Sum cost_usd over 'today' or 'month'."""
    from db.database import _get_db
    import aiosqlite
    if period == "today":
        where = "date(created_at) = date('now', 'localtime')"
    else:  # month
        where = "strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now', 'localtime')"
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            f"SELECT COALESCE(SUM(cost_usd), 0) AS total FROM llm_usage WHERE {where}"
        )
        return float(rows[0]["total"] or 0)


async def _log_usage(*, feature, provider, model, input_tokens, output_tokens,
                     cost, cached, latency_ms, status, error=None):
    from db.database import _get_db
    async with _get_db() as db:
        await db.execute(
            """INSERT INTO llm_usage
               (feature, provider, model, input_tokens, output_tokens, cost_usd,
                cached, latency_ms, status, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (feature, provider, model, input_tokens, output_tokens, cost,
             1 if cached else 0, latency_ms, status, error),
        )
        await db.commit()


# ── Cache ──────────────────────────────────────────────────────
def _cache_key(provider, model, system, prompt, max_tokens) -> str:
    raw = f"{provider}|{model}|{system or ''}|{prompt}|{max_tokens}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _cache_get(key: str) -> str | None:
    from db.database import _get_db
    import aiosqlite
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT response FROM llm_cache WHERE cache_key = ?", (key,))
        return rows[0]["response"] if rows else None


async def _cache_put(key: str, response: str, model: str):
    from db.database import _get_db
    async with _get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO llm_cache (cache_key, response, model) VALUES (?, ?, ?)",
            (key, response, model),
        )
        await db.commit()


# ── Provider calls (blocking SDKs → run in thread) ─────────────
def _call_anthropic(model, system, prompt, max_tokens, temperature):
    from anthropic import Anthropic
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise ProviderError("ANTHROPIC_API_KEY not set")
    client = Anthropic(api_key=key)
    msg = client.messages.create(
        model=model, max_tokens=max_tokens, temperature=temperature,
        system=system or "You are a helpful trading-strategy assistant.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
    return text, msg.usage.input_tokens, msg.usage.output_tokens


def _call_openai(model, system, prompt, max_tokens, temperature):
    from openai import OpenAI
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ProviderError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=model, messages=messages, max_tokens=max_tokens, temperature=temperature,
    )
    text = resp.choices[0].message.content or ""
    u = resp.usage
    return text, u.prompt_tokens, u.completion_tokens


def _call_groq(model, system, prompt, max_tokens, temperature):
    from groq import Groq
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise ProviderError("GROQ_API_KEY not set")
    client = Groq(api_key=key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=model, messages=messages, max_tokens=max_tokens, temperature=temperature,
    )
    text = resp.choices[0].message.content or ""
    u = resp.usage
    return text, u.prompt_tokens, u.completion_tokens


def _call_gemini(model, system, prompt, max_tokens, temperature):
    import google.generativeai as genai
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        raise ProviderError("GOOGLE_API_KEY not set")
    genai.configure(api_key=key)
    gm = genai.GenerativeModel(model, system_instruction=system or None)
    resp = gm.generate_content(
        prompt,
        generation_config={"max_output_tokens": max_tokens, "temperature": temperature},
    )
    text = resp.text or ""
    # Gemini usage metadata
    um = getattr(resp, "usage_metadata", None)
    in_tok = getattr(um, "prompt_token_count", estimate_tokens(prompt)) if um else estimate_tokens(prompt)
    out_tok = getattr(um, "candidates_token_count", estimate_tokens(text)) if um else estimate_tokens(text)
    return text, in_tok, out_tok


_PROVIDERS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "groq": _call_groq,
    "gemini": _call_gemini,
}


# ── Main entry point ───────────────────────────────────────────
async def complete(prompt: str, *, feature: str, system: str = None,
                   max_tokens: int = None, model: str = None,
                   temperature: float = 0.6, allow_cache: bool = True) -> LLMResult:
    """
    Run one LLM completion through all cost guards. Raises LLMError subclasses
    when blocked (disabled / budget / rate-limit / provider error).
    """
    cfg = await get_config()

    # 1) master switch
    if not cfg.get("enabled", 1):
        await _log_usage(feature=feature, provider="-", model="-", input_tokens=0,
                         output_tokens=0, cost=0, cached=False, latency_ms=0,
                         status="disabled", error="LLM features disabled in config")
        raise LLMDisabled("LLM features are disabled. Enable them in Settings → LLM.")

    model = model or cfg.get("default_model") or "claude-haiku-4-5-20251001"
    provider = cfg.get("provider") or provider_for_model(model)
    # cap output tokens
    cap = int(cfg.get("per_call_max_tokens", 1500))
    max_tokens = min(int(max_tokens or cap), cap)

    # 2) cache
    cache_enabled = bool(cfg.get("cache_enabled", 1)) and allow_cache
    ckey = _cache_key(provider, model, system, prompt, max_tokens)
    if cache_enabled:
        hit = await _cache_get(ckey)
        if hit is not None:
            await _log_usage(feature=feature, provider=provider, model=model,
                             input_tokens=0, output_tokens=0, cost=0, cached=True,
                             latency_ms=0, status="ok")
            return LLMResult(text=hit, model=model, provider=provider, input_tokens=0,
                             output_tokens=0, cost_usd=0.0, cached=True, latency_ms=0)

    # 3) rate limit
    now = time.time()
    cpm = int(cfg.get("calls_per_min", 12))
    recent = [t for t in _call_times if now - t < 60]
    if len(recent) >= cpm:
        await _log_usage(feature=feature, provider=provider, model=model, input_tokens=0,
                         output_tokens=0, cost=0, cached=False, latency_ms=0,
                         status="rate_limited", error=f"{cpm}/min exceeded")
        raise RateLimited(f"Rate limit reached ({cpm} calls/min). Try again shortly.")

    # 4) budget pre-check (worst case: full max_tokens of output)
    est_in = estimate_tokens((system or "") + prompt)
    est_cost = cost_usd(model, est_in, max_tokens)
    spend_today = await _spend("today")
    spend_month = await _spend("month")
    daily_limit = float(cfg.get("daily_limit_usd", 1.0))
    monthly_limit = float(cfg.get("monthly_limit_usd", 10.0))

    if spend_today + est_cost > daily_limit:
        await _log_usage(feature=feature, provider=provider, model=model, input_tokens=0,
                         output_tokens=0, cost=0, cached=False, latency_ms=0,
                         status="budget_blocked",
                         error=f"daily ${spend_today:.4f}+${est_cost:.4f} > ${daily_limit}")
        raise BudgetExceeded(
            f"Daily LLM budget reached (${spend_today:.3f} of ${daily_limit:.2f}). "
            f"Raise the limit in Settings → LLM or wait until tomorrow."
        )
    if spend_month + est_cost > monthly_limit:
        await _log_usage(feature=feature, provider=provider, model=model, input_tokens=0,
                         output_tokens=0, cost=0, cached=False, latency_ms=0,
                         status="budget_blocked",
                         error=f"monthly ${spend_month:.4f}+${est_cost:.4f} > ${monthly_limit}")
        raise BudgetExceeded(
            f"Monthly LLM budget reached (${spend_month:.3f} of ${monthly_limit:.2f}). "
            f"Raise the limit in Settings → LLM."
        )

    # 5) call provider
    fn = _PROVIDERS.get(provider)
    if not fn:
        raise ProviderError(f"Unknown provider '{provider}'")

    _call_times.append(now)
    start = time.time()
    try:
        text, in_tok, out_tok = await asyncio.to_thread(
            fn, model, system, prompt, max_tokens, temperature
        )
    except LLMError:
        raise
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        await _log_usage(feature=feature, provider=provider, model=model, input_tokens=0,
                         output_tokens=0, cost=0, cached=False, latency_ms=latency,
                         status="error", error=str(e)[:300])
        raise ProviderError(f"{provider} call failed: {e}")

    latency = int((time.time() - start) * 1000)
    actual_cost = cost_usd(model, in_tok, out_tok)

    await _log_usage(feature=feature, provider=provider, model=model,
                     input_tokens=in_tok, output_tokens=out_tok, cost=actual_cost,
                     cached=False, latency_ms=latency, status="ok")

    if cache_enabled:
        await _cache_put(ckey, text, model)

    return LLMResult(text=text, model=model, provider=provider, input_tokens=in_tok,
                     output_tokens=out_tok, cost_usd=actual_cost, cached=False,
                     latency_ms=latency)


# ── Observability summary ──────────────────────────────────────
async def usage_summary() -> dict:
    from db.database import _get_db
    import aiosqlite
    cfg = await get_config()
    today = await _spend("today")
    month = await _spend("month")

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        by_feature = [dict(r) for r in await db.execute_fetchall(
            """SELECT feature, COUNT(*) AS calls, COALESCE(SUM(cost_usd),0) AS cost,
                      COALESCE(SUM(input_tokens),0) AS in_tok, COALESCE(SUM(output_tokens),0) AS out_tok
               FROM llm_usage
               WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m','now','localtime')
               GROUP BY feature ORDER BY cost DESC"""
        )]
        recent = [dict(r) for r in await db.execute_fetchall(
            """SELECT created_at, feature, model, input_tokens, output_tokens,
                      cost_usd, cached, status FROM llm_usage
               ORDER BY created_at DESC LIMIT 25"""
        )]
        totals = dict((await db.execute_fetchall(
            """SELECT COUNT(*) AS calls,
                      COALESCE(SUM(CASE WHEN cached=1 THEN 1 ELSE 0 END),0) AS cached_calls,
                      COALESCE(SUM(CASE WHEN status='budget_blocked' THEN 1 ELSE 0 END),0) AS blocked
               FROM llm_usage"""
        ))[0])

    daily_limit = float(cfg.get("daily_limit_usd", 1.0))
    monthly_limit = float(cfg.get("monthly_limit_usd", 10.0))
    return {
        "config": cfg,
        "spend_today_usd": round(today, 5),
        "spend_month_usd": round(month, 5),
        "daily_limit_usd": daily_limit,
        "monthly_limit_usd": monthly_limit,
        "daily_remaining_usd": round(max(0, daily_limit - today), 5),
        "monthly_remaining_usd": round(max(0, monthly_limit - month), 5),
        "daily_pct": round(min(100, today / daily_limit * 100), 1) if daily_limit else 0,
        "monthly_pct": round(min(100, month / monthly_limit * 100), 1) if monthly_limit else 0,
        "by_feature": by_feature,
        "recent": recent,
        "totals": totals,
    }
