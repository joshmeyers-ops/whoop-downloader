"""Wyze auth + data access with token caching.

Wyze rate-limits its LOGIN endpoint aggressively (HTTP 429). Logging in on every
run trips that limit, so we cache the access/refresh tokens after the first
login (~/.wyze-downloader/token.json) and reuse them. Normal runs then never
hit the login endpoint; an expired access token is renewed via the refresh
endpoint, and only a failed refresh falls back to a full login.
"""

import json
import os
import time

from . import config

TOKEN_DIR = os.path.join(os.path.expanduser("~"), ".wyze-downloader")
TOKEN_PATH = os.path.join(TOKEN_DIR, "token.json")


# --------------------------------------------------------------------------- #
# Token cache
# --------------------------------------------------------------------------- #
def _load_token():
    if not os.path.isfile(TOKEN_PATH):
        return None
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _save_token(client):
    token = getattr(client, "_token", None)
    if not token:
        return
    os.makedirs(TOKEN_DIR, exist_ok=True)
    tmp = TOKEN_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({
            "access_token": token,
            "refresh_token": getattr(client, "_refresh_token", None),
            "obtained_at": int(time.time()),
        }, fh, indent=2)
    os.replace(tmp, TOKEN_PATH)
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        pass


def clear_token():
    try:
        os.remove(TOKEN_PATH)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# Client construction
# --------------------------------------------------------------------------- #
def _client_from_cache(creds, cached):
    """Build a client from cached tokens (does NOT log in)."""
    from wyze_sdk import Client

    return Client(
        token=cached.get("access_token"),
        refresh_token=cached.get("refresh_token"),
        # creds passed too so refresh_token()/re-login have what they need,
        # but the constructor skips login because token is set.
        email=creds["email"],
        password=creds["password"],
        key_id=creds["key_id"],
        api_key=creds["api_key"],
        totp_key=creds["totp_key"],
    )


def login(creds=None, verbose=False):
    """Full login via the (rate-limited) login endpoint. Caches the tokens."""
    from wyze_sdk import Client

    creds = creds or config.get_creds()
    if verbose:
        print("Logging in to Wyze (this hits the rate-limited login endpoint)...")
    try:
        client = Client(
            email=creds["email"],
            password=creds["password"],
            key_id=creds["key_id"],
            api_key=creds["api_key"],
            totp_key=creds["totp_key"],
        )
    except Exception as exc:  # noqa: BLE001
        if _is_rate_limited(exc):
            raise RuntimeError(
                "Wyze is temporarily rate-limiting logins (HTTP 429). Wait "
                "~30-60 minutes, then try again. Avoid repeated runs in the "
                "meantime -- each attempt restarts the cooldown."
            ) from exc
        raise
    _save_token(client)
    return client


def get_client():
    """Return a client from the cached token if present, else a fresh login."""
    creds = config.get_creds()
    cached = _load_token()
    if cached and cached.get("access_token"):
        return _client_from_cache(creds, cached)
    return login(creds, verbose=True)


# --------------------------------------------------------------------------- #
# Auth-resilient operation runner
# --------------------------------------------------------------------------- #
def _is_rate_limited(exc):
    s = f"{exc}".lower()
    return "429" in s or "too many" in s


def _is_auth_error(exc):
    s = f"{type(exc).__name__} {exc}".lower()
    return any(k in s for k in (
        "token", "unauthor", "401", "expired", "session", "2001", "access denied",
    ))


def run(op, verbose=False):
    """Run op(client), renewing auth on token failure.

    1. Use the cached token.
    2. On an auth error, renew via the refresh endpoint (not login).
    3. If refresh fails, fall back to a full login.
    Non-auth errors propagate unchanged (so we don't re-login on, say, a 429).
    """
    client = get_client()
    try:
        return op(client)
    except Exception as first:  # noqa: BLE001
        if _is_rate_limited(first) or not _is_auth_error(first):
            raise
        # Try a token refresh (uses the refresh endpoint, not login).
        try:
            if getattr(client, "_refresh_token", None):
                if verbose:
                    print("Access token expired; refreshing...")
                client.refresh_token()
                _save_token(client)
                return op(client)
        except Exception:  # noqa: BLE001 -- fall through to full login
            pass
        # Last resort: full login.
        if verbose:
            print("Refresh failed; performing a full login...")
        client = login(verbose=verbose)
        return op(client)


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #
def list_scales(verbose=False):
    return run(lambda c: c.scales.list(), verbose=verbose)


def fetch_records(start, end, verbose=False):
    """Return (records, scales) for the date range. Auth handled internally."""

    def op(client):
        scales = client.scales.list()

        seen_models = []
        for s in scales:
            model = getattr(getattr(s, "product", None), "model", None)
            if model and model not in seen_models:
                seen_models.append(model)
        if not seen_models:
            seen_models = [None]  # let get_records use its default model

        records = []
        seen_ids = set()
        for model in seen_models:
            kwargs = {"start_time": start, "end_time": end}
            if model:
                kwargs["device_model"] = model
            recs = client.scales.get_records(**kwargs)
            for r in recs:
                rid = getattr(r, "id", None)
                if rid is not None and rid in seen_ids:
                    continue
                seen_ids.add(rid)
                records.append(r)
            if verbose:
                print(f"    model {model or 'default'}: {len(recs)} records")
        return records, scales

    return run(op, verbose=verbose)
