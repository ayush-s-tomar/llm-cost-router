# LLM Cost Router

A FastAPI service that routes each query to a cheap or expensive Groq model
based on complexity, then shows a live dashboard of what you actually spent
vs what you'd have spent if every request went to the big model.

## Live Demo

![LLM Cost Router dashboard showing live savings](assets/demo.png)

A simple query ("What is FastAPI?") routes to Llama 3.1 8B Instant and costs
$0.000047. A complex query ("Compare LangGraph and CrewAI in depth...")
correctly routes to Llama 3.3 70B Versatile instead — the router isn't just
always picking the cheap model, it's making a real complexity-based call.

## Why this exists

Most agent projects call one model for everything, regardless of whether the
query is "what is X" or "design a distributed system architecture." That's
money left on the table. This router classifies each query with a
near-free heuristic (no LLM call needed just to decide which LLM to call),
sends simple queries to **Llama 3.1 8B Instant** ($0.05/$0.08 per 1M
input/output tokens) and complex ones to **Llama 3.3 70B Versatile**
($0.59/$0.79 per 1M tokens) — an ~11x price gap — and tracks the savings.

## How routing works

The classifier (`router_logic.py`) checks for:
- Query length (very long queries default to the big model)
- Complexity keywords ("compare", "analyze", "design", "trade-off", "step by
  step", etc.)
- Simple-query patterns ("what is", "who is", "define", "list")

No ML model, no extra API call — routing decisions have to be free or they
defeat the purpose.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your Groq API key:

```bash
cp .env.example .env
```

Get a free key at [console.groq.com](https://console.groq.com) if you don't
have one.

## Run it

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000** — you'll see the live dashboard. Type a query
in the box:
- Try `What is FastAPI?` — routes to the cheap model
- Try `Compare LangGraph and CrewAI in depth, covering architecture trade-offs`
  — routes to the expensive model

Watch the "Saved" and "% Saved" numbers update as you send more queries.

## API

- `POST /route` — `{"query": "..."}` → routes, calls Groq, returns the
  answer plus cost breakdown
- `GET /stats` — running totals: requests, actual spend, baseline spend,
  amount saved, last 10 requests
- `POST /reset` — clears the in-memory log

## Architecture

```
llm-cost-router/
├── main.py           FastAPI app, /route and /stats endpoints
├── router_logic.py    complexity classifier + model selection
├── pricing.py          Groq pricing constants + cost math
├── storage.py           in-memory request log + stats aggregation
├── static/index.html    live dashboard (vanilla JS, no build step)
└── assets/demo.png       screenshot used in this README
```

Storage is in-memory (a Python list behind a lock) — good enough for a demo
or single-process deployment. Swap `storage.py` for SQLite/Postgres if you
need it to survive restarts.

## Notes

- Pricing constants in `pricing.py` are from groq.com/pricing as of July
  2026 — update them if Groq changes rates.
- Token counts use the real `usage` field from Groq's API response when
  available, falling back to a rough character-count estimate.

## Author

Ayush Tomar — [GitHub](https://github.com/ayush-s-tomar)
