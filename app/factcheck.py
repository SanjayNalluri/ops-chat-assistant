"""Grade a written answer against the key facts it must contain (used for multi-step questions).

facts: "AL ; 22.22 ; 20.71". Facts are separated by ';'. A text fact may list accepted spellings
separated by '|' ("2017-11|november 2017"), matched case-insensitively as a substring
(short upper-case codes such as state 'AL' must appear as a whole word, in capitals).
A number fact matches a number in the answer only if it is the same value at the answer's precision:
whole numbers exactly (commas allowed, 7,288), decimals after rounding the fact to the decimals the answer
shows, so 22.2 or 22.22 match 22.22 but 3.94 does not match 3.98 and 2.27 does not match 2.25.
Unicode dashes and spaces (non-breaking hyphen, narrow no-break space) are normalised first.
"""
import re
import unicodedata

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")


def normalise(text: str) -> str:
    """Plain ASCII-ish text: NFKC (turns narrow/no-break spaces into spaces), unicode dashes -> '-'."""
    return unicodedata.normalize("NFKC", text or "").translate(_DASHES)

NUM = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")   # 7,288 / 22.22 / 7288 (not "1,2.25")


def _numbers(text: str):
    """[(value, decimals shown)] for every number in the text."""
    out = []
    for m in NUM.findall(text):
        m = m.replace(",", "").rstrip(".")
        try:
            out.append((float(m), len(m.split(".")[1]) if "." in m else 0))
        except ValueError:
            pass
    return out


def number_matches(v: float, n: float, decimals: int) -> bool:
    """Is n (shown with `decimals` places) the value v written at that precision?"""
    if decimals == 0:
        return abs(n - v) < 0.5 if not float(v).is_integer() else n == v
    return abs(round(v, decimals) - n) < 10 ** -(decimals + 3)


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def fact_found(fact: str, text: str) -> bool:
    fact, text = fact.strip(), normalise(text)
    if _is_number(fact):
        v = float(fact)
        return any(number_matches(v, abs(n), d) for n, d in _numbers(text))   # sign-insensitive: a "difference"
    low = text.lower()
    for alt in (a.strip() for a in fact.split("|")):
        if not alt:
            continue
        if alt.isupper() and len(alt) <= 3:                    # state codes: 'AL' must not match 'total'
            if re.search(rf"\b{re.escape(alt)}\b", text):
                return True
        elif alt.lower() in low:
            return True
    return False


def check_facts(facts: str, text: str):
    """Return (all_found, list of missing facts)."""
    items = [f for f in facts.split(";") if f.strip()]
    missing = [f.strip() for f in items if not fact_found(f, text or "")]
    return not missing, missing
