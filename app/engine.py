"""
Question -> SQL -> checked -> run -> short answer.

LLM: Groq (OpenAI-compatible API). Key and model come from environment variables:
  GROQ_API_KEY  (required)     GROQ_MODEL (default below)
"""
import os
import re
import sqlite3
import time
from pathlib import Path

import httpx

from app.env import load_env
from app.grounding import write_grounded
from app.guard import UnsafeSQL, check_sql

load_env()

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "deliverylens.db"
SCHEMA = (Path(__file__).parent / "schema.md").read_text(encoding="utf-8")
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
QUERY_SECONDS = 5
RETRIES = int(os.getenv("GROQ_RETRIES", "3"))   # the evaluation script raises this

# Worked examples for the prompt. They are NOT in the 40 test questions.
EXAMPLES = [
    ("How many delivered orders went to customers in Rio de Janeiro state (RJ)?",
     "SELECT COUNT(*) AS orders FROM delivered_orders WHERE customer_state = 'RJ'"),
    ("Late rate by number of items in the order, for orders with 1 to 5 items",
     "SELECT n_items, COUNT(*) AS orders, ROUND(100.0 * AVG(is_late), 2) AS late_rate_pct\n"
     "FROM delivered_orders WHERE n_items BETWEEN 1 AND 5 GROUP BY n_items ORDER BY n_items"),
    ("Top 3 product categories by number of orders in 2017",
     "SELECT ce.product_category_name_english AS category, COUNT(DISTINCT oi.order_id) AS orders\n"
     "FROM order_items oi JOIN orders o ON o.order_id = oi.order_id\n"
     "JOIN products p ON p.product_id = oi.product_id\n"
     "JOIN category_en ce ON ce.product_category_name = p.product_category_name\n"
     "WHERE strftime('%Y', o.order_purchase_timestamp) = '2017'\n"
     "GROUP BY category ORDER BY orders DESC LIMIT 3"),
]

SYSTEM = f"""You write SQLite queries for a delivery-operations database. Answer with ONE SQL query only,
inside a ```sql code block, and nothing else.

Rules:
- Read-only: a single SELECT (WITH ... SELECT is fine). Never modify data.
- Use only the tables and columns below. Prefer delivered_orders for delivery, lateness and review questions.
- Give readable column names with AS. Round rates and averages to 2 decimals.
- Rates and shares are percentages (100.0 * AVG(...)).
- For "top N" questions use ORDER BY ... LIMIT N.
- If the question cannot be answered from this data, return: SELECT 'not available' AS answer

{SCHEMA}"""


REFUSAL = ("I can only answer read-only questions about the DeliveryLens orders data "
           "(deliveries, lateness, sellers, products, payments, reviews).")


class LLMError(RuntimeError):
    def __init__(self, message, status=None, body=""):
        super().__init__(message)
        self.status, self.body = status, body or ""


def post_chat(body: dict) -> dict:
    """POST one chat-completions request to Groq, retrying on rate limits. Returns the JSON reply."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise LLMError("GROQ_API_KEY is not set")
    for attempt in range(RETRIES):                              # retry on rate limit / server error / network drop
        try:
            r = httpx.post(API_URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=60)
        except httpx.TransportError as e:                       # connection reset, timeout, DNS hiccup
            if attempt == RETRIES - 1:
                raise LLMError(f"network error talking to the LLM: {e}") from None
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 502, 503) and attempt < RETRIES - 1:
            time.sleep(min(60.0, float(r.headers.get("retry-after", 2 * (attempt + 1)))))
            continue
        if r.status_code != 200:
            raise LLMError(f"LLM request failed ({r.status_code}): {r.text[:200]}", r.status_code, r.text)
        return r.json()
    raise LLMError("LLM request failed after retries")


def _chat(messages, max_tokens=1200):
    body = {"model": MODEL, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
    if MODEL.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"
    return post_chat(body)["choices"][0]["message"]["content"] or ""


def strip_markdown(text: str) -> str:
    """Drop markdown bold if the model adds it."""
    return re.sub(r"\*\*|__", "", text or "").strip()


def extract_sql(text: str) -> str:
    """Take the SQL out of the model's reply (code block if present, else the whole reply)."""
    m = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip().rstrip(";").strip()


