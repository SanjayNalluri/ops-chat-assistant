"""
Step 5 - Turn the evaluation runs into one small file the API and web app can show.

Inputs : eval/results_v1.csv, eval/results_v2.csv   40 development questions (runs while building)
         eval/results_holdout.csv                   60 held-out questions (if that run exists)
         eval/attack_results_holdout.csv            25 attack prompts (falls back to the v2 run's 10)
         data/deliverylens.db
Output : eval/evaluation.json

Every run is re-graded here with the same grader (strict and lenient), by re-running the SQL
the model wrote, so all runs are scored in exactly the same way.
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
DEV_RUNS = {"v1": "first run, schema notes only",
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


def summarise_run(df, run, note):
    df[["strict", "lenient"]] = [grade(r) for r in df.itertuples()]
    by = [{"difficulty": d, "questions": int((df.difficulty == d).sum()),
           "strict": int(df[df.difficulty == d].strict.sum()), "lenient": int(df[df.difficulty == d].lenient.sum())}
          for d in ["easy", "medium", "hard"]]
    out = {"run": run, "note": note, "questions": len(df),
           "strict": int(df.strict.sum()), "lenient": int(df.lenient.sum()),
           "strict_pct": round(100 * df.strict.mean(), 1), "lenient_pct": round(100 * df.lenient.mean(), 1),
           "median_seconds": round(float(df.seconds.median()), 2), "repaired": int(df.repaired.sum()),
           "by_difficulty": by,
           "labels_only": df[~df.strict & df.lenient].id.astype(str).tolist(),
           "wrong": df[~df.lenient][["id", "question"]].astype({"id": str}).to_dict(orient="records")}
    if "category" in df:
        out["by_category"] = [{"category": c, "questions": int(len(g)), "strict": int(g.strict.sum()),
                               "lenient": int(g.lenient.sum())} for c, g in df.groupby("category")]
    print(f"{run}: strict {out['strict']}/{len(df)} ({out['strict_pct']}%), "
          f"lenient {out['lenient']}/{len(df)} ({out['lenient_pct']}%)")
    return out


report = {"model": MODEL, "questions": 40, "runs": []}
for run, note in DEV_RUNS.items():
    report["runs"].append(summarise_run(pd.read_csv(EVAL / f"results_{run}.csv"), run, note))

hold = EVAL / "results_holdout.csv"
if hold.exists():
    df = pd.read_csv(hold)
    df = df.merge(pd.read_csv(EVAL / "holdout_questions.csv")[["id", "category"]], on="id", how="left")
    report["holdout"] = summarise_run(df, "holdout", "60 new questions written before the run; prompt and "
                                                    "schema notes unchanged since v2")

af = EVAL / "attack_results_holdout.csv"
if not af.exists():
    af = EVAL / "attack_results_v2.csv"
att = pd.read_csv(af)
report["attacks"] = {"total": len(att), "outcomes": att.outcome.value_counts().to_dict(),
                     "list": att[["prompt", "outcome"]].to_dict(orient="records")}
print("attacks:", report["attacks"]["outcomes"])
(EVAL / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("Saved eval/evaluation.json")
