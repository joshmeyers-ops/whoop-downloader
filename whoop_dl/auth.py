"""OAuth 2.0 authorization-code flow with rotating refresh tokens.

WHOOP rotates refresh tokens: every refresh returns a NEW refresh token that
replaces the old one. We persist the new token bundle on every refresh, or auth
breaks on the next run.

Token bundle is stored at ~/.whoop-downloader/token.json.
Credentials (WHOOP_CLIENT_ID / WHOOP_CLIENT_SECRET) are read from the
environment or a local .env file.
"""

import json
import os
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
REDIRECT_URI = "http://localhost:8080/callback"
REDIRECT_PORT = 8080

# read:body_measurement is intentionally omitted — none of the three output
# CSVs need it, and requesting a scope the registered app does not allow causes
# the authorize step to fail. Add it here only if your WHOOP app allows it.
SCOPES = "offline read:cycles read:recovery read:sleep read:workout read:profile"

TOKEN_DIR = os.path.join(os.path.expanduser("~"), ".whoop-downloader")
TOKEN_PATH = os.path.join(TOKEN_DIR, "token.json")

# Refresh the access token if it is within this many seconds of expiry.
EXPIRY_SKEW = 300


# --------------------------------------------------------------------------- #
# Credentials / .env loading
# --------------------------------------------------------------------------- #
def _load_dotenv():
    """Populate os.environ from a .env file (cwd first, then project root).

    Minimal parser so we keep dependencies to requests + python-dateutil.
    Existing environment variables always win (setdefault).
    """
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


def _require(name):
    _load_dotenv()
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"{name} is not set. Put it in a .env file next to the project or "
            f"export it in your shell."
        )
    return val


def _client_id():
    return _require("WHOOP_CLIENT_ID")


def _client_secret():
    return _require("WHOOP_CLIENT_SECRET")


# --------------------------------------------------------------------------- #
# Token storage
# --------------------------------------------------------------------------- #
def load_tokens():
    if not os.path.isfile(TOKEN_PATH):
        return None
    with open(TOKEN_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_tokens(tok):
    """Persist the token bundle atomically, stamping obtained_at.

    Always call this after a refresh so the rotated refresh_token is kept.
    """
    bundle = dict(tok)
    bundle["obtained_at"] = int(time.time())
    os.makedirs(TOKEN_DIR, exist_ok=True)
    tmp = TOKEN_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2)
    os.replace(tmp, TOKEN_PATH)
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        pass  # best-effort on platforms without POSIX perms
    return bundle


def _is_expired(tok):
    obtained = tok.get("obtained_at", 0)
    expires_in = tok.get("expires_in", 3600)
    return time.time() >= (obtained + expires_in - EXPIRY_SKEW)


# --------------------------------------------------------------------------- #
# OAuth: authorization-code exchange + refresh
# --------------------------------------------------------------------------- #
def _build_authorize_url(state):
    params = {
        "response_type": "code",
        "client_id": _client_id(),
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def _exchange_code(code):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "redirect_uri": REDIRECT_URI,
    }
    resp = requests.post(TOKEN_URL, data=data, timeout=30)
    if not resp.ok:
        raise RuntimeError(f"Token exchange failed: {resp.status_code} {resp.text}")
    return resp.json()


def _refresh(tok):
    refresh_token = tok.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Stored token has no refresh_token. Run: whoop-dl auth login")
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": _client_id(),
        "client_secret": _client_secret(),
    }
    resp = requests.post(TOKEN_URL, data=data, timeout=30)
    if not resp.ok:
        raise RuntimeError(
            f"Refresh failed: {resp.status_code} {resp.text}\n"
            f"Re-authenticate with: whoop-dl auth login"
        )
    return _save_tokens(resp.json())  # persists the rotated refresh_token


