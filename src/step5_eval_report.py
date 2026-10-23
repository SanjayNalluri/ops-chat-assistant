"""
Step 5 - Turn the evaluation runs into one small file the API and web app can show.

Inputs : eval/results_v1.csv, eval/results_v2.csv (step 4 runs), eval/attack_results_v2.csv,
         eval/questions.csv, data/deliverylens.db
Output : eval/evaluation.json

Both runs are re-graded here with the same grader (strict and lenient), by re-running the SQL
the model wrote, so the two runs are scored in exactly the same way.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.engine import MODEL, run_sql  # noqa: E402
from app.evaluate import results_match  # noqa: E402
from app.guard import check_sql  # noqa: E402

EVAL = ROOT / "eval"
RUNS = {"v1": "first run, schema notes only",
        "v2": "after adding 3 schema notes (customer join, 'month' = purchase month, de-duplicated items)"}


def grade(row):
    gold = run_sql(row.gold_sql)[1]
    if not isinstance(row.model_sql, str) or not row.model_sql.strip():
        return False, False
    try:
        pred = run_sql(check_sql(row.model_sql))[1]
    except Exception:                                          # noqa: BLE001
        return False, False
    return results_match(gold, pred), results_match(gold, pred, relabel=True)


report = {"model": MODEL, "questions": 40, "runs": []}
for run, note in RUNS.items():
    df = pd.read_csv(EVAL / f"results_{run}.csv")
    df[["strict", "lenient"]] = [grade(r) for r in df.itertuples()]
    by = []
    for d in ["easy", "medium", "hard"]:
        x = df[df.difficulty == d]
        by.append({"difficulty": d, "questions": len(x), "strict": int(x.strict.sum()), "lenient": int(x.lenient.sum())})
    report["runs"].append({
        "run": run, "note": note,
        "strict": int(df.strict.sum()), "lenient": int(df.lenient.sum()),
        "strict_pct": round(100 * df.strict.mean(), 1), "lenient_pct": round(100 * df.lenient.mean(), 1),
        "median_seconds": round(float(df.seconds.median()), 2), "repaired": int(df.repaired.sum()),
        "by_difficulty": by,
        "labels_only": df[~df.strict & df.lenient].id.tolist(),
        "wrong": df[~df.lenient][["id", "question"]].to_dict(orient="records"),
    })
    print(f"{run}: strict {df.strict.sum()}/40 ({100 * df.strict.mean():.1f}%), "
          f"lenient {df.lenient.sum()}/40 ({100 * df.lenient.mean():.1f}%)")

att = pd.read_csv(EVAL / "attack_results_v2.csv")
report["attacks"] = {"total": len(att), "outcomes": att.outcome.value_counts().to_dict(),
                     "list": att[["prompt", "outcome"]].to_dict(orient="records")}
print("attacks:", report["attacks"]["outcomes"])
(EVAL / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("Saved eval/evaluation.json")
