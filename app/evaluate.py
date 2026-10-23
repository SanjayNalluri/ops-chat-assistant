"""Compare a predicted query result with the hand-written (gold) result.

A prediction counts as correct when it returns the same number of rows and every gold column
has a matching column in the prediction (same values, in any row order; numbers within 0.01).
Extra columns in the prediction are allowed, e.g. an order count shown next to a late rate.

Lenient mode (relabel=True) also accepts answers whose row LABELS are written differently,
e.g. 'Late'/'On-time' instead of is_late 1/0, or '2018-01' instead of '2018-01-01'.
At most one gold column may be unmatched, it must have a different value in every row
(a row label), the result must have 2+ rows, and every other gold column must match.
"""
TOL = 0.011


def _norm(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    return str(v).strip().lower()


def _key(v):
    return (0, v) if isinstance(v, float) else (1, "" if v is None else str(v))


def _same(a, b):
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= TOL
    return a == b


def _column(rows, i):
    return sorted((_norm(r[i]) for r in rows), key=_key)


def results_match(gold_rows, pred_rows, relabel: bool = False) -> bool:
    if len(gold_rows) != len(pred_rows):
        return False
    if not gold_rows:
        return True
    gold_cols = [_column(gold_rows, i) for i in range(len(gold_rows[0]))]
    pred_cols = [_column(pred_rows, i) for i in range(len(pred_rows[0]))]
    used, missing = set(), []
    for g in gold_cols:
        hit = next((j for j, p in enumerate(pred_cols)
                    if j not in used and len(p) == len(g) and all(_same(x, y) for x, y in zip(g, p))), None)
        if hit is None:
            missing.append(g)
        else:
            used.add(hit)
    if not missing:
        return True
    # lenient: exactly one gold column unmatched, it is a row label (all values different),
    # there are 2+ rows and at least one other gold column matched
    return (relabel and len(missing) == 1 and len(gold_rows) >= 2 and len(gold_cols) >= 2
            and len(set(map(str, missing[0]))) == len(missing[0]))
