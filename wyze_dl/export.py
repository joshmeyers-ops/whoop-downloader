"""Fetch Wyze scale history and write body_composition.csv atomically."""

import csv
import os
from datetime import datetime

from . import client, transform

DEFAULT_START = datetime(2015, 1, 1)  # well before any Wyze scale existed


def _parse_date(date_str, default):
    if not date_str:
        return default
    return datetime.strptime(date_str, "%Y-%m-%d")


def _write_csv(out_dir, filename, headers, rows):
    path = os.path.join(out_dir, filename)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(tmp, path)
    return path


def export_all(out_dir="out", start=None, end=None, verbose=True):
    start_dt = _parse_date(start, DEFAULT_START)
    end_dt = _parse_date(end, datetime.now())
    # cover the whole end day
    end_dt = end_dt.replace(hour=23, minute=59, second=59)

    if verbose:
        print(f"Fetching scale records ({start_dt.date()} -> {end_dt.date()})...")
    records, scales = client.fetch_records(start_dt, end_dt, verbose=verbose)

    if verbose:
        names = ", ".join(getattr(s, "nickname", "?") or "?" for s in scales) or "(none listed)"
        print(f"  scales: {names}")

    rows = transform.build_rows(records)

    os.makedirs(out_dir, exist_ok=True)
    path = _write_csv(out_dir, "body_composition.csv", transform.HEADERS, rows)

    if verbose:
        print(f"\n[OK] Wrote {len(rows)} records to {path}")
        if rows:
            r = rows[0]
            print(
                f"     Latest: {r['Date']}  "
                f"{r['Weight (lb)']} lb  {r['Body fat %']}% BF  "
                f"{r['Lean mass (lb)']} lb lean"
            )
    return {"records": len(rows)}
