"""Command-line entrypoint for journal-dl."""

import argparse
import csv
import os
import sys

from . import transform

DEFAULT_CANDIDATES = ["journal_entries.csv", "input/journal_entries.csv"]


def _resolve_file(arg):
    candidates = [arg] if arg else DEFAULT_CANDIDATES
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    raise FileNotFoundError(
        "Could not find journal_entries.csv. Pass --file PATH, or drop the file "
        "in this folder (or ./input/). Get it from WHOOP: Settings -> Account -> "
        "Export My Data."
    )


def _write_csv(out_dir, filename, headers, rows):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(tmp, path)
    return path


def _cmd_questions(args):
    path = _resolve_file(args.file)
    fieldnames, rows = transform.read_rows(path)
    cols = transform.detect_columns(fieldnames)
    print(f"File: {path}")
    print(f"Rows: {len(rows)}")
    print(f"Headers: {fieldnames}")
    print(f"Detected columns: {cols}")
    if not cols["question"]:
        print("\n[WARN] No 'question' column detected — check the headers above.")
        return 1
    print("\nDistinct journal questions (count):")
    for q, n in transform.distinct_questions(rows, cols["question"]):
        mark = "  <-- ALCOHOL" if any(
            k in q.lower() for k in transform.ALCOHOL_KEYWORDS
        ) else ""
        print(f"  {n:5d}  {q}{mark}")
    return 0


def _cmd_export(args):
    path = _resolve_file(args.file)
    fieldnames, rows = transform.read_rows(path)
    cols = transform.detect_columns(fieldnames)

    missing = [k for k in ("date", "question") if not cols[k]]
    if missing:
        print(
            f"[ERROR] Could not detect required column(s): {missing}.\n"
            f"Headers found: {fieldnames}\n"
            f"Run `python -m journal_dl questions` to inspect the file.",
            file=sys.stderr,
        )
        return 1

    alcohol_rows = transform.build_alcohol_rows(rows, cols)
    all_rows = transform.build_journal_all_rows(rows, cols)

    a_path = _write_csv(args.out, "alcohol.csv", transform.ALCOHOL_HEADERS, alcohol_rows)
    j_path = _write_csv(args.out, "journal_all.csv", transform.JOURNAL_ALL_HEADERS, all_rows)

    drank_days = sum(1 for r in alcohol_rows if r["Drank alcohol"] == "true")
    print(f"[OK] Parsed {len(rows)} journal entries from {os.path.basename(path)}")
    print(f"     {a_path}   ({len(alcohol_rows)} days with alcohol entries, "
          f"{drank_days} where alcohol = true)")
    print(f"     {j_path}   ({len(all_rows)} total entries)")
    if alcohol_rows:
        print("\n     Most recent alcohol entries:")
        for r in alcohol_rows[:3]:
            print(f"       {r['Date']}  drank={r['Drank alcohol'] or '?'}  "
                  f"drinks={r['Number of drinks'] or '?'}  | {r['Journal detail']}")
        print("\n     Verify the above against your WHOOP app. If 'drank'/'drinks' look"
              "\n     wrong, run `python -m journal_dl questions` and share the output.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="journal-dl",
        description="Parse WHOOP's exported journal_entries.csv (alcohol + full journal).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_q = sub.add_parser("questions", help="list distinct journal questions (diagnostic)")
    p_q.add_argument("--file", help="path to journal_entries.csv")
    p_q.set_defaults(func=_cmd_questions)

    p_e = sub.add_parser("export", help="write alcohol.csv + journal_all.csv")
    p_e.add_argument("--file", help="path to journal_entries.csv")
    p_e.add_argument("--out", default="out", help="output directory (default: ./out)")
    p_e.set_defaults(func=_cmd_export)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