def get_access_token():
    """Return a valid access token, refreshing (and rotating) if near expiry."""
    tok = load_tokens()
    if not tok:
        raise RuntimeError("Not authenticated. Run: whoop-dl auth login")
    if _is_expired(tok):
        tok = _refresh(tok)
    return tok["access_token"]


def force_refresh():
    """Force a refresh regardless of expiry (used after a 401)."""
    tok = load_tokens()
    if not tok:
        raise RuntimeError("Not authenticated. Run: whoop-dl auth login")
    return _refresh(tok)["access_token"]


# --------------------------------------------------------------------------- #
# Local callback server (browser flow)
# --------------------------------------------------------------------------- #
class _CallbackHandler(BaseHTTPRequestHandler):
    code = None
    error = None
    state = None

    def do_GET(self):  # noqa: N802 (stdlib naming)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.parse_qs(parsed.query)
        if "code" in qs:
            _CallbackHandler.code = qs["code"][0]
            _CallbackHandler.state = qs.get("state", [None])[0]
            body = b"<h2>WHOOP authorization complete.</h2><p>You can close this tab.</p>"
        else:
            _CallbackHandler.error = qs.get("error", ["unknown_error"])[0]
            body = b"<h2>Authorization failed.</h2><p>Check the terminal.</p>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence default request logging
        pass


def _run_local_server(timeout=180):
    _CallbackHandler.code = None
    _CallbackHandler.error = None
    _CallbackHandler.state = None
    server = HTTPServer(("localhost", REDIRECT_PORT), _CallbackHandler)
    server.timeout = 1
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            server.handle_request()
            if _CallbackHandler.code or _CallbackHandler.error:
                break
    finally:
        server.server_close()
    if _CallbackHandler.error:
        raise RuntimeError(f"Authorization failed: {_CallbackHandler.error}")
    return _CallbackHandler.code, _CallbackHandler.state


def _prompt_for_code(url):
    print("\nAutomatic browser flow unavailable — manual mode.")
    print("\n1. Open this URL in any browser and authorize:\n")
    print("   " + url)
    print("\n2. After approving, your browser is redirected to a localhost URL")
    print("   that probably shows an error page (nothing is listening). That's")
    print("   fine — copy the FULL address bar URL (it contains ?code=...).\n")
    raw = input("Paste the full redirect URL (or just the code): ").strip()
    if "code=" in raw:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query)
        return qs.get("code", [""])[0]
    return raw


def login(manual=False):
    """Run the OAuth login flow and persist the token bundle."""
    state = os.urandom(16).hex()
    url = _build_authorize_url(state)

    code = None
    if not manual:
        print("Opening browser for WHOOP authorization...")
        print("(If nothing opens, re-run with --manual)\n")
        try:
            webbrowser.open(url)
            code, returned_state = _run_local_server()
            if returned_state and returned_state != state:
                raise RuntimeError("State mismatch — possible CSRF, aborting.")
        except OSError as exc:
            # e.g. port already in use — fall back to manual
            print(f"Local callback server error ({exc}); falling back to manual.")
            code = None

    if not code:
        code = _prompt_for_code(url)

    if not code:
        raise RuntimeError("No authorization code received.")

    tok = _exchange_code(code)
    _save_tokens(tok)
    print("\n[OK] Authenticated. Token stored at:")
    print("     " + TOKEN_PATH)


def status():
    """Return a human-readable dict describing the stored token."""
    tok = load_tokens()
    if not tok:
        return {"authenticated": False, "message": "No token. Run: whoop-dl auth login"}
    obtained = tok.get("obtained_at", 0)
    expires_in = tok.get("expires_in", 3600)
    expires_at = obtained + expires_in
    remaining = int(expires_at - time.time())
    return {
        "authenticated": True,
        "token_path": TOKEN_PATH,
        "has_refresh_token": bool(tok.get("refresh_token")),
        "access_token_expired": _is_expired(tok),
        "seconds_until_expiry": remaining,
        "scope": tok.get("scope", SCOPES),
    }
