"""
app.py
------
LLM Cost Router — Streamlit version.
Routes each query to a cheap or expensive Groq model based on complexity,
tracks actual spend vs a "what if we always used the big model" baseline.

Run with:
    streamlit run app.py
"""

import os
import time

import streamlit as st
from groq import Groq

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="LLM Cost Router", page_icon="💸", layout="wide")

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", None)

SIMPLE_MODEL = "llama-3.1-8b-instant"
COMPLEX_MODEL = "llama-3.3-70b-versatile"

PRICING = {
    SIMPLE_MODEL: {"input": 0.05, "output": 0.08},
    COMPLEX_MODEL: {"input": 0.59, "output": 0.79},
}

COMPLEXITY_KEYWORDS = [
    "compare", "analyze", "design", "trade-off", "tradeoff",
    "step by step", "architecture", "evaluate", "pros and cons",
    "explain in depth", "walk through", "optimize",
]
SIMPLE_PATTERNS = ["what is", "who is", "define", "list"]
LONG_QUERY_THRESHOLD = 300


@st.cache_resource
def get_client():
    if not GROQ_API_KEY:
        return None
    return Groq(api_key=GROQ_API_KEY)


def select_model(query: str):
    q = query.lower().strip()
    if len(q) > LONG_QUERY_THRESHOLD:
        return COMPLEX_MODEL, "complex"
    if any(kw in q for kw in COMPLEXITY_KEYWORDS):
        return COMPLEX_MODEL, "complex"
    if any(q.startswith(p) for p in SIMPLE_PATTERNS):
        return SIMPLE_MODEL, "simple"
    return SIMPLE_MODEL, "simple"


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING[model]
    return (input_tokens / 1_000_000) * rates["input"] + (output_tokens / 1_000_000) * rates["output"]


def baseline_cost(input_tokens: int, output_tokens: int) -> float:
    return calc_cost(COMPLEX_MODEL, input_tokens, output_tokens)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "log" not in st.session_state:
    st.session_state.log = []


def record_request(query, model, complexity, input_tokens, output_tokens, answer):
    actual = calc_cost(model, input_tokens, output_tokens)
    base = baseline_cost(input_tokens, output_tokens)
    entry = {
        "query": query,
        "model": model,
        "complexity": complexity,
        "answer": answer,
        "actual_cost": actual,
        "baseline_cost": base,
        "saved": base - actual,
        "ts": time.time(),
    }
    st.session_state.log.insert(0, entry)
    return entry


def get_stats():
    log = st.session_state.log
    total_actual = sum(e["actual_cost"] for e in log)
    total_baseline = sum(e["baseline_cost"] for e in log)
    total_saved = total_baseline - total_actual
    pct_saved = (total_saved / total_baseline * 100) if total_baseline > 0 else 0.0
    return {
        "total_requests": len(log),
        "total_cost_actual": total_actual,
        "total_cost_if_always_big_model": total_baseline,
        "total_saved": total_saved,
        "percent_saved": round(pct_saved, 1),
        "recent_requests": log[:10],
    }


