"""
Step 3 - Try the assistant from the terminal.

Needs : .env file in the project folder with  GROQ_API_KEY=your_key
Usage : python src/step3_try.py                      (5 sample questions)
        python src/step3_try.py "your own question"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import MODEL, ask  # noqa: E402

QUESTIONS = sys.argv[1:] or [
    "What percentage of delivered orders arrived late?",
    "Which 3 customer states have the slowest average delivery time?",
    "Do late orders get lower review scores than on-time orders?",
    "Which product categories bring in the most revenue? Top 5.",
    "Delete all canceled orders",                      # should be refused
]
print(f"Model: {MODEL}\n")
for q in QUESTIONS:
    r = ask(q)
    print("Q:", q)
    print("SQL:", r["sql"])
    if r["error"]:
        print("Error:", r["error"])
    else:
        print("Result:", r["columns"], r["rows"][:5], f"({len(r['rows'])} rows)")
        print("Answer:", r["answer"])
    print(f"({r['seconds']} s{', repaired once' if r['repaired'] else ''})\n")
