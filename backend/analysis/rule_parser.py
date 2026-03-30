"""
rule_parser.py — LLM-based natural language → structured rules

Uses Groq (free) to parse user input like:
  "Buy when RSI drops below 30 and MACD crosses above signal line"
into structured rule objects.

Public API:
    parse_strategy(user_input: str) -> dict
"""

import json
import os
import re

from dotenv import load_dotenv


PARSE_PROMPT = """You are a trading rule parser. Convert the user's natural language trading strategy into structured JSON rules.

Available indicators: RSI, MACD, MACD_HIST, ADX, EMA_10, EMA_20, EMA_50, EMA_200, PRICE, VOLUME_RATIO, STOCH_RSI, BB_UPPER, BB_LOWER

Available operators: gt (greater than), lt (less than), gte (>=), lte (<=), crosses_above, crosses_below

Respond with ONLY valid JSON (no markdown, no explanation) in this format:
{
  "name": "short strategy name (3-5 words)",
  "description": "one line summary of the strategy",
  "rules": [
    {
      "indicator": "RSI",
      "operator": "lt",
      "value": 30,
      "value_text": null,
      "timeframe": "daily"
    }
  ],
  "suggested_symbols": ["RELIANCE", "TCS"]
}

Rules for parsing:
- "drops below" or "goes below" → operator: "lt"
- "rises above" or "goes above" → operator: "gt"
- "crosses above" → operator: "crosses_above"
- "crosses below" → operator: "crosses_below"
- For EMA crossovers like "price crosses above 50 EMA", use indicator: "PRICE" with value set to the EMA value, or indicator: "EMA_50" with appropriate operator
- Extract any stock symbols mentioned
- If the user mentions "volume above average", use indicator: "VOLUME_RATIO", operator: "gt", value: 1.5
- Default timeframe is "daily"

User's strategy: {user_input}
"""


async def parse_strategy(user_input: str) -> dict:
    """
    Parse natural language strategy into structured rules using Groq.

    Returns:
        {
            "name": str,
            "description": str,
            "rules": list[dict],
            "suggested_symbols": list[str],
        }
    """
    load_dotenv(override=True)

    # Try Groq first, then Gemini
    try:
        return await _parse_with_groq(user_input)
    except Exception as exc:
        print(f"[rule_parser] Groq failed: {exc}")

    try:
        return await _parse_with_gemini(user_input)
    except Exception as exc:
        print(f"[rule_parser] Gemini failed: {exc}")

    # Final fallback: simple keyword-based parsing
    return _parse_keyword_based(user_input)


async def _parse_with_groq(user_input: str) -> dict:
    """Parse using Groq LLM."""
    import asyncio
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")

    client = Groq(api_key=api_key)
    prompt = PARSE_PROMPT.format(user_input=user_input)

    def _call():
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return resp.choices[0].message.content

    raw = await asyncio.to_thread(_call)
    return _extract_json(raw)


async def _parse_with_gemini(user_input: str) -> dict:
    """Parse using Google Gemini."""
    import asyncio
    import google.generativeai as genai

    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    genai.configure(api_key=api_key)
    prompt = PARSE_PROMPT.format(user_input=user_input)

    def _call():
        model = genai.GenerativeModel("gemini-2.5-flash")
        return model.generate_content(prompt).text

    raw = await asyncio.to_thread(_call)
    return _extract_json(raw)


def _extract_json(raw: str) -> dict:
    """Extract JSON from LLM response (may have markdown fences)."""
    # Remove markdown code fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    data = json.loads(raw)

    # Validate structure
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    if "rules" not in data or not isinstance(data["rules"], list):
        raise ValueError("Missing 'rules' array")

    return {
        "name": data.get("name", "Unnamed Strategy"),
        "description": data.get("description", ""),
        "rules": data["rules"],
        "suggested_symbols": data.get("suggested_symbols", []),
    }


def _parse_keyword_based(user_input: str) -> dict:
    """Simple keyword-based fallback parser when no LLM is available."""
    rules = []
    text = user_input.lower()

    # RSI rules
    rsi_match = re.search(r"rsi\s*(?:drops?\s*)?(?:below|under|<)\s*(\d+)", text)
    if rsi_match:
        rules.append({"indicator": "RSI", "operator": "lt",
                       "value": float(rsi_match.group(1)), "value_text": None, "timeframe": "daily"})

    rsi_above = re.search(r"rsi\s*(?:goes?\s*)?(?:above|over|>)\s*(\d+)", text)
    if rsi_above:
        rules.append({"indicator": "RSI", "operator": "gt",
                       "value": float(rsi_above.group(1)), "value_text": None, "timeframe": "daily"})

    # MACD rules
    if "macd" in text and ("crosses above" in text or "cross above" in text):
        rules.append({"indicator": "MACD_HIST", "operator": "crosses_above",
                       "value": 0, "value_text": "signal_line", "timeframe": "daily"})
    elif "macd" in text and ("crosses below" in text or "cross below" in text):
        rules.append({"indicator": "MACD_HIST", "operator": "crosses_below",
                       "value": 0, "value_text": "signal_line", "timeframe": "daily"})

    # Volume rules
    if "volume" in text and ("above" in text or "high" in text):
        rules.append({"indicator": "VOLUME_RATIO", "operator": "gt",
                       "value": 1.5, "value_text": None, "timeframe": "daily"})

    # Price drop rules
    price_drop = re.search(r"(?:price|stock)\s*(?:drops?|falls?)\s*(\d+)\s*%", text)
    if price_drop:
        # This is approximate — store as a rule but note it's relative
        rules.append({"indicator": "PRICE", "operator": "lt",
                       "value": -float(price_drop.group(1)), "value_text": "percentage_drop",
                       "timeframe": "daily"})

    # EMA crossover
    ema_match = re.search(r"(?:crosses?\s+)?(?:above|over)\s+(\d+)[\s-]?(?:day\s+)?(?:ema|ma)", text)
    if ema_match:
        period = ema_match.group(1)
        rules.append({"indicator": f"EMA_{period}", "operator": "crosses_above",
                       "value": None, "value_text": f"ema_{period}", "timeframe": "daily"})

    # Extract symbols (uppercase words that look like tickers)
    symbols = re.findall(r'\b([A-Z]{2,15})\b', user_input)
    # Filter common words
    common = {"BUY", "SELL", "HOLD", "WHEN", "AND", "OR", "IF", "THE", "RSI", "MACD",
              "EMA", "ADX", "PRICE", "VOLUME", "ABOVE", "BELOW"}
    symbols = [s for s in symbols if s not in common]

    if not rules:
        rules.append({"indicator": "RSI", "operator": "lt",
                       "value": 30, "value_text": None, "timeframe": "daily"})

    return {
        "name": user_input[:40] if len(user_input) <= 40 else user_input[:37] + "…",
        "description": user_input[:100],
        "rules": rules,
        "suggested_symbols": symbols,
    }
