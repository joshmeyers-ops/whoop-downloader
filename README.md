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

## Project layout

```
whoop-downloader/
  whoop_dl/
    __init__.py
    __main__.py     # python -m whoop_dl
    auth.py         # OAuth flow, token storage + rotation/refresh
    client.py       # paginated GET helpers, 429 retry
    transform.py    # API JSON -> export row dicts (units, timezone)
    export.py       # join cycles+recovery+sleep, write 3 CSVs atomically
    cli.py          # argparse entrypoints
  requirements.txt
  README.md
  .gitignore
```
