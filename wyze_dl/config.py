"""Credential loading for wyze_dl (reads .env or environment).

Required: WYZE_EMAIL, WYZE_PASSWORD, WYZE_KEY_ID, WYZE_API_KEY
Optional: WYZE_TOTP_KEY (base32 TOTP secret, only if 2FA is enabled)

Generate WYZE_KEY_ID / WYZE_API_KEY at:
  https://developer-api-console.wyze.com/#/apikey/view
"""

import os

_REQUIRED = ["WYZE_EMAIL", "WYZE_PASSWORD", "WYZE_KEY_ID", "WYZE_API_KEY"]


def _load_dotenv():
    """Populate os.environ from a .env file (cwd first, then project root)."""
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
        break


def get_creds():
    _load_dotenv()
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            "Missing Wyze credentials: "
            + ", ".join(missing)
            + "\nAdd them to a .env file. Get KEY_ID/API_KEY at "
            "https://developer-api-console.wyze.com/#/apikey/view"
        )
    return {
        "email": os.environ["WYZE_EMAIL"],
        "password": os.environ["WYZE_PASSWORD"],
        "key_id": os.environ["WYZE_KEY_ID"],
        "api_key": os.environ["WYZE_API_KEY"],
        "totp_key": os.environ.get("WYZE_TOTP_KEY") or None,
    }
