"""Fetch all collections, assemble the three CSVs, write them atomically.

Everything is assembled in memory first; files are only written once all four
API collections have been fetched successfully, so a mid-export failure leaves
no partial output.
"""

import csv
import os

from . import client, transform


def _to_iso(date_str, end_of_day=False):
    """'YYYY-MM-DD' -> RFC3339 instant at start/end of that UTC day."""
    if not date_str:
        return None
    suffix = "T23:59:59.999Z" if end_of_day else "T00:00:00.000Z"
    return date_str + suffix


def _write_csv(out_dir, filename, headers, rows):
    """Write rows (list of dicts keyed by header) to out_dir/filename atomically."""
    path = os.path.join(out_dir, filename)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(tmp, path)
    return path


def export_all(out_dir="out", start=None, end=None, limit=25, verbose=True):
    """Fetch history and write the three CSVs. Returns a dict of counts."""
    start_iso = _to_iso(start, end_of_day=False)
    end_iso = _to_iso(end, end_of_day=True)

    if verbose:
        rng = f"{start or 'beginning'} -> {end or 'now'}"
        print(f"Fetching WHOOP history ({rng})...")

    # --- fetch (fails before any file is written) ---------------------------
    if verbose:
        print("  cycles...")
    cycles = client.get_collection("/v2/cycle", start_iso, end_iso, limit, verbose)
    if verbose:
        print("  recovery...")
    recoveries = client.get_collection("/v2/recovery", start_iso, end_iso, limit, verbose)
    if verbose:
        print("  sleep...")
    sleeps = client.get_collection("/v2/activity/sleep", start_iso, end_iso, limit, verbose)
    if verbose:
        print("  workouts...")
    workouts = client.get_collection("/v2/activity/workout", start_iso, end_iso, limit, verbose)

    # --- sort newest-first (matches the official export) --------------------
    cycles.sort(key=transform.start_key, reverse=True)
    sleeps.sort(key=transform.start_key, reverse=True)
    workouts.sort(key=transform.start_key, reverse=True)

    # --- assemble rows in memory --------------------------------------------
    cycle_rows = transform.build_cycle_rows(cycles, recoveries, sleeps)
    sleep_rows = transform.build_sleep_rows(sleeps)
    workout_rows = transform.build_workout_rows(workouts, cycles)

    # --- write atomically ----------------------------------------------------
    os.makedirs(out_dir, exist_ok=True)
    _write_csv(out_dir, "physiological_cycles.csv", transform.CYCLE_HEADERS, cycle_rows)
    _write_csv(out_dir, "sleeps.csv", transform.SLEEP_HEADERS, sleep_rows)
    _write_csv(out_dir, "workouts.csv", transform.WORKOUT_HEADERS, workout_rows)

    counts = {
        "cycles": len(cycle_rows),
        "sleeps": len(sleep_rows),
        "workouts": len(workout_rows),
        "recoveries": len(recoveries),
    }
    if verbose:
        print(
            f"\n[OK] Wrote 3 CSVs to {os.path.abspath(out_dir)}\n"
            f"     physiological_cycles.csv  {counts['cycles']} rows "
            f"({counts['recoveries']} recoveries joined)\n"
            f"     sleeps.csv                {counts['sleeps']} rows\n"
            f"     workouts.csv              {counts['workouts']} rows"
        )
    return counts
