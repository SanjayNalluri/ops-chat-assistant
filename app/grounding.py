"""Check that every number in a written answer comes from the query results.

An LLM summarising correct data can still misquote it (e.g. results say 2.25, the answer says 2.27).
A number in the answer counts as grounded if, at the precision it is written with, it equals:
  - a number in the query results, or
  - a number in the question itself (years, "top 5", "10 days"), or
  - the difference of two numbers in the results (e.g. "2.03 points lower").
Small counting words like "1" or "2" in "top 2" are covered by the question rule.
"""
from itertools import combinations

from app.factcheck import _numbers, normalise

MAX_PAIRS_FROM = 80          # limit the difference check to the first 80 result numbers


def ungrounded_numbers(answer: str, results_text: str, question: str = "") -> list[str]:
    source = [v for v, _ in _numbers(normalise(results_text))]
    asked = [v for v, _ in _numbers(normalise(question))]
    diffs = [abs(a - b) for a, b in combinations(source[:MAX_PAIRS_FROM], 2)]
    bad = []
    for n, d in _numbers(normalise(answer)):
        n = abs(n)

        def close(v):
            return abs(round(v, d) - n) < 10 ** -(d + 3) if d else abs(v - n) < 0.5 and round(v) == n

        if any(close(abs(v)) for v in source) or any(close(abs(v)) for v in asked) or any(close(v) for v in diffs):
            continue
        bad.append(f"{n:.{d}f}")
    return bad


def fix_prompt(bad: list[str]) -> str:
    return (f"These numbers in your answer do not appear in the query results: {', '.join(bad)}. "
            "Rewrite the answer using ONLY numbers exactly as they appear in the results "
            "(a difference of two result numbers is fine). Plain text, 1-3 sentences.")


def write_grounded(chat, messages, results_text: str, question: str, clean=lambda t: t, max_tokens: int = 400):
    """Ask `chat` for an answer; if it quotes numbers that are not in the results, ask once for a rewrite.
    Returns (answer, ungrounded numbers left in the final answer, number of rewrites)."""
    text = clean(chat(messages, max_tokens=max_tokens))
    bad = ungrounded_numbers(text, results_text, question)
    if not bad:
        return text, [], 0
    retry = messages + [{"role": "assistant", "content": text}, {"role": "user", "content": fix_prompt(bad)}]
    text2 = clean(chat(retry, max_tokens=max_tokens))
    bad2 = ungrounded_numbers(text2, results_text, question)
    return (text2, bad2, 1) if len(bad2) <= len(bad) else (text, bad, 1)
