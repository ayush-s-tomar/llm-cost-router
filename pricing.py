"""
pricing.py
----------
Groq per-token pricing (USD per 1M tokens), confirmed against groq.com/pricing
as of July 2026. Update these constants if Groq changes its pricing.
"""

# (input $ per 1M tokens, output $ per 1M tokens)
PRICING = {
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
}

BASELINE_MODEL = "llama-3.3-70b-versatile"  # what you'd pay if you always used the big model
CHEAP_MODEL = "llama-3.1-8b-instant"
EXPENSIVE_MODEL = "llama-3.3-70b-versatile"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return cost in USD for a single request given token counts."""
    rates = PRICING[model]
    cost = (input_tokens / 1_000_000) * rates["input"] + (output_tokens / 1_000_000) * rates["output"]
    return round(cost, 8)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token (standard approximation
    for English text, good enough for cost tracking without calling a
    tokenizer library)."""
    return max(1, len(text) // 4)
