"""Convert wyze-sdk ScaleRecord objects into CSV row dicts.

Units: Wyze stores masses in kg internally. Weight is exposed via the SDK's
.weight property in lb; muscle/bone_mineral are raw kg. We output weight in both
lb and kg, mass-type metrics in lb, and percentage metrics as-is. Lean mass is
derived (weight x (1 - body_fat%)), matching how WHOOP computes Lean Body Mass.
"""

from datetime import datetime, timezone

from dateutil.tz import gettz

KG_TO_LB = 2.2046226218

HEADERS = [
    "Date", "Weight (lb)", "Weight (kg)", "Body fat %", "Lean mass (lb)",
    "Lean mass %", "Muscle mass (lb)", "Body water %", "BMI", "BMR (cal)",
    "Bone mineral (lb)", "Protein %", "Visceral fat", "Metabolic age",
    "Source MAC", "Record ID",
]


def _r1(v):
    return round(v, 1) if v is not None else ""


def _r0(v):
    return round(v) if v is not None else ""


def _kg_to_lb(v):
    return round(v * KG_TO_LB, 1) if v is not None else ""


def _fmt_ts(ts, tzname):
    """Epoch (s or ms) + IANA tz name -> 'YYYY-MM-DD HH:MM:SS' local."""
    if not ts:
        return ""
    secs = ts / 1000 if ts > 1e12 else ts
    dt = datetime.fromtimestamp(secs, tz=timezone.utc)
    tz = gettz(tzname) if tzname else None
    if tz:
        dt = dt.astimezone(tz)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def record_to_row(r):
    weight_lb = r.weight  # SDK property returns lb
    weight_kg = (weight_lb / KG_TO_LB) if weight_lb is not None else None
    body_fat = r.body_fat

    lean_lb = ""
    lean_pct = ""
    if weight_lb is not None and body_fat is not None:
        lean_lb = round(weight_lb * (1 - body_fat / 100), 1)
        lean_pct = round(100 - body_fat, 1)  # lean/weight x 100 == 100 - body fat%

    return {
        "Date": _fmt_ts(r.measure_ts, r.timezone),
        "Weight (lb)": _r1(weight_lb),
        "Weight (kg)": _r1(weight_kg),
        "Body fat %": _r1(body_fat),
        "Lean mass (lb)": lean_lb,
        "Lean mass %": lean_pct,
        "Muscle mass (lb)": _kg_to_lb(r.muscle),
        "Body water %": _r1(r.body_water),
        "BMI": _r1(r.bmi),
        "BMR (cal)": _r0(r.bmr),
        "Bone mineral (lb)": _kg_to_lb(r.bone_mineral),
        "Protein %": _r1(r.protein),
        "Visceral fat": _r1(r.body_vfr),
        "Metabolic age": _r0(r.metabolic_age),
        "Source MAC": r.mac or "",
        "Record ID": r.id or "",
    }


def build_rows(records):
    rows = [record_to_row(r) for r in records]
    rows.sort(key=lambda row: row["Date"], reverse=True)  # newest first
    return rows
