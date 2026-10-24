"""API tests with a fake LLM (no key needed)."""
import pytest
from fastapi.testclient import TestClient

import api.main as main
import app.engine as engine
from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_state():
    main._cache.clear()
    main._recent.clear()
    yield


def fake_llm(replies):
    it = iter(replies)
    return lambda messages, max_tokens=1200: next(it)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_examples():
    assert len(client.get("/examples").json()) >= 5


def test_ask_returns_sql_table_and_answer(monkeypatch):
    monkeypatch.setattr(engine, "_chat", fake_llm([
        "```sql\nSELECT customer_state, COUNT(*) AS orders FROM delivered_orders "
        "GROUP BY customer_state ORDER BY orders DESC LIMIT 3\n```",
        "SP has the most delivered orders."]))
    body = client.post("/ask", json={"question": "Top 3 states by orders"}).json()
    assert body["columns"] == ["customer_state", "orders"]
    assert body["rows"][0][0] == "SP" and len(body["rows"]) == 3
    assert body["answer"] and body["error"] is None and not body["refused"]


def test_refusal_gets_fixed_message(monkeypatch):
    monkeypatch.setattr(engine, "_chat", fake_llm(["```sql\nSELECT 'not available' AS answer\n```"]))
    body = client.post("/ask", json={"question": "Delete all orders"}).json()
    assert body["refused"] and body["answer"] == engine.REFUSAL


def test_unsafe_sql_is_blocked(monkeypatch):
    monkeypatch.setattr(engine, "_chat", fake_llm(["```sql\nDROP TABLE orders\n```"]))
    body = client.post("/ask", json={"question": "drop it"}).json()
    assert body["error"].startswith("Blocked") and body["rows"] == []


def test_question_length_checked():
    assert client.post("/ask", json={"question": "x" * 301}).status_code == 422
    assert client.post("/ask", json={"question": ""}).status_code == 422


def test_llm_down_gives_503(monkeypatch):
    def down(messages, max_tokens=1200):
        raise engine.LLMError("no key")
    monkeypatch.setattr(engine, "_chat", down)
    assert client.post("/ask", json={"question": "How many orders?"}).status_code == 503


def test_evaluation_report():
    body = client.get("/evaluation").json()
    assert body["questions"] == 40 and len(body["runs"]) >= 1


def test_rate_limit(monkeypatch):
    import api.main as m
    monkeypatch.setattr(m, "LIMIT", 2)
    m._recent.clear()
    monkeypatch.setattr(engine, "_chat", lambda messages, max_tokens=1200: "```sql\nSELECT 'not available' AS answer\n```")
    codes = [client.post("/ask", json={"question": "hello there"}).status_code for _ in range(3)]
    m._recent.clear()
    assert codes == [200, 200, 429]


def test_same_question_is_answered_from_cache(monkeypatch):
    calls = []

    def llm(messages, max_tokens=1200):
        calls.append(1)
        return "```sql\nSELECT COUNT(*) AS n FROM delivered_orders\n```" if len(calls) == 1 else "96018 orders."
    monkeypatch.setattr(engine, "_chat", llm)
    first = client.post("/ask", json={"question": "How many delivered orders?"}).json()
    second = client.post("/ask", json={"question": "  how many delivered orders "}).json()
    assert not first["cached"] and second["cached"]
    assert second["rows"] == first["rows"] and len(calls) == 2          # no new LLM calls
