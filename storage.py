"""
storage.py
----------
Simple in-memory request log. Fine for a demo/portfolio project — swap for
SQLite or Postgres if you ever need this to survive a restart or scale past
one process.
"""

from threading import Lock
from pricing import estimate_cost, BASELINE_MODEL

_lock = Lock()
_log: list[dict] = []


def record_request(query: str, model: str, complexity: str, input_tokens: int, output_tokens: int) -> dict:
    actual_cost = estimate_cost(model, input_tokens, output_tokens)
    baseline_cost = estimate_cost(BASELINE_MODEL, input_tokens, output_tokens)

    entry = {
        "query": query,
        "model": model,
        "complexity": complexity,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "actual_cost": actual_cost,
        "baseline_cost": baseline_cost,
        "saved": round(baseline_cost - actual_cost, 8),
    }
    with _lock:
        _log.append(entry)
    return entry


def get_stats() -> dict:
    with _lock:
        entries = list(_log)

    total_requests = len(entries)
    total_actual = round(sum(e["actual_cost"] for e in entries), 6)
    total_baseline = round(sum(e["baseline_cost"] for e in entries), 6)
    total_saved = round(total_baseline - total_actual, 6)
    simple_count = sum(1 for e in entries if e["complexity"] == "simple")
    complex_count = total_requests - simple_count
    pct_saved = round((total_saved / total_baseline) * 100, 1) if total_baseline > 0 else 0.0

    return {
        "total_requests": total_requests,
        "simple_requests": simple_count,
        "complex_requests": complex_count,
        "total_cost_actual": total_actual,
        "total_cost_if_always_big_model": total_baseline,
        "total_saved": total_saved,
        "percent_saved": pct_saved,
        "recent_requests": entries[-10:][::-1],  # last 10, newest first
    }


def clear_log():
    with _lock:
        _log.clear()
