"""Transform WHOOP v2 API JSON into export-format row dicts.

Unit conversions:
  - timestamps: API UTC ISO -> local wall-clock 'YYYY-MM-DD HH:MM:SS' using the
    record's timezone_offset; the offset itself goes in the 'Cycle timezone'
    column as 'UTC-07:00'.
  - durations: API milliseconds -> minutes (rounded).
  - energy: API kilojoules -> calories (kcal) via cal = kJ / 4.184.
  - HR zones: API zone durations (ms) -> integer % of total zone time.

Row dict keys are the EXACT export header strings (see the *_HEADERS lists),
so export.py can hand them straight to csv.DictWriter.
"""

from datetime import timedelta, timezone

from dateutil import parser as dtparser

KJ_PER_CAL = 4.184

# --------------------------------------------------------------------------- #
# Exact export headers (copy verbatim — column order/spelling must match)
# --------------------------------------------------------------------------- #
CYCLE_HEADERS = [
    "Cycle start time", "Cycle end time", "Cycle timezone", "Recovery score %",
    "Resting heart rate (bpm)", "Heart rate variability (ms)", "Skin temp (celsius)",
    "Blood oxygen %", "Day Strain", "Energy burned (cal)", "Max HR (bpm)",
    "Average HR (bpm)", "Sleep onset", "Wake onset", "Sleep performance %",
    "Respiratory rate (rpm)", "Asleep duration (min)", "In bed duration (min)",
    "Light sleep duration (min)", "Deep (SWS) duration (min)", "REM duration (min)",
    "Awake duration (min)", "Sleep need (min)", "Sleep debt (min)",
    "Sleep efficiency %", "Sleep consistency %",
]

SLEEP_HEADERS = [
    "Cycle start time", "Cycle end time", "Cycle timezone", "Sleep onset",
    "Wake onset", "Sleep performance %", "Respiratory rate (rpm)",
    "Asleep duration (min)", "In bed duration (min)", "Light sleep duration (min)",
    "Deep (SWS) duration (min)", "REM duration (min)", "Awake duration (min)",
    "Sleep need (min)", "Sleep debt (min)", "Sleep efficiency %",
    "Sleep consistency %", "Nap",
]

WORKOUT_HEADERS = [
    "Cycle start time", "Cycle end time", "Cycle timezone", "Workout start time",
    "Workout end time", "Duration (min)", "Activity name", "Activity Strain",
    "Energy burned (cal)", "Max HR (bpm)", "Average HR (bpm)", "HR Zone 1 %",
    "HR Zone 2 %", "HR Zone 3 %", "HR Zone 4 %", "HR Zone 5 %", "GPS enabled",
]

# Keys shared between the cycle sleep panel and sleeps.csv.
_SLEEP_PANEL_KEYS = [
    "Sleep onset", "Wake onset", "Sleep performance %", "Respiratory rate (rpm)",
    "Asleep duration (min)", "In bed duration (min)", "Light sleep duration (min)",
    "Deep (SWS) duration (min)", "REM duration (min)", "Awake duration (min)",
    "Sleep need (min)", "Sleep debt (min)", "Sleep efficiency %",
    "Sleep consistency %",
]

# v2 returns sport_name as a lowercase slug (e.g. "mountain-biking",
# "weightlifting_msk", "hot_tub"). We title-case it for the export. A couple of
# slugs don't title-case cleanly, so override them explicitly.
# NOTE: v2 sport_id numbering differs from v1 and is NOT a reliable name source,
# so we key off sport_name only.
_ACTIVITY_OVERRIDES = {
    "hiit": "HIIT",
    "weightlifting_msk": "Weightlifting",  # WHOOP's strength-strain variant
}
_ACTIVITY_ACRONYMS = {"hiit", "tv"}  # words to fully upper-case when title-casing


def format_activity_name(slug):
    """v2 sport_name slug -> readable name, e.g. 'mountain-biking' -> 'Mountain Biking'."""
    if not slug:
        return "Activity"
    key = slug.strip().lower()
    if key in _ACTIVITY_OVERRIDES:
        return _ACTIVITY_OVERRIDES[key]
    words = key.replace("-", " ").replace("_", " ").split()
    return " ".join(w.upper() if w in _ACTIVITY_ACRONYMS else w.capitalize() for w in words)


