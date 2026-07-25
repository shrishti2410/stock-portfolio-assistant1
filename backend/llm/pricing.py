"""
pricing.py — per-model token pricing (USD per 1M tokens) for cost calculation.

These are ESTIMATES (update as provider prices change). The mechanism matters
more than exact numbers — the gateway uses these to compute and cap spend.
Free providers (Groq, Gemini free tier) are priced at 0.
"""

# (input_per_1m, output_per_1m) in USD
PRICING = {
    # Anthropic Claude
    "claude-opus-4-8":            (15.0, 75.0),
    "claude-opus-4-8[1m]":        (15.0, 75.0),
    "claude-sonnet-4-6":          (3.0, 15.0),
    "claude-haiku-4-5-20251001":  (1.0, 5.0),
    "claude-haiku-4-5":           (1.0, 5.0),

    # OpenAI
    "gpt-4o":                     (2.5, 10.0),
    "gpt-4o-mini":                (0.15, 0.60),
    "gpt-4.1":                    (2.0, 8.0),
    "gpt-4.1-mini":               (0.40, 1.60),
    "o4-mini":                    (1.1, 4.4),

    # Free / effectively-free tiers
    "llama-3.3-70b-versatile":    (0.0, 0.0),   # Groq free
    "gemini-2.0-flash":           (0.0, 0.0),   # Gemini free tier
    "gemini-1.5-flash":           (0.0, 0.0),
}

# Fallback pricing for unknown models (conservative — assume mid-tier cost so
# the budget guard never under-estimates).
DEFAULT_PRICE = (3.0, 15.0)


def price_for(model: str) -> tuple[float, float]:
    """Return (input_per_1m, output_per_1m) USD for a model."""
    if not model:
        return DEFAULT_PRICE
    if model in PRICING:
        return PRICING[model]
    # Prefix match (e.g. versioned model ids)
    for key, val in PRICING.items():
        if model.startswith(key) or key.startswith(model):
            return val
    return DEFAULT_PRICE


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost for a call."""
    in_price, out_price = price_for(model)
    return round(
        (input_tokens / 1_000_000) * in_price +
        (output_tokens / 1_000_000) * out_price,
        6,
    )


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) for pre-call budget checks."""
    return max(1, len(text or "") // 4)


def provider_for_model(model: str) -> str:
    """Infer provider from model name."""
    m = (model or "").lower()
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if "llama" in m or "mixtral" in m or "groq" in m:
        return "groq"
    if "gemini" in m:
        return "gemini"
    return "anthropic"