# ---------------------------------------------------------------------------
# Styling — color-coded badges
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .badge-simple {
        display: inline-block;
        background: rgba(107,207,143,0.15);
        color: #6bcf8f;
        font-size: 13px;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 999px;
        border: 1px solid rgba(107,207,143,0.4);
    }
    .badge-complex {
        display: inline-block;
        background: rgba(240,168,104,0.15);
        color: #f0a868;
        font-size: 13px;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 999px;
        border: 1px solid rgba(240,168,104,0.4);
    }
    .hero-stat {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
    }
    .hero-number {
        font-size: 56px;
        font-weight: 700;
        color: #f0a868;
        line-height: 1;
    }
    .hero-label {
        font-size: 14px;
        color: #9a9aa2;
        letter-spacing: 0.04em;
        margin-top: 4px;
    }
    .table-scroll {
        max-height: 260px;
        overflow-y: auto;
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Hero stat — above the fold
# ---------------------------------------------------------------------------
stats = get_stats()

st.markdown(
    f"""
    <div class="hero-stat">
        <div class="hero-number">{stats['percent_saved']}% CHEAPER</div>
        <div class="hero-label">SAME ANSWER · SMARTER MODEL ROUTING</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.title("LLM Cost Router")
st.caption(
    "Routes each query to Llama 3.1 8B Instant or Llama 3.3 70B Versatile based on "
    "complexity, and tracks what you would have paid if every request went to the big model."
)

client = get_client()
if client is None:
    st.error("GROQ_API_KEY not set. Add it under Settings → Secrets on Streamlit Cloud, "
              "or in a local .env / environment variable.")

with st.form("query_form", clear_on_submit=True):
    query = st.text_input(
        "Ask something",
        placeholder="e.g. 'What is FastAPI?' or 'Compare LangGraph and CrewAI in depth'",
    )
    submitted = st.form_submit_button("Route", disabled=(client is None))

if submitted and query.strip():
    model, complexity = select_model(query)
    with st.spinner(f"Routing to {model}..."):
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": query}],
        )
        answer = response.choices[0].message.content

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None) or estimate_tokens(query)
        output_tokens = getattr(usage, "completion_tokens", None) or estimate_tokens(answer)

        entry = record_request(query, model, complexity, input_tokens, output_tokens, answer)

    badge_class = "badge-simple" if complexity == "simple" else "badge-complex"
    st.markdown(
        f'<span class="{badge_class}">Routed to {model} · {complexity}</span>',
        unsafe_allow_html=True,
    )
    st.write("")
    st.write(answer)
    stats = get_stats()  # refresh after new entry

# ---------------------------------------------------------------------------
# Headline stats — 3 columns
# ---------------------------------------------------------------------------
st.write("")
col1, col2, col3 = st.columns(3)
col1.metric("Total Requests", stats["total_requests"])
col2.metric("Saved", f"${stats['total_saved']:.6f}")
col3.metric("% Saved", f"{stats['percent_saved']}%")

with st.expander("Show cost breakdown"):
    c1, c2 = st.columns(2)
    c1.metric("Actual Spend", f"${stats['total_cost_actual']:.6f}")
    c2.metric("If Always Big Model", f"${stats['total_cost_if_always_big_model']:.6f}")

# ---------------------------------------------------------------------------
# Recent requests — capped height, scrollable
# ---------------------------------------------------------------------------
st.subheader("Recent Requests")
if not stats["recent_requests"]:
    st.caption("No requests yet — try the box above.")
else:
    rows_html = ""
    for e in stats["recent_requests"]:
        short_query = (e["query"][:60] + "...") if len(e["query"]) > 60 else e["query"]
        badge_class = "badge-simple" if e["complexity"] == "simple" else "badge-complex"
        rows_html += f"""
        <tr>
            <td style="padding:8px 10px; border-bottom:1px solid rgba(255,255,255,0.08);">{short_query}</td>
            <td style="padding:8px 10px; border-bottom:1px solid rgba(255,255,255,0.08);">
                <span class="{badge_class}">{e['model']}</span>
            </td>
            <td style="padding:8px 10px; border-bottom:1px solid rgba(255,255,255,0.08);">${e['actual_cost']:.6f}</td>
            <td style="padding:8px 10px; border-bottom:1px solid rgba(255,255,255,0.08);">${e['saved']:.6f}</td>
        </tr>
        """

    table_html = f"""
    <div class="table-scroll">
        <table style="width:100%; border-collapse:collapse; font-size:13px;">
            <thead>
                <tr style="text-align:left; color:#9a9aa2;">
                    <th style="padding:8px 10px;">Query</th>
                    <th style="padding:8px 10px;">Routed To</th>
                    <th style="padding:8px 10px;">Cost</th>
                    <th style="padding:8px 10px;">Saved</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)

if st.button("Reset stats"):
    st.session_state.log = []
    st.rerun()