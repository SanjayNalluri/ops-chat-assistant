"""
Step 7 - Re-grade saved multi-step answers with the current fact checker (no API calls, no tokens).

Use after changing app/factcheck.py: the saved answers in eval/agent_multistep*.csv are graded again.
Usage: python src/step7_regrade.py                      (eval/agent_multistep.csv)
       python src/step7_regrade.py eval/agent_multistep_previous.csv
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.factcheck import check_facts  # noqa: E402

f = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "eval/agent_multistep.csv")
d = pd.read_csv(f)
for who, col in [("agent", "agent_answer"), ("v1", "v1_answer")]:
    graded = [check_facts(facts, a if isinstance(a, str) else "") for facts, a in zip(d.facts, d[col])]
    ok = "correct" if who == "agent" else "v1_correct"
    miss = "missing" if who == "agent" else "v1_missing"
    changed = sum(bool(g[0]) != bool(o) for g, o in zip(graded, d[ok]))
    d[ok], d[miss] = [g[0] for g in graded], [" ; ".join(g[1]) for g in graded]
    print(f"{who:5s}: {int(d[ok].sum())}/{len(d)} correct  ({changed} changed by re-grading)")
d.to_csv(f, index=False)
wrong = d[~d.correct.astype(bool) | ~d.v1_correct.astype(bool)]
if len(wrong):
    print("\nNot fully correct (missing facts):")
    for r in wrong.itertuples():
        print(f"  {r.id}: agent [{r.missing or 'ok'}]  v1 [{r.v1_missing or 'ok'}]")
print(f"\nSaved {f.relative_to(ROOT)}")
