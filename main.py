"""
main.py
-------
LLM Cost Router — routes chat queries to a cheap or expensive Groq model
based on query complexity, tracks actual spend vs a "what if we always used
the big model" baseline, and serves a live savings dashboard.

Run with:
    uvicorn main:app --reload
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

from router_logic import select_model
from pricing import estimate_tokens
from storage import record_request, get_stats, clear_log

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

app = FastAPI(title="LLM Cost Router")


class QueryRequest(BaseModel):
    query: str


@app.post("/route")
def route_query(req: QueryRequest):
    """Classify the query, send it to the appropriate Groq model, log cost."""
    if client is None:
        return {"error": "GROQ_API_KEY not set. Add it to your .env file."}

    model, complexity = select_model(req.query)

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": req.query}],
    )

    answer = response.choices[0].message.content

    # Prefer real usage numbers from the API response if available,
    # fall back to a rough character-based estimate otherwise.
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", None) or estimate_tokens(req.query)
    output_tokens = getattr(usage, "completion_tokens", None) or estimate_tokens(answer)

    entry = record_request(
        query=req.query,
        model=model,
        complexity=complexity,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return {
        "answer": answer,
        "model_used": model,
        "complexity": complexity,
        "cost": entry["actual_cost"],
        "cost_if_big_model": entry["baseline_cost"],
        "saved_on_this_request": entry["saved"],
    }


@app.get("/stats")
def stats():
    return get_stats()


@app.post("/reset")
def reset():
    clear_log()
    return {"status": "cleared"}


# Serve the dashboard at /
app.mount("/", StaticFiles(directory="static", html=True), name="static")
