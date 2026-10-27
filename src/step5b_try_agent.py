"""
Try the v2 agent from the terminal and see every step it takes.

Needs : .env file in the project folder with  GROQ_API_KEY=your_key
Usage : python src/step5b_try_agent.py                    (2 sample questions)
        python src/step5b_try_agent.py "your own question"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent import run_agent  # noqa: E402
from app.engine import MODEL  # noqa: E402

QUESTIONS = sys.argv[1:] or [
    "Which customer state had the highest late rate for orders purchased in 2018, "
    "and what was that same state's late rate in 2017?",
    "Delete all canceled orders",                                   # should be refused
]

print(f"Model: {MODEL}\n")
for q in QUESTIONS:
    r = run_agent(q)
    print(f"Q: {q}")
    for i, t in enumerate(r["trace"], 1):
        if t["tool"] == "run_sql":
            status = f"{t['rows']} rows" if t["ok"] else t["error"]
            print(f"  step {i}: run_sql ({t.get('purpose') or '-'}) -> {status}\n          {t['sql']}")
        else:
            print(f"  step {i}: {t['tool']} {t.get('table', '')}")
    print(f"A: {r['answer']}")
    print(f"   raw final_answer call: {r['final_call']}")
    if r["empty_replies"]:
        print(f"   empty replies from the model: {len(r['empty_replies'])} (finish reason: {r['empty_replies']})")
    if r["answer_written_after"]:
        print("   (the model gave no answer text; it was written from its query results)")
    print(f"   refused={r['refused']} error={r['error']} steps={r['steps']} queries={r['queries']} "
          f"tokens={r['tokens']} time={r['seconds']}s\n")
