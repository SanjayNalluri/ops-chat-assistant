"""
Ops Chat API: ask a question in plain English, get SQL, the result table and a short answer.
Run locally : uvicorn api.main:app --reload      (from the project folder)
Docs        : http://127.0.0.1:8000/docs
"""
import json
import sys
from pathlib import Path

import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import engine  # noqa: E402

app = FastAPI(title="Ops Chat API",
              description="Ask questions about 96,018 delivered marketplace orders (Olist, 2017-2018). "
                          "An LLM writes SQLite; every query is checked to be a single read-only SELECT "
                          "and runs on a read-only database with a time limit.",
              version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

EXAMPLES = [
    "What percentage of delivered orders arrived late?",
    "Late rate by month in 2018",
    "Which 5 customer states have the highest late rate?",
    "Do late orders get lower review scores than on-time orders?",
    "Which 5 product categories bring in the most revenue?",
    "Among sellers with at least 100 orders, which 5 are late most often?",
    "How does the late rate compare for same-state and cross-state orders?",
    "Average delivery time by customer state, slowest first",
]


# Simple per-visitor limit so the free LLM quota is not used up by one person
LIMIT, WINDOW = 20, 600                       # 20 questions per 10 minutes
_recent = defaultdict(deque)


def _allow(ip: str) -> bool:
    now, q = time.time(), _recent[ip]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        return False
    q.append(now)
    return True


class Question(BaseModel):
    question: str = Field(..., min_length=3, max_length=300, examples=["Which 5 states have the highest late rate?"])


class Answer(BaseModel):
    question: str
    answer: str | None
    sql: str | None
    columns: list[str]
    rows: list[list]
    error: str | None
    refused: bool
    repaired: bool
    seconds: float


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/docs")


@app.get("/health")
def health():
    return {"status": "ok", "model": engine.MODEL, "database": engine.DB.name}


@app.get("/examples")
def examples():
    return EXAMPLES


@app.get("/schema", summary="The table notes the model is given")
def schema():
    return {"schema": engine.SCHEMA}


@app.get("/evaluation", summary="Accuracy on the 40 test questions and the attack test")
def evaluation():
    f = ROOT / "eval" / "evaluation.json"
    if not f.exists():
        raise HTTPException(404, "No evaluation report yet (run src/step5_eval_report.py)")
    return json.loads(f.read_text(encoding="utf-8"))


@app.post("/ask", response_model=Answer)
def ask(q: Question, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    if not _allow(ip):
        raise HTTPException(429, "Too many questions in a short time. Please wait a few minutes.")
    try:
        out = engine.ask(q.question.strip())
    except engine.LLMError as e:
        raise HTTPException(503, f"The language model is not available right now: {e}") from None
    out["rows"] = [list(r) for r in out["rows"]]
    return out
