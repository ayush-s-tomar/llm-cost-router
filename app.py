import os
import time
import streamlit as st
from groq import Groq

st.set_page_config(page_title="LLM Cost Router", page_icon="dollar", layout="wide")

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


def select_model(query):
    q = query.lower().strip()
    if len(q) > LONG_QUERY_THRESHOLD:
        return COMPLEX_MODEL, "complex"
    if any(kw in q for kw in COMPLEXITY_KEYWORDS):
        return COMPLEX_MODEL, "complex"
    if any(q.startswith(p) for p in SIMPLE_PATTERNS):
        return SIMPLE_MODEL, "simple"
    return SIMPLE_MODEL, "simple"


def estimate_tokens(text):
    return max(1, len(text) // 4)


def calc_cost(model, input_tokens, output_tokens):
    rates = PRICING[model]
    return (input_tokens / 1_000_000) * rates["input"] + (output_tokens / 1_000_000) * rates["output"]


def baseline_cost(input_tokens, output_tokens):
    return calc_cost(COMPLEX_MODEL, input_tokens, output_tokens)


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


st.title("LLM Cost Router")
st.caption(
    "Routes each query to Llama 3.1 8B Instant or Llama 3.3 70B Versatile based on "
    "complexity, and tracks what you would have paid if every request went to the big model."
)

client = get_client()
if client is None:
    st.error("GROQ_API_KEY not set. Add it under Settings, Secrets on Streamlit Cloud, or in a local .env / environment variable.")

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

    badge = "[simple]" if complexity == "simple" else "[complex]"
    st.info(f"Routed to {model} {badge}")
    st.write(answer)

stats = get_stats()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Requests", stats["total_requests"])
col2.metric("Actual Spend", f"${stats['total_cost_actual']:.6f}")
col3.metric("If Always Big Model", f"${stats['total_cost_if_always_big_model']:.6f}")
col4.metric("Saved", f"${stats['total_saved']:.6f}")
col5.metric("% Saved", f"{stats['percent_saved']}%")

st.subheader("Recent Requests")
if not stats["recent_requests"]:
    st.caption("No requests yet, try the box above.")
else:
    rows = [
        {
            "Query": (e["query"][:60] + "...") if len(e["query"]) > 60 else e["query"],
            "Routed To": f"{e['model']} ({e['complexity']})",
            "Cost": f"${e['actual_cost']:.6f}",
            "Saved": f"${e['saved']:.6f}",
        }
        for e in stats["recent_requests"]
    ]
    st.table(rows)

if st.button("Reset stats"):
    st.session_state.log = []
    st.rerun()