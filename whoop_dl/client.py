"""Paginated GET helpers for the WHOOP v2 developer API.

Handles bearer-token auth (via auth.py), 429 rate-limit backoff, a single
401-triggered token refresh, and nextToken pagination.
"""

import time

import requests

from . import auth

API_BASE = "https://api.prod.whoop.com/developer"

MAX_PAGE_LIMIT = 25
MAX_RETRIES = 6


def _get(path, params=None):
    """GET a single API page with retry on 429 and one refresh on 401."""
    token = auth.get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = API_BASE + path
    backoff = 2
    did_refresh = False

    for attempt in range(MAX_RETRIES):
        resp = requests.get(url, headers=headers, params=params, timeout=30)

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = int(retry_after) if (retry_after and retry_after.isdigit()) else backoff
            time.sleep(wait)
            backoff = min(backoff * 2, 60)
            continue

        if resp.status_code == 401 and not did_refresh:
            # Access token likely expired between calls — force one refresh.
            token = auth.force_refresh()
            headers["Authorization"] = f"Bearer {token}"
            did_refresh = True
            continue

        if not resp.ok:
            raise RuntimeError(f"GET {path} -> {resp.status_code}: {resp.text}")

        return resp.json()

    raise RuntimeError(f"GET {path} failed after {MAX_RETRIES} retries (rate-limited?)")


def get_collection(path, start=None, end=None, limit=MAX_PAGE_LIMIT, verbose=False):
    """Fetch every page of a collection endpoint, following next_token.

    start / end are RFC3339 strings (or None for full history).
    Returns the concatenated list of record dicts.
    """
    limit = min(limit, MAX_PAGE_LIMIT)
    records = []
    next_token = None
    page = 0

    while True:
        params = {"limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if next_token:
            params["nextToken"] = next_token

        data = _get(path, params=params)
        batch = data.get("records", []) or []
        records.extend(batch)
        page += 1
        if verbose:
            print(f"    {path}: page {page} (+{len(batch)} = {len(records)})")

        next_token = data.get("next_token")
        if not next_token:
            break

    return records
