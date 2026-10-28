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

### Home-level control ("Control type")

The whole home runs on one *control type*: a named `SCHEDULE`, `MANUAL` (one
mode for everything), `OFF`, or `INDIVIDUAL` (each radiator on its own). Named
schedules carry weekly slots of **modes** (Présent / Nuit / Absent), not °C —
the per-device schedules below carry temperatures instead.

| Method | Path | Notes |
|---|---|---|
| GET | `api-enki-mobile-bff-prod/v1/heating/modes?homeId={h}&extended=true` | the home's schedule modes (`{items:[{id,name:{label,i18n},type,color,offset}]}`) |
| GET | `api-enki-mobile-heating-bff-prod/v1/heating/homes/{h}/schedules` | named schedules, without their weeks |
| GET | `api-enki-mobile-bff-prod/v1/heating/schedules/{scheduleId}?homeId={h}` | one schedule **with** `timeslots` |
| GET | `api-enki-heating-controller-prod/v1/homes/{h}/states` | current control type |
| POST | `api-enki-heating-controller-prod/v1/homes/{h}/states` | set it: `{"type":"SCHEDULE","value":"<scheduleId>"}` (`MANUAL` takes a modeId, `OFF`/`INDIVIDUAL` `null`) |
| PUT | `api-enki-heating-prod/v1/schedules/{scheduleId}/timeslots?homeId={h}` | rewrite the week: `{"name":"…","days":{…}}` |

The `overview` call above already carries the home state, so reading it costs
nothing extra: `state` (the control type) plus `currentMode`, `nextMode` and
`currentSchedule`.

Timeslots of a named schedule tile each day — every slot is a `startTime` plus
the mode running from it, the last one ending `"00:00"`:
```json
{"days": {"MONDAY": [
  {"startTime":"00:00","endTime":"07:00","modeId":"<night>"},
  {"startTime":"07:00","endTime":"00:00","modeId":"<day>"}], "TUESDAY": [...]}}
```
The PUT **replaces all seven days**, so a partial mapping silently wipes the
missing ones; `EnkiClient.set_timeslots` refuses it instead.

Note `api-enki-heating-prod` (the timeslots PUT) is its own service, distinct
from `api-enki-heating-controller-prod`, and needs its own gateway key.

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
