# WHOOP Data Downloader

A standalone Python CLI that authenticates to the **WHOOP v2 developer API**,
pulls your full history, and writes CSV files matching WHOOP's official account
export (header-for-header).

It is a one-shot downloader — no server, no database. Run it, it authenticates,
fetches, and writes CSVs.

## Output

Three CSVs in `./out/` (or `--out`):

| File | Source |
|------|--------|
| `physiological_cycles.csv` | cycle ⨝ recovery ⨝ that cycle's sleep |
| `sleeps.csv` | sleep records |
| `workouts.csv` | workout records |

> `journal_entries.csv` is **not** produced — journal/behavior data is only in
> WHOOP's manual account export and is not exposed by the developer API.

## Requirements

- Python 3.8+
- `pip install -r requirements.txt` (just `requests` + `python-dateutil`)

```bash
cd whoop-downloader
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

## Setup: WHOOP app credentials

This tool needs a WHOOP developer app's `client_id` / `client_secret`.

1. Go to <https://developer.whoop.com> → your app (apps with <10 users need no
   review).
2. **Add `http://localhost:8080/callback` as an allowed Redirect URI.** This is
   required for the local browser login flow. (If WHOOP rejects `http://`, the
   manual flow below still works — you just paste the code by hand.)
3. Confirm the app allows these scopes:
   `offline read:cycles read:recovery read:sleep read:workout read:profile`.
   **`offline` is required** to receive a refresh token.
4. Put the credentials in a `.env` file in this folder:

   ```
   WHOOP_CLIENT_ID=your_client_id
   WHOOP_CLIENT_SECRET=your_client_secret
   ```

   (A `.env` is pre-populated with the credentials reused from the Recomp-Coach
   app. It is git-ignored.)

## Usage

```bash
# one-time login (opens browser, stores token at ~/.whoop-downloader/token.json)
python -m whoop_dl auth login

# if the browser/localhost flow fails, paste the code by hand:
python -m whoop_dl auth login --manual

# check token validity
python -m whoop_dl auth status

# export entire history -> ./out/*.csv
python -m whoop_dl export

# export a date range
python -m whoop_dl export --start 2026-01-01 --end 2026-06-28

# custom output directory
python -m whoop_dl export --out ./my_export/
```

`auth login` finishes by fetching one cycle and printing it — a built-in check
that auth and the API both work before you run a full export.

## Auth notes

- **Refresh tokens rotate.** Every refresh returns a *new* refresh token that
  replaces the old one; the tool persists the new bundle each time. If auth ever
  breaks, just run `auth login` again.
- Access tokens last ~1 hour. `export` refreshes automatically when the token is
  near expiry (and once more if the API returns 401 mid-run).
- The token bundle lives at `~/.whoop-downloader/token.json` (chmod 600 where
  supported). Keep it private.

## Format conventions (match the official export)

- Timestamps are local wall-clock `YYYY-MM-DD HH:MM:SS`; the offset is in the
  `Cycle timezone` column as e.g. `UTC-07:00`.
- `Cycle end time` is blank for the current still-open cycle.
- Durations are whole minutes (API returns ms → ÷60000, rounded).
- `Energy burned (cal)` = kilojoules ÷ 4.184 (kcal, displayed as "cal").
- HR Zone columns are integer % of total recorded zone time.
- `Nap` and `GPS enabled` are lowercase `true`/`false`.
- Rows are sorted newest-first.

## Known gaps (columns left blank, never fabricated)

- **Skin temp (celsius)** and **Blood oxygen %** — only available for WHOOP 4.0+
  members via the recovery object. Blank when the API omits them.
- **Recovery columns** are blank for any cycle with no recovery (e.g. strap not
  worn) — the cycle row is still emitted.
- **GPS enabled** is inferred from the presence of GPS-derived fields
  (`distance_meter` / `altitude_gain_meter`) in the workout score, since the API
  has no explicit flag. Best-effort.
- A few cycle-panel values in the manual account export are export-only and may
  not be reproducible from the developer API. Blank is acceptable.

## Fallback (not implemented)

The internal `app.whoop.com` API (used by the WHOOP web app) can expose a few
extra fields but is undocumented and unsupported. This tool deliberately uses
only the official `api.prod.whoop.com/developer` v2 API.

## Run both at once (`downloader`)

A thin wrapper runs both exporters into one folder. Each source is independent —
if WHOOP isn't authenticated, Wyze still exports (and vice versa).

