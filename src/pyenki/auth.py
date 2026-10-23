"""Keycloak OAuth for Enki: one browser login, then silent refresh forever.

Enki uses a plain OAuth2 authorization-code flow (no PKCE) on the public client
`enki-front`, federated through Google/Apple/Leroy-Merlin. The redirect is a
custom scheme (`enki://oauth/callback`) that no desktop app can catch, so login
is: open the URL, sign in, then paste the `enki://...?code=...` URL the browser
ends up on. The returned refresh token rotates on every use (~14-day life, reset
each refresh), so as long as something refreshes within 14 days it runs forever.
"""
import json
import os
import time
import urllib.parse
import urllib.request
import webbrowser

from .const import KEYCLOAK, CLIENT_ID, REDIRECT_URI, PROVIDERS

TOKEN_URL = KEYCLOAK + "/token"
AUTH_URL = KEYCLOAK + "/auth"


class Store:
    """Token + home_id persisted to a JSON file (chmod 600)."""

    def __init__(self, path):
        self.path = os.path.expanduser(path)
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path) as f:
                return json.load(f)
        except (FileNotFoundError, ValueError):
            return {}

    def save(self):
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @property
    def logged_in(self):
        return bool(self.data.get("refresh_token"))


def _post_token(params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def authorize_url(idp_hint="google"):
    q = {"client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI,
         "response_type": "code", "scope": "profile email"}
    if idp_hint:
        q["kc_idp_hint"] = idp_hint
    return AUTH_URL + "?" + urllib.parse.urlencode(q)


def exchange_code(code, provider_type="google"):
    params = {"grant_type": "authorization_code", "client_id": CLIENT_ID,
              "code": code, "redirect_uri": REDIRECT_URI}
    if provider_type:
        params["provider_type"] = provider_type
    return _post_token(params)


def refresh(refresh_token):
    return _post_token({"grant_type": "refresh_token", "client_id": CLIENT_ID,
                        "refresh_token": refresh_token})


def _apply(store, tok):
    store.data["refresh_token"] = tok["refresh_token"]  # rotates — must persist
    store.data["access_token"] = tok["access_token"]
    store.data["access_expiry"] = int(time.time()) + int(tok["expires_in"]) - 60
    store.save()


def access_token(store):
    """A valid bearer, refreshing (and persisting the rotated token) if stale."""
    if time.time() >= store.data.get("access_expiry", 0):
        _apply(store, refresh(store.data["refresh_token"]))
    return store.data["access_token"]


def login(store, provider="google", open_browser=True, read=input):
    """Interactive browser login; writes tokens into `store`."""
    hint, ptype = PROVIDERS.get(provider, (provider, provider))
    url = authorize_url(hint)
    print("1) Open this URL and sign in with your Enki account:\n   " + url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    print("2) The browser will try to open  enki://oauth/callback?code=...\n"
          "   (it can't open an app — that's fine). Copy that FULL url from the\n"
          "   address bar and paste it below.")
    pasted = read("Paste redirect url: ").strip()
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query)
    code = qs.get("code", [None])[0]
    if not code:
        raise SystemExit("No ?code= found in the pasted url.")
    _apply(store, exchange_code(code, ptype))
    print("Logged in — tokens saved to " + store.path)