# --------------------------------------------------------------------------- #
# Low-level formatting helpers
# --------------------------------------------------------------------------- #
def parse_offset(offset_str):
    """'-07:00' -> (tzinfo, 'UTC-07:00'). Defaults to UTC if missing."""
    if not offset_str:
        return timezone.utc, "UTC+00:00"
    sign = -1 if offset_str.startswith("-") else 1
    body = offset_str.lstrip("+-")
    try:
        hh, mm = body.split(":")
        delta = timedelta(hours=int(hh), minutes=int(mm))
    except ValueError:
        return timezone.utc, "UTC+00:00"
    if sign < 0:
        delta = -delta
    label = "UTC" + (offset_str if offset_str[0] in "+-" else "+" + offset_str)
    return timezone(delta), label


def fmt_local(iso_ts, tzinfo):
    """API UTC ISO timestamp -> 'YYYY-MM-DD HH:MM:SS' in tzinfo. Blank if None."""
    if not iso_ts:
        return ""
    dt = dtparser.isoparse(iso_ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tzinfo).strftime("%Y-%m-%d %H:%M:%S")


def _cal(kj):
    if kj is None:
        return ""
    return round(kj / KJ_PER_CAL)


def _ms_to_min(ms):
    if ms is None:
        return ""
    return round(ms / 60000)


def _int(v):
    if v is None or v == "":
        return ""
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return ""


def _dec1(v):
    if v is None or v == "":
        return ""
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return ""


def _duration_min(start, end):
    if not start or not end:
        return ""
    a = dtparser.isoparse(start)
    b = dtparser.isoparse(end)
    return round((b - a).total_seconds() / 60)


def start_key(record):
    """Sort key for descending-by-start ordering."""
    return record.get("start") or ""


# --------------------------------------------------------------------------- #
# Sleep panel (shared by cycle rows and sleeps.csv)
# --------------------------------------------------------------------------- #
def _sleep_panel(sleep, tzinfo):
    if not sleep:
        return {k: "" for k in _SLEEP_PANEL_KEYS}
    score = sleep.get("score") or {}
    stages = score.get("stage_summary") or {}
    need = score.get("sleep_needed") or {}

    light = stages.get("total_light_sleep_time_milli")
    sws = stages.get("total_slow_wave_sleep_time_milli")
    rem = stages.get("total_rem_sleep_time_milli")
    awake = stages.get("total_awake_time_milli")
    in_bed = stages.get("total_in_bed_time_milli")

    asleep = None
    if None not in (light, sws, rem):
        asleep = light + sws + rem

    need_parts = [
        need.get("baseline_milli"),
        need.get("need_from_sleep_debt_milli"),
        need.get("need_from_recent_strain_milli"),
        need.get("need_from_recent_nap_milli"),
    ]
    need_total = sum(p or 0 for p in need_parts) if any(p is not None for p in need_parts) else None

    return {
        "Sleep onset": fmt_local(sleep.get("start"), tzinfo),
        "Wake onset": fmt_local(sleep.get("end"), tzinfo),
        "Sleep performance %": _int(score.get("sleep_performance_percentage")),
        "Respiratory rate (rpm)": _dec1(score.get("respiratory_rate")),
        "Asleep duration (min)": _ms_to_min(asleep),
        "In bed duration (min)": _ms_to_min(in_bed),
        "Light sleep duration (min)": _ms_to_min(light),
        "Deep (SWS) duration (min)": _ms_to_min(sws),
        "REM duration (min)": _ms_to_min(rem),
        "Awake duration (min)": _ms_to_min(awake),
        "Sleep need (min)": _ms_to_min(need_total),
        "Sleep debt (min)": _ms_to_min(need.get("need_from_sleep_debt_milli")),
        "Sleep efficiency %": _dec1(score.get("sleep_efficiency_percentage")),
        "Sleep consistency %": _int(score.get("sleep_consistency_percentage")),
    }


# --------------------------------------------------------------------------- #
# Row builders
# --------------------------------------------------------------------------- #
def build_cycle_rows(cycles, recoveries, sleeps):
    """physiological_cycles.csv = cycle JOIN recovery JOIN that cycle's sleep."""
    rec_by_cycle = {r.get("cycle_id"): r for r in recoveries}
    sleep_by_id = {s.get("id"): s for s in sleeps}

    rows = []
    for cyc in cycles:
        tzinfo, tzlabel = parse_offset(cyc.get("timezone_offset"))
        cscore = cyc.get("score") or {}

        rec = rec_by_cycle.get(cyc.get("id"))
        rscore = (rec.get("score") if rec else None) or {}
        sleep = sleep_by_id.get(rec.get("sleep_id")) if rec and rec.get("sleep_id") else None

        row = {
            "Cycle start time": fmt_local(cyc.get("start"), tzinfo),
            "Cycle end time": fmt_local(cyc.get("end"), tzinfo),  # blank if open cycle
            "Cycle timezone": tzlabel,
            "Recovery score %": _int(rscore.get("recovery_score")),
            "Resting heart rate (bpm)": _int(rscore.get("resting_heart_rate")),
            "Heart rate variability (ms)": _int(rscore.get("hrv_rmssd_milli")),
            "Skin temp (celsius)": _dec1(rscore.get("skin_temp_celsius")),
            "Blood oxygen %": _dec1(rscore.get("spo2_percentage")),
            "Day Strain": _dec1(cscore.get("strain")),
            "Energy burned (cal)": _cal(cscore.get("kilojoule")),
            "Max HR (bpm)": _int(cscore.get("max_heart_rate")),
            "Average HR (bpm)": _int(cscore.get("average_heart_rate")),
        }
        row.update(_sleep_panel(sleep, tzinfo))
        rows.append(row)
    return rows


