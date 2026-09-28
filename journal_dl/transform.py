"""Parse WHOOP journal_entries.csv into clean alcohol + full-journal rows.

Defensive by design: WHOOP's exact column headers/wording can vary, so we
detect columns by keyword, and for alcohol we preserve the raw question+answer
in a "Journal detail" column so nothing is lost if the yes/no vs count
heuristic misreads an unusual format.
"""

import csv
import re
from collections import Counter, defaultdict

# Question-text keywords that mark a row as alcohol-related.
ALCOHOL_KEYWORDS = ("alcohol", "drink")

ALCOHOL_HEADERS = ["Date", "Drank alcohol", "Number of drinks", "Journal detail"]
JOURNAL_ALL_HEADERS = ["Date", "Cycle start time", "Question", "Answer", "Notes"]


# --------------------------------------------------------------------------- #
# Reading + column detection
# --------------------------------------------------------------------------- #
def read_rows(path):
    """Return (fieldnames, rows). utf-8-sig strips a BOM if WHOOP includes one."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    return (reader.fieldnames or []), rows


def _find_col(fieldnames, *needles):
    """First header containing all needle substrings (case-insensitive)."""
    for f in fieldnames:
        low = (f or "").lower()
        if all(n in low for n in needles):
            return f
    return None


def detect_columns(fieldnames):
    """Map logical fields -> actual header names in this file."""
    return {
        "date": _find_col(fieldnames, "cycle", "start")
        or _find_col(fieldnames, "start")
        or _find_col(fieldnames, "date"),
        "timezone": _find_col(fieldnames, "timezone"),
        "question": _find_col(fieldnames, "question"),
        # WHOOP uses "Answered yes" (true/false); other exports may say "answer".
        "answer": _find_col(fieldnames, "answered") or _find_col(fieldnames, "answer"),
        "notes": _find_col(fieldnames, "notes"),
    }


# --------------------------------------------------------------------------- #
# Small value helpers
# --------------------------------------------------------------------------- #
def _day(value):
    """First 10 chars of a 'YYYY-MM-DD HH:MM:SS' timestamp -> the date."""
    return (value or "").strip()[:10]


def _parse_bool(value):
    v = (value or "").strip().lower()
    if v in ("true", "yes", "y", "1"):
        return True
    if v in ("false", "no", "n", "0"):
        return False
    return None


def _extract_number(value):
    """First number found in a string, e.g. '3 drinks' -> 3, '1-2' -> 1."""
    m = re.search(r"\d+(?:\.\d+)?", value or "")
    return m.group(0) if m else None


# --------------------------------------------------------------------------- #
# Diagnostics
# --------------------------------------------------------------------------- #
def distinct_questions(rows, question_col):
    """List (question_text, count) most-common first."""
    counter = Counter((r.get(question_col) or "").strip() for r in rows if question_col)
    return counter.most_common()


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def build_alcohol_rows(rows, cols):
    """One row per day that has any alcohol/drink journal entry, newest first."""
    date_c, q_c, a_c = cols["date"], cols["question"], cols["answer"]
    by_day = defaultdict(list)
    for r in rows:
        q = (r.get(q_c) or "") if q_c else ""
        if any(k in q.lower() for k in ALCOHOL_KEYWORDS):
            by_day[_day(r.get(date_c) if date_c else "")].append(r)

    out = []
    for day in sorted(by_day, reverse=True):
        drank = ""
        drinks = ""
        details = []
        for r in by_day[day]:
            q = (r.get(q_c) or "").strip() if q_c else ""
            a = (r.get(a_c) or "").strip() if a_c else ""
            details.append(f"{q} = {a}" if a else q)
            ql = q.lower()
            if "how many" in ql or "number" in ql or "how much" in ql:
                num = _extract_number(a)
                if num is not None:
                    drinks = num
            else:
                b = _parse_bool(a)
                if b is not None:
                    # Any "true" alcohol behavior means drank; don't overwrite a
                    # prior true with a later false from a different sub-question.
                    if b or drank == "":
                        drank = "true" if b else "false"

        # A positive drink count implies alcohol was consumed.
        try:
            if drinks not in ("", None) and float(drinks) > 0:
                drank = "true"
        except ValueError:
            pass

        out.append({
            "Date": day,
            "Drank alcohol": drank,
            "Number of drinks": drinks,
            "Journal detail": " | ".join(details),
        })
    return out


def build_journal_all_rows(rows, cols):
    """Every journal answer, long format, newest first. Loses nothing."""
    date_c, q_c, a_c, n_c = cols["date"], cols["question"], cols["answer"], cols["notes"]
    out = []
    for r in rows:
        start = (r.get(date_c) or "").strip() if date_c else ""
        out.append({
            "Date": _day(start),
            "Cycle start time": start,
            "Question": (r.get(q_c) or "").strip() if q_c else "",
            "Answer": (r.get(a_c) or "").strip() if a_c else "",
            "Notes": (r.get(n_c) or "").strip() if n_c else "",
        })
    out.sort(key=lambda x: x["Cycle start time"], reverse=True)
    return out
