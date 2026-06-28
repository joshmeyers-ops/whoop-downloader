"""Thin wrapper over wyze-sdk: authenticate, list scales, fetch records."""

from . import config


def make_client():
    """Construct an authenticated Wyze client (logs in via creds + API key)."""
    from wyze_sdk import Client  # imported lazily so config errors surface first

    creds = config.get_creds()
    # Passing email/password/key_id/api_key triggers login in the constructor.
    return Client(
        email=creds["email"],
        password=creds["password"],
        key_id=creds["key_id"],
        api_key=creds["api_key"],
        totp_key=creds["totp_key"],
    )


def list_scales(client):
    return client.scales.list()


def fetch_records(client, start, end, verbose=False):
    """Return (records, scales). Pulls records for each distinct scale model.

    get_records is keyed by device_model (+ logged-in user), not by MAC, so we
    query once per distinct model and dedup records by id.
    """
    scales = client.scales.list()

    models = []
    for s in scales:
        model = getattr(getattr(s, "product", None), "model", None)
        if model:
            models.append(model)
    # De-dup, preserve order. Fall back to the SDK's default model if list empty.
    seen_models = []
    for m in models:
        if m not in seen_models:
            seen_models.append(m)
    if not seen_models:
        seen_models = [None]  # let get_records use its default ('JA.SC')

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
