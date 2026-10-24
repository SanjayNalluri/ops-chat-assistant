"""
Step 2 - Check the 40 test questions before using them to grade the assistant.

Inputs : eval/questions.csv          40 development questions (id, difficulty, question, gold_sql)
         eval/holdout_questions.csv  60 held-out questions, never used to tune the prompt
         data/deliverylens.db (step 1)
Output : eval/gold_results_<set>.csv (id, rows, first row) and a printed check
Usage  : python src/step2_check_questions.py                      (development set)
         python src/step2_check_questions.py eval/holdout_questions.csv

Every gold query must run, return rows, and (for "top N" questions) not have a tie at the
cut-off, otherwise a correct answer could be marked wrong.
"""
from pathlib import Path
import re
import sqlite3
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "deliverylens.db"
QFILE = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "eval/questions.csv")
Q = pd.read_csv(QFILE)

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
out, problems = [], []
for r in Q.itertuples():
    try:
        rows = con.execute(r.gold_sql).fetchall()
    except Exception as e:                                   # noqa: BLE001
        problems.append(f"Q{r.id}: SQL error {e}")
        continue
    if not rows:
        problems.append(f"Q{r.id}: no rows")
    m = re.search(r"ORDER BY\s+(\w+).*LIMIT\s+(\d+)\s*$", r.gold_sql, re.I | re.S)
    if m:                                                     # tie at the LIMIT cut-off?
        n = int(m.group(2))
        full = con.execute(re.sub(r"LIMIT\s+\d+\s*$", "", r.gold_sql, flags=re.I)).fetchall()
        if len(full) > n:
            col = [d[0] for d in con.execute(re.sub(r"LIMIT\s+\d+\s*$", "LIMIT 1", r.gold_sql, flags=re.I)).description]
            k = col.index(m.group(1)) if m.group(1) in col else -1
            if full[n - 1][k] == full[n][k]:
                problems.append(f"Q{r.id}: tie at the top-{n} cut-off")
    out.append({"id": r.id, "difficulty": r.difficulty, "rows": len(rows), "first_row": rows[0] if rows else None})

res = pd.DataFrame(out)
res.to_csv(ROOT / "eval" / f"gold_results_{QFILE.stem}.csv", index=False)
print(res.to_string(index=False))
print(f"\n{len(res)} of {len(Q)} questions ran: "
      + ", ".join(f"{k} {v}" for k, v in Q.difficulty.value_counts().items()))
print("Problems:" if problems else "No problems found.")
for p in problems:
    print("  ", p)