```bash
pip install -r requirements.txt -r requirements-wyze.txt   # both toolsets

python -m downloader                       # WHOOP + Wyze -> ./out/  (4 CSVs)
python -m downloader --start 2026-01-01 --end 2026-06-28
python -m downloader --out ./my_export/
python -m downloader --skip-whoop          # Wyze only
python -m downloader --skip-wyze           # WHOOP only
```

It prints a per-source SUMMARY at the end. Exit code is non-zero if any source
failed. (WHOOP still requires a one-time `python -m whoop_dl auth login` first.)

## Companion: Wyze Scale downloader (`wyze_dl`)

WHOOP's developer API does **not** expose body-composition data (body fat %,
lean mass), even when you see it in the WHOOP app — that data is ingested from
Health Connect / Withings / Wyze for display only. To get it, go to the source.

`wyze_dl` pulls your Wyze Scale history (the same readings that flow
Wyze → Health Connect → WHOOP) via the unofficial
[`wyze-sdk`](https://github.com/shauntarves/wyze-sdk) and writes
`body_composition.csv`: date, weight (lb + kg), body fat %, lean mass (derived
as weight × (1 − body fat%), matching WHOOP), plus muscle mass, body water %,
BMI, BMR, bone mineral, protein %, visceral fat, metabolic age.

### Setup

```bash
pip install -r requirements-wyze.txt   # wyze-sdk (heavier; separate from whoop_dl)
```

Add Wyze credentials to the same `.env`:

```
WYZE_EMAIL=you@example.com
WYZE_PASSWORD=your_password
WYZE_KEY_ID=...        # from developer-api-console.wyze.com/#/apikey/view
WYZE_API_KEY=...
# WYZE_TOTP_KEY=...     # only if 2FA is enabled (base32 secret)
```

### Usage

```bash
python -m wyze_dl list                       # list scales (auth check)
python -m wyze_dl export                      # all history -> ./out/body_composition.csv
python -m wyze_dl export --start 2026-01-01   # date range
```

Output columns: Date, Weight (lb), Weight (kg), Body fat %, Lean mass (lb),
Lean mass %, Muscle mass (lb), Body water %, BMI, BMR (cal), Bone mineral (lb),
Protein %, Visceral fat, Metabolic age, Source MAC, Record ID. The scale logs
every step-on, so you may see several records seconds apart — all are kept.

### Notes / known gaps
- `wyze-sdk` is **unofficial / reverse-engineered** — Wyze can change auth and
  break it. It is the current working method (Wyze has no public scale API).
- **Windows SSL:** Wyze's device API (`api.wyzecam.com`) can fail cert
  verification on Windows (`CERTIFICATE_VERIFY_FAILED`). `requirements-wyze.txt`
  includes `pip-system-certs`, which routes verification through the Windows
  trust store and fixes it. (Needed because of a missing intermediate cert / TLS
  inspection, not a credential problem.)
- **Auth needs a native Wyze password** — accounts that only use "Sign in with
  Google/Apple" must set a password in the Wyze app first. 2FA accounts also
  need `WYZE_TOTP_KEY`.
- Auth is plain credentials + API key — no browser flow, no token caching; it
  logs in fresh each run.
- Wyze has **no lean-mass field**; lean mass is computed as
  `weight × (1 − body_fat%)`. Mass metrics (muscle, bone) are converted kg→lb;
  percentages (body water, protein) are passed through. Verify a row against the
  Wyze app once to confirm units.

## Project layout

```
whoop-downloader/
  whoop_dl/             # WHOOP exporter (requests + python-dateutil only)
    __init__.py
    __main__.py         # python -m whoop_dl
    auth.py             # OAuth flow, token storage + rotation/refresh
    client.py           # paginated GET helpers, 429 retry
    transform.py        # API JSON -> export row dicts (units, timezone)
    export.py           # join cycles+recovery+sleep, write 3 CSVs atomically
    cli.py              # argparse entrypoints
  wyze_dl/              # Wyze Scale exporter (needs wyze-sdk)
    __init__.py
    __main__.py         # python -m wyze_dl
    config.py           # credential loading
    client.py           # wyze-sdk wrapper: auth, list, fetch records
    transform.py        # ScaleRecord -> CSV row (units, tz, derived lean mass)
    export.py           # write body_composition.csv atomically
    cli.py              # argparse entrypoints
  downloader/          # wrapper: runs both exporters into one folder
    __init__.py
    __main__.py         # python -m downloader
    cli.py
  requirements.txt        # whoop_dl deps
  requirements-wyze.txt   # wyze_dl deps
  README.md
  .gitignore
```
