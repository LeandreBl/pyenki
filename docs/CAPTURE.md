# Getting your tokens and service keys

`pyenki` needs two local, **gitignored** things:

1. `enki_secret.json` — your account tokens (from a one-time browser login).
2. `service_keys.json` — the per-service gateway keys (app-global, not secret,
   but not shipped in this repo — you extract them once).

## 1. Log in (tokens)

```sh
python -m pyenki.cli login            # defaults to --provider google
```
Open the printed URL, sign in with your Enki (Leroy Merlin) account, then paste
back the `enki://oauth/callback?code=...` URL your browser ends up on. Tokens are
written to `~/.config/enki/enki_secret.json` and refreshed automatically after
that. `--provider apple` / `--provider lm` exist but only `google` is verified.

## 2. Service keys

Each `api-enki-<service>-prod` service has its own `x-gateway-apikey`. Extract
them from a capture of your own app (they are the same for every user, but this
repo does not redistribute Adeo's keys).

**From a HAR** (easiest — HTTP Toolkit, mitmweb "Export", or Chrome DevTools on a
proxied session export a `.har`):

```sh
python -m pyenki.cli keys enki.har --out service_keys.json
```

This writes `{ "api-enki-heating-controller-prod": "…", … }`. You only need the
services you use (heating needs `heating-controller`, `mobile-heating-bff`,
`node-agg`, `home`, `schedule`, `thermostat`, `zigbee`). Point the client at the
file with `ENKI_SERVICE_KEYS=/path/service_keys.json` if it isn't in the repo
root.

### How to capture

Android apps (targetSdk ≥ 24) don't trust user CA certs by default, and Enki has
no web app, so you capture on a **rooted device or emulator**:

1. A Google-APIs (non-PlayStore) Android emulator image is rootable:
   `adb root`, mount the mitmproxy CA into the system/APEX cert store, restart
   the framework.
2. Point the device proxy at mitmproxy (`adb reverse tcp:8080 tcp:8080`,
   `settings put global http_proxy 127.0.0.1:8080`).
3. Open Enki, use the features you want, and save the flows. There is **no cert
   pinning**, so TLS decrypts cleanly.

Then export to HAR and run the `keys` command above. New endpoints you exercise
show up in the capture — that's how this reference grows.
