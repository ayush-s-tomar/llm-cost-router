"""
router_logic.py
----------------
Decides which model a query should go to, based on a cheap heuristic
classifier. No LLM call needed to classify — this has to be near-free itself,
or the router adds more cost than it saves.
"""

import re
from pricing import CHEAP_MODEL, EXPENSIVE_MODEL

# Signals that suggest a query needs the bigger, more capable model.
COMPLEXITY_KEYWORDS = [
    "compare", "analyze", "analyse", "explain in detail", "why does",
    "why is", "architecture", "design a", "trade-off", "tradeoff",
    "pros and cons", "step by step", "step-by-step", "walk me through",
    "reasoning", "debug", "root cause", "optimize", "optimise",
    "multi-step", "strategy", "evaluate", "critique", "in depth",
    "comprehensive", "详细",  # harmless extra token, ignore
]

# Signals that suggest a query is simple and factual — safe for the cheap model.
SIMPLE_PATTERNS = [
    r"^what is\b", r"^who is\b", r"^when (is|was)\b", r"^where is\b",
    r"^define\b", r"^list\b", r"^give me\b.*\bexample\b",
]


def classify_complexity(query: str) -> str:
    """Return 'simple' or 'complex' for a given query string."""
    q = query.lower().strip()
    word_count = len(q.split())

    # Long queries are usually complex regardless of keywords.
    if word_count > 40:
        return "complex"

    for kw in COMPLEXITY_KEYWORDS:
        if kw in q:
            return "complex"

    for pattern in SIMPLE_PATTERNS:
        if re.match(pattern, q):
            return "simple"

    # Short query, no complexity signals, no explicit simple-pattern match:
    # default by length. Short = simple, medium = complex (safer default,
    # since sending something borderline to the small model risks a bad
    # answer, and the cost gap is worth erring toward quality here).
    return "simple" if word_count <= 12 else "complex"


def select_model(query: str) -> tuple[str, str]:
    """Return (model_name, complexity_label) for a query."""
    complexity = classify_complexity(query)
    model = CHEAP_MODEL if complexity == "simple" else EXPENSIVE_MODEL
    return model, complexity
