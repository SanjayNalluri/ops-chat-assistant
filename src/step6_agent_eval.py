"""
Step 6 - Evaluate the v2 agent against v1, one question set at a time (resumable).

Sets:
  multistep  eval/multistep_questions.csv (20 new questions that need 2+ queries).
             Both v1 and the agent answer each one; the written answer is graded on the key facts
             it must contain (app/factcheck.py). Gold facts were computed from the database by hand-written SQL.
  holdout    eval/holdout_questions.csv (the same 60 held-out questions as v1, never used for tuning).
             The agent's final_sql result is graded against the gold result exactly like v1.
  attacks    eval/attack_prompts_extended.csv (the same 25 attack prompts as v1).

Usage:  python src/step6_agent_eval.py multistep
        python src/step6_agent_eval.py attacks
        python src/step6_agent_eval.py holdout
Re-run the same command to continue: questions already in eval/agent_<set>.csv are skipped.
Add --redo to start a set again (the old file is kept as agent_<set>_previous.csv).

Groq free tier for openai/gpt-oss-120b: 8,000 tokens per minute and 200,000 per day. One agent question
uses ~5-8k tokens, so this script paces itself to stay under ~7,000 tokens a minute and stops cleanly
when the daily limit is hit (just run it again the next day).
"""
import collections
import os
import sys
import time
from pathlib import Path

import pandas as pd

os.environ.setdefault("GROQ_RETRIES", "6")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import engine  # noqa: E402
from app.agent import run_agent  # noqa: E402
from app.evaluate import results_match  # noqa: E402
from app.factcheck import check_facts  # noqa: E402

EVAL = ROOT / "eval"
SET = sys.argv[1] if len(sys.argv) > 1 else "multistep"
FILES = {"multistep": "multistep_questions.csv", "holdout": "holdout_questions.csv",
         "attacks": "attack_prompts_extended.csv"}
if SET not in FILES:
    sys.exit(f"set must be one of {list(FILES)}")
OUT = EVAL / f"agent_{SET}.csv"
TOKENS_PER_MIN = 7000

window = collections.deque()                          # (time, tokens) of recent calls


def pace(tokens: int):
    """Sleep so that the last 60 s stay under TOKENS_PER_MIN."""
    now = time.monotonic()
    window.append((now, tokens))
    while window and now - window[0][0] > 60:
        window.popleft()
    used = sum(t for _, t in window)
    if used > TOKENS_PER_MIN and window:
        time.sleep(max(1.0, 61 - (now - window[0][0])))


def daily_limit(e: Exception) -> bool:
    text = str(e).lower()
    return "429" in text and ("per day" in text or "tpd" in text or "rpd" in text)


questions = pd.read_csv(EVAL / FILES[SET])
if "--redo" in sys.argv and OUT.exists():                 # start this set again from scratch
    OUT.rename(OUT.with_name(OUT.stem + "_previous.csv"))
done = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame()
done_ids = set(done["id"].astype(str)) if len(done) else set()
todo = [r for r in questions.itertuples() if str(r.id) not in done_ids]
print(f"Set {SET}: {len(done_ids)} done, {len(todo)} to go. Model {engine.MODEL}")

new = []
try:
    for r in todo:
        row = {"id": r.id}
        if SET == "attacks":
            out = run_agent(r.prompt)
            ran = [t for t in out["trace"] if t.get("tool") == "run_sql" and t["ok"]]
            blocked = [t for t in out["trace"] if t.get("tool") == "run_sql" and (t["error"] or "").startswith("blocked")]
            outcome = ("refused" if out["refused"] and not ran else
                       "blocked by safety check" if blocked and not ran else
                       "harmless read-only query ran" if ran else "no query ran")
            row.update(prompt=r.prompt, outcome=outcome, answer=out["answer"],
                       queries_run=" | ".join(t["sql"] for t in ran))
        else:
            out = run_agent(r.question)
            row.update(question=r.question)
            if SET == "holdout":
                gold = engine.run_sql(r.gold_sql)[1]
                ok = out["error"] is None and bool(out["sql"]) and results_match(gold, out["rows"])
                ok_l = out["error"] is None and bool(out["sql"]) and results_match(gold, out["rows"], relabel=True)
                row.update(difficulty=r.difficulty, correct=ok, correct_lenient=ok_l, gold_sql=r.gold_sql)
            else:
                ok, missing = check_facts(r.facts, out["answer"] or "")
                v1 = engine.ask(r.question, with_summary=True)
                v1_ok, v1_missing = check_facts(r.facts, v1["answer"] or "")
                pace(3000)                                     # v1 uses ~2-3k tokens
                row.update(facts=r.facts, correct=ok, missing=" ; ".join(missing),
                           v1_correct=v1_ok, v1_missing=" ; ".join(v1_missing), v1_answer=v1["answer"],
                           v1_rewrites=v1.get("rewrites", 0), v1_ungrounded=" ".join(v1.get("ungrounded", [])))
        row.update(steps=out["steps"], queries=out["queries"], tokens=out["tokens"], seconds=out["seconds"],
                   finished_by="stopped by safety check (one strike)" if out.get("stopped_on_block") else
                               "answer writer (fallback)" if out.get("answer_written_after") else
                               ("final_answer" if out.get("final_call") else "plain text or none"),
                   empty_replies=len(out.get("empty_replies", [])),
                   rewrites=out.get("rewrites", 0), ungrounded=" ".join(out.get("ungrounded", [])),
                   error=out["error"], agent_sql=out["sql"], agent_answer=out["answer"])
        new.append(row)
        pd.concat([done, pd.DataFrame(new)], ignore_index=True).to_csv(OUT, index=False)   # save after every question
        mark = "" if SET == "attacks" else ("OK " if row["correct"] else "X  ")
        extra = row.get("outcome", "") + (f" | v1 {'OK' if row.get('v1_correct') else 'X'}" if SET == "multistep" else "")
        print(f"{str(r.id):>4} {mark}{extra:30s} steps {out['steps']} queries {out['queries']} "
              f"tokens {out['tokens']:>6} {out['seconds']:>5}s")
        pace(out["tokens"])
except engine.LLMError as e:
    if daily_limit(e):
        print("\nGroq daily token limit reached. Results so far are saved; run the same command tomorrow.")
    else:
        print(f"\nStopped on an API error: {e}\nResults so far are saved; run the same command again.")
except KeyboardInterrupt:
    print("\nStopped by you. Results so far are saved.")
except Exception as e:                                       # noqa: BLE001  (anything else: keep what we have)
    print(f"\nStopped on an unexpected error: {e}\nResults so far are saved; run the same command again.")

res = pd.concat([done, pd.DataFrame(new)], ignore_index=True) if new else done
if len(res):
    res.to_csv(OUT, index=False)
    print(f"\nSaved {len(res)}/{len(questions)} to {OUT.relative_to(ROOT)}")
    if len(res) == len(questions):
        if SET == "attacks":
            print(res.outcome.value_counts().to_string())
        else:
            print(f"Agent correct: {int(res.correct.sum())}/{len(res)}"
                  + (f" | v1 correct: {int(res.v1_correct.sum())}/{len(res)}" if SET == "multistep" else "")
                  + (f" | lenient: {int(res.correct_lenient.sum())}/{len(res)}" if SET == "holdout" else ""))
        if "finished_by" in res:
            print("How the agent finished:", res.finished_by.value_counts().to_dict())
        print(f"Median steps {res.steps.median():.0f}, queries {res.queries.median():.0f}, "
              f"tokens {res.tokens.median():.0f}, seconds {res.seconds.median():.1f} per question")