def build_sleep_rows(sleeps):
    """sleeps.csv = sleep records directly."""
    rows = []
    for sleep in sleeps:
        tzinfo, tzlabel = parse_offset(sleep.get("timezone_offset"))
        row = {
            "Cycle start time": fmt_local(sleep.get("start"), tzinfo),
            "Cycle end time": fmt_local(sleep.get("end"), tzinfo),
            "Cycle timezone": tzlabel,
            "Nap": "true" if sleep.get("nap") else "false",
        }
        row.update(_sleep_panel(sleep, tzinfo))
        rows.append(row)
    return rows


def _find_cycle(workout_start_iso, cycles):
    """Find the physiological cycle whose [start, end) contains the workout start."""
    if not workout_start_iso:
        return None
    ws = dtparser.isoparse(workout_start_iso)
    for cyc in cycles:
        cstart_iso = cyc.get("start")
        if not cstart_iso:
            continue
        cstart = dtparser.isoparse(cstart_iso)
        cend_iso = cyc.get("end")
        cend = dtparser.isoparse(cend_iso) if cend_iso else None
        if ws >= cstart and (cend is None or ws < cend):
            return cyc
    return None


def _zone_pcts(score):
    """Return [z1%, z2%, z3%, z4%, z5%] as integers of total zone time.

    WHOOP exposes six zone buckets (zero..five); the export shows zones 1-5,
    each as a % of total recorded time (zone zero is the implicit remainder).
    Handles both 'zone_durations' (v2) and legacy 'zone_duration'.
    """
    zd = score.get("zone_durations") or score.get("zone_duration") or {}
    all_keys = [
        "zone_zero_milli", "zone_one_milli", "zone_two_milli",
        "zone_three_milli", "zone_four_milli", "zone_five_milli",
    ]
    total = sum((zd.get(k) or 0) for k in all_keys)
    if not total:
        return ["", "", "", "", ""]
    display_keys = [
        "zone_one_milli", "zone_two_milli", "zone_three_milli",
        "zone_four_milli", "zone_five_milli",
    ]
    return [round((zd.get(k) or 0) / total * 100) for k in display_keys]


def build_workout_rows(workouts, cycles):
    """workouts.csv = workout records directly, joined to containing cycle times."""
    rows = []
    for wk in workouts:
        tzinfo, tzlabel = parse_offset(wk.get("timezone_offset"))
        score = wk.get("score") or {}

        cyc = _find_cycle(wk.get("start"), cycles)
        if cyc:
            ctz, ctzlabel = parse_offset(cyc.get("timezone_offset"))
            cycle_start = fmt_local(cyc.get("start"), ctz)
            cycle_end = fmt_local(cyc.get("end"), ctz)
        else:
            ctzlabel = tzlabel
            cycle_start = ""
            cycle_end = ""

        name = format_activity_name(wk.get("sport_name"))
        gps = bool(score.get("distance_meter")) or bool(score.get("altitude_gain_meter"))
        z1, z2, z3, z4, z5 = _zone_pcts(score)

        rows.append({
            "Cycle start time": cycle_start,
            "Cycle end time": cycle_end,
            "Cycle timezone": ctzlabel,
            "Workout start time": fmt_local(wk.get("start"), tzinfo),
            "Workout end time": fmt_local(wk.get("end"), tzinfo),
            "Duration (min)": _duration_min(wk.get("start"), wk.get("end")),
            "Activity name": name,
            "Activity Strain": _dec1(score.get("strain")),
            "Energy burned (cal)": _cal(score.get("kilojoule")),
            "Max HR (bpm)": _int(score.get("max_heart_rate")),
            "Average HR (bpm)": _int(score.get("average_heart_rate")),
            "HR Zone 1 %": z1,
            "HR Zone 2 %": z2,
            "HR Zone 3 %": z3,
            "HR Zone 4 %": z4,
            "HR Zone 5 %": z5,
            "GPS enabled": "true" if gps else "false",
        })
    return rows
