"""Engine tests with a fake LLM, so they run without an API key."""
import sqlite3

import pytest

import app.engine as engine


def fake_llm(replies):
    it = iter(replies)
    return lambda messages, max_tokens=1200: next(it)


def test_database_is_read_only():
    with pytest.raises(sqlite3.OperationalError):
        engine.run_sql("DELETE FROM orders")


def test_slow_query_is_stopped(monkeypatch):
    monkeypatch.setattr(engine, "QUERY_SECONDS", 0.5)
    with pytest.raises(sqlite3.OperationalError):
        engine.run_sql("SELECT COUNT(*) FROM order_items a, order_items b")


def test_extract_sql_from_code_block():
    assert engine.extract_sql("Here:\n```sql\nSELECT 1;\n```") == "SELECT 1"


def test_answer_flow(monkeypatch):
    monkeypatch.setattr(engine, "_chat", fake_llm(["```sql\nSELECT COUNT(*) AS n FROM delivered_orders\n```",
                                                   "There were 96,018 delivered orders."]))
    r = engine.ask("How many delivered orders?")
    assert r["error"] is None and r["rows"] == [(96018,)] and r["answer"]


def test_typo_is_repaired_once(monkeypatch):
    monkeypatch.setattr(engine, "_chat", fake_llm(["```sql\nSELECT COUNT(*) FROM delivered_ordrs\n```",
                                                   "```sql\nSELECT COUNT(*) FROM delivered_orders\n```", "ok"]))
    r = engine.ask("How many delivered orders?")
    assert r["repaired"] and r["error"] is None


def test_dangerous_sql_is_refused_not_repaired(monkeypatch):
    monkeypatch.setattr(engine, "_chat", fake_llm(["```sql\nDROP TABLE orders\n```"]))
    r = engine.ask("drop the orders table")
    assert r["error"].startswith("Blocked") and not r["repaired"] and r["rows"] == []


def test_answer_has_no_markdown_bold(monkeypatch):
    monkeypatch.setattr(engine, "_chat", fake_llm(["```sql\nSELECT 1 AS n FROM orders LIMIT 1\n```",
                                                   "There are **96018** delivered orders."]))
    assert engine.ask("How many?")["answer"] == "There are 96018 delivered orders."


def test_runaway_recursive_query_is_stopped(monkeypatch):
    monkeypatch.setattr(engine, "QUERY_SECONDS", 0.5)
    sql = engine.check_sql("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT MAX(x) FROM c")
    with pytest.raises(sqlite3.OperationalError):
        engine.run_sql(sql)
