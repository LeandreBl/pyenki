# Enki API — reverse-engineered reference

Unofficial notes on the Leroy Merlin **Enki** smart-home cloud API, from the
Android app (`com.leroymerlin.enki`). Not affiliated with Leroy Merlin / Adeo.
Endpoints and payloads can change without notice.

## Architecture

Enki is **cloud only** — radiators are not controlled on the LAN. The phone talks
to an Apigee gateway that fans out to per-domain microservices; device state is
pushed over MQTT, commands go over REST.

```
app ──HTTPS──> enki.api.devportal.adeo.cloud/api-enki-<service>-prod/v1/<path>
         auth: Keycloak (keycloak-prod.iot.leroymerlin.fr, realm "enki")
```

No static certificate pinning, which is what makes capture possible (see
[CAPTURE.md](CAPTURE.md)).

## Authentication — Keycloak OIDC

- Public client **`enki-front`**, flow **authorization_code** (no PKCE),
  federated login (Google / Apple / Leroy-Merlin) via `kc_idp_hint`.
- `redirect_uri = enki://oauth/callback`, `scope = profile email`.
- Token endpoint: `…/realms/enki/protocol/openid-connect/token`.

Login (one time), token exchange:

```
POST /token
grant_type=authorization_code&client_id=enki-front&code=<code>
    &redirect_uri=enki://oauth/callback&provider_type=google
```
`provider_type` matches the IdP used (`google` verified; others vary).

Refresh (silent, forever — the refresh token **rotates** each call, ~14-day life
reset on use):

```
POST /token
grant_type=refresh_token&client_id=enki-front&refresh_token=<token>
```
→ `{ access_token (2h), refresh_token (new), expires_in, refresh_expires_in }`.

## Gateway request shape

Every service call carries:

| Header | Value |
|---|---|
| `authorization` | `Bearer <access_token>` |
| `x-gateway-apikey` | per-service key (app-global; see [CAPTURE.md](CAPTURE.md)) |
| `homeid` | your home id (required by device/home services; 400 without it) |
| `content-type` | `application/json; charset=utf-8` |

A wrong/missing service key → `403 {"message":"You cannot consume this service"}`.
Each `api-enki-<service>-prod` product has its **own** key.

## Endpoints (verified)

### Home & devices
| Method | Path | Notes |
|---|---|---|
| GET | `api-enki-home-prod/v1/homes` | `{items:[{id,label,countryId,timezone,…}]}` → your `home_id` |
| GET | `api-enki-node-agg-prod/v1/nodes?homeId={h}` | all devices (`{items:[…]}`); add `pairing_state` filtering client-side |
| GET | `api-enki-node-agg-prod/v1/nodes/{nodeId}` | device detail (type, icon, eui64, label, parentId) |
| PATCH | `api-enki-zigbee-prod/v1/nodes/{nodeId}` | **rename**: body `{"label":"New name"}` |

### Heating — read
| Method | Path | Notes |
|---|---|---|
| GET | `api-enki-mobile-heating-bff-prod/v1/heating/homes/{h}/overview` | all radiators + states (`check_current_temperature`, `check_thermostat_target_temperature`, …) + home mode + current schedule |
| GET | `api-enki-heating-controller-prod/v1/nodes/{nodeId}/policies/current` | active mode `{type, state}` |
| GET | `api-enki-heating-controller-prod/v1/nodes/{nodeId}/policies` | available modes & which is active |

### Heating — control
| Method | Path | Body |
|---|---|---|
| POST | `api-enki-heating-controller-prod/v1/nodes/{nodeId}/policies` | switch mode: `{"type":"FROST_PROTECTION\|MANUAL\|INDIVIDUAL_SCHEDULE\|COLLECTIVE_SCHEDULE","capabilityId":null,"value":null}` |
| POST | `…/nodes/{nodeId}/policies` | set target: `{"type":"MANUAL","capabilityId":"change_thermostat_target_temperature","value":21.5}` |
| POST | `api-enki-thermostat-prod/v1/heating/{nodeId}/change-window-open-detection-mode` | `{"value":"ENABLED"\|"DISABLED"}` |

Writes answer `202`/`204` with an empty body. Other `heating/{nodeId}/change-*`
and `check-*` routes exist on `thermostat-prod` (offset temperature, child lock,
preheating, hysteresis, pilot-wire state…) — bodies not all captured yet.

### Native weekly schedule (programming)
| Method | Path | Notes |
|---|---|---|
| GET | `api-enki-schedule-prod/v1/schedules?nodeId={n}&types=CUSTOM&types=DEFAULT&types=PEAK_OFF_PEAK` | schedules for a device |
| GET | `api-enki-schedule-prod/v1/devices/{deviceId}/default-schedule` | the default schedule |
| POST | `api-enki-schedule-prod/v1/schedules` | create (body below) |

Create body:
```json
{
  "label": "My schedule",
  "homeId": "<home>",
  "nodeId": "<node>",
  "timeslots": {
    "MONDAY": [
      {"startTime":"00:00:00","commands":[
        {"type":"COMMAND","nodeId":"<node>",
         "capabilityId":"change_thermostat_target_temperature","value":17.0}]},
      {"startTime":"06:00:00","commands":[{ "…":"…","value":20.0}]}
    ],
    "TUESDAY": [ … ]
  }
}
```
Days are full upper-case English names; `startTime` is `HH:MM:SS`.

### Sensors
| Method | Path | Body |
|---|---|---|
| POST | `api-enki-presence-detector-prod/v1/sensors/{sensorId}/change-occupancy-mode` | `{"value":"ENABLED"\|"DISABLED"}` |

## Device model

Radiators are `type: "ZIGBEE"`, `icon: "heaters_and_pilot_wires"`, attached to a
gateway node (`type: "GW_CONNECT"`, "Box enki"). Pilot-wire heating uses the
`policies` model (MANUAL + target temperature, or FROST_PROTECTION / schedules).

## Service catalogue

The app uses ~70 `api-enki-*-prod` services (lighting, rolling shutters, cameras,
scenarios, energy, Netatmo/Somfy/Tahoma bridges, …). All share the gateway shape
above; only their per-service key differs. Capture the key for a service the
first time you call it (see [CAPTURE.md](CAPTURE.md)).

## Signature / integrity

APK signature verification is not performed by these tools; this is interop, not
an endorsement. Treat your tokens as passwords.
