"""Enki API constants (reverse-engineered from the Android app).

The gateway is uniform: every call is
    {GATEWAY}/api-enki-<service>-prod/v1/<path>
with headers:
    authorization: Bearer <keycloak access token>
    x-gateway-apikey: <per-service key>
    homeid: <your home id>            (required by device/home services)

The per-service gateway keys are app-global (not user secrets), but this repo
does NOT ship them: you extract them from your own Enki app once, into a local
`service_keys.json` (gitignored). See docs/CAPTURE.md and
`python -m pyenki.cli keys`. This keeps the vendor's keys out of the repo and
lets you refresh them if Adeo rotates one (403 "You cannot consume this
service").
"""
import json
import os
from enum import Enum

GATEWAY = "https://enki.api.devportal.adeo.cloud"
KEYCLOAK = ("https://keycloak-prod.iot.leroymerlin.fr"
            "/realms/enki/protocol/openid-connect")
CLIENT_ID = "enki-front"
REDIRECT_URI = "enki://oauth/callback"
UA = "okhttp/5.4.0"

# Identity providers for login: name -> (kc_idp_hint, provider_type).
# "google" is verified; the others are best-effort and need confirmation.
PROVIDERS = {
    "google": ("google", "google"),
    "apple": ("apple", "apple"),
    "lm": (None, None),  # native Leroy Merlin / Adeo account (UNVERIFIED)
}

class HeatingMode(str, Enum):
    """Pilot-wire / thermostat policy types (GET .../nodes/{id}/policies).

    A ``str`` enum, so members serialize to their API value in JSON bodies and
    compare equal to the raw string.
    """
    MANUAL = "MANUAL"
    FROST_PROTECTION = "FROST_PROTECTION"
    INDIVIDUAL_SCHEDULE = "INDIVIDUAL_SCHEDULE"
    COLLECTIVE_SCHEDULE = "COLLECTIVE_SCHEDULE"


class Capability(str, Enum):
    """Node capability ids used in policy/schedule commands."""
    TARGET_TEMPERATURE = "change_thermostat_target_temperature"

# Per-service gateway keys are loaded from a local file, never committed.
SERVICE_KEYS_FILE = os.environ.get(
    "ENKI_SERVICE_KEYS",
    os.path.expanduser("~/.config/enki/service_keys.json"),
)


def load_service_keys():
    """{service_name: gateway_key} from the local, gitignored file (or {})."""
    try:
        with open(SERVICE_KEYS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}
