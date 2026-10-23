# enki-api

The reverse engineered Enki API to use it in your home assistant.

Unofficial Python client + CLI + demo webapp for Leroy Merlin **Enki** connected
radiators (and the rest of the Enki cloud). Not affiliated with Leroy Merlin /
Adeo — the API is undocumented and may change. Pure standard library, no deps.

## What it does

- Log in with your Enki account (one browser step), then refresh tokens forever.
- Discover your radiators, read live temperature / target / mode.
- Set target temperature, switch modes (manual, frost protection, schedule).
- Rename a device, toggle window-open detection, read/create native schedules.
- A tiny web UI, and a local weekly programmer (°C / time / day).
- A generic `request()` that reaches **any** Enki service (given its key).

See **[docs/API.md](docs/API.md)** for the full endpoint reference and
**[docs/CAPTURE.md](docs/CAPTURE.md)** to get your tokens and service keys.

## Install

```sh
pip install git+https://github.com/LeandreBl/pyenki.git   # or: pip install -e . in a clone
```

Standard src-layout package (`src/pyenki/`), standard library only, tests under
`tests/` (`pytest`).

## Quickstart

```sh
python -m pyenki.cli keys enki.har          # 1. extract service keys (once)
python -m pyenki.cli login                  # 2. browser login (once)
python -m pyenki.cli radiators              # 3. list your radiators
python -m pyenki.cli temp <nodeId> 21.5     #    set 21.5 °C
python -m pyenki.cli mode <nodeId> FROST_PROTECTION
python -m pyenki.cli rename <nodeId> "Bedroom radiator"
python webapp/server.py                     # http://localhost:8099
```

## Library

```python
from pyenki import EnkiClient, HeatingMode

enki = EnkiClient()                 # tokens: ~/.config/enki/enki_secret.json
for r in enki.radiators():          # -> list[Node]
    print(r.label, enki.current(r.id).mode)   # -> CurrentPolicy
enki.set_temp(r.id, 20.0)
enki.set_mode(r.id, HeatingMode.COLLECTIVE_SCHEDULE)
enki.rename(r.id, "Salon")

# native weekly schedule (Enki's own programming)
enki.create_schedule(r["id"], {
    "MONDAY":  [("06:00", 20), ("08:00", 17), ("18:00", 21), ("22:00", 16)],
    "TUESDAY": [("06:00", 20), ("22:00", 16)],
}, label="week")

# any other service:
enki.request("GET", "api-enki-lighting-prod", "…")
```

## Config / files (all gitignored)

| File | What |
|---|---|
| `~/.config/enki/enki_secret.json` | tokens + home id (override with `ENKI_SECRET`) |
| `service_keys.json` | per-service gateway keys (override with `ENKI_SERVICE_KEYS`) |
| `webapp/schedule.json` | the local weekly plan |

## Security

Your `enki_secret.json` holds live tokens — treat it as a password. The webapp
has no auth; keep it on a trusted network. Service keys are app-global, not your
secret, but this repo does not redistribute Adeo's keys — you extract your own.

## License

GPL-3.0 (see [LICENSE](LICENSE)).