def run_sql(sql: str):
    """Run checked SQL on a read-only connection with a time limit. Returns (columns, rows)."""
    con = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True, check_same_thread=False)  # never written
    try:
        con.execute("PRAGMA query_only = ON")
        deadline = time.monotonic() + QUERY_SECONDS
        con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        cur = con.execute(sql)
        return [d[0] for d in cur.description], cur.fetchall()
    finally:
        con.close()


def generate_sql(question: str) -> str:
    messages = [{"role": "system", "content": SYSTEM}]
    for q, s in EXAMPLES:
        messages += [{"role": "user", "content": q}, {"role": "assistant", "content": f"```sql\n{s}\n```"}]
    messages.append({"role": "user", "content": question})
    return extract_sql(_chat(messages))


def fix_sql(question: str, sql: str, error: str) -> str:
    """One self-correction round: show the model its SQL and the error."""
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"```sql\n{sql}\n```"},
                {"role": "user", "content": f"That query failed: {error}\nReturn a corrected query."}]
    return extract_sql(_chat(messages))


def summarise(question: str, columns, rows, details: dict | None = None) -> str:
    """1-2 sentence plain answer, written only from the returned rows. Numbers are checked against the rows
    (app/grounding.py) and the answer is rewritten once if it misquotes them. `details` gets the check result."""
    preview = "\n".join(str(r) for r in rows[:20])
    data = f"Columns: {columns}\nRows ({len(rows)}):\n{preview}"
    messages = [{"role": "system", "content": "Answer the manager's question in 1-2 short sentences using ONLY the "
                 "query result given. Quote the key numbers exactly as they appear in the result. Do not guess "
                 "beyond the result. Brazilian real = BRL. Plain text only: no markdown, no bold, no bullet points."},
                {"role": "user", "content": f"Question: {question}\n{data}"}]
    text, bad, rewrites = write_grounded(_chat, messages, data, question, clean=strip_markdown)
    if details is not None:
        details.update(ungrounded=bad, rewrites=rewrites)
    return text


def ask(question: str, with_summary: bool = True) -> dict:
    """Full pipeline. Never raises for bad SQL: returns an 'error' field instead."""
    t0 = time.monotonic()
    out = {"question": question, "sql": None, "columns": [], "rows": [], "answer": None,
           "error": None, "repaired": False, "ungrounded": [], "rewrites": 0}
    sql = generate_sql(question)
    for attempt in range(2):
        out["sql"] = sql
        try:
            safe = check_sql(sql)
            out["columns"], out["rows"] = run_sql(safe)
            out["error"] = None
            break
        except UnsafeSQL as e:
            out["error"] = f"Blocked by safety check: {e}"
            if not e.repairable or attempt == 1:                 # never "repair" a dangerous query
                break
            sql = fix_sql(question, sql, str(e))
            out["repaired"] = True
        except sqlite3.Error as e:
            out["error"] = f"SQL error: {e}"
            if attempt == 0:
                sql = fix_sql(question, sql, str(e))
                out["repaired"] = True
    refused = out["rows"] == [("not available",)]
    if refused:
        out["answer"] = REFUSAL
    elif out["error"] is None and with_summary:
        if not out["rows"]:
            out["answer"] = "The query ran but found no matching rows."
        else:
            try:
                out["answer"] = summarise(question, out["columns"], out["rows"], details=out)
            except LLMError:
                out["answer"] = None                              # table is still shown
    out["refused"] = refused
    out["seconds"] = round(time.monotonic() - t0, 2)
    return out
