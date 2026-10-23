"""EnkiClient — call any Enki cloud service, with typed helpers for the verified
heating / schedule / device operations.

Transport is uniform, so `request(method, service, path, body)` reaches ANY
service (given its gateway key in service_keys.json); the named methods below are
the ones captured and confirmed against a real account.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid

from . import auth
from .const import GATEWAY, UA, Capability, HeatingMode, load_service_keys
from .models import (
    CurrentPolicy,
    Home,
    Node,
    Overview,
    PolicyOption,
    Schedule,
)

DEFAULT_SECRET = "~/.config/enki/enki_secret.json"


class EnkiError(Exception):
    pass


class EnkiClient:
    def __init__(self, secret_path=DEFAULT_SECRET):
        self.store = auth.Store(secret_path)
        self.keys = load_service_keys()

    # -- transport -------------------------------------------------------------

    def request(self, method, service, path, body=None, with_home=True):
        """Call GATEWAY/<service>/v1/<path>. `service` e.g. 'api-enki-home-prod'."""
        key = self.keys.get(service)
        if not key:
            raise EnkiError("no gateway key for %r (run: pyenki keys)" % service)
        url = "%s/%s/v1/%s" % (GATEWAY, service, path.lstrip("/"))
        headers = {
            "authorization": "Bearer " + auth.access_token(self.store),
            "x-gateway-apikey": key,
            "content-type": "application/json; charset=utf-8",
            "user-agent": UA,
            "x-correlation-id": "PY_" + str(uuid.uuid4()),
        }
        if with_home and self.store.data.get("home_id"):
            headers["homeid"] = self.store.data["home_id"]
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            return self._send(req)
        except urllib.error.HTTPError as e:
            if e.code == 401:  # token expired server-side: refresh once and retry
                auth._apply(self.store, auth.refresh(self.store.data["refresh_token"]))
                req.headers["Authorization"] = "Bearer " + self.store.data["access_token"]
                return self._send(req)
            raise EnkiError("%s %s -> %s %s" % (method, url, e.code, e.read()[:200]))

    @staticmethod
    def _send(req):
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return json.loads(raw) if raw else None  # writes answer 202/204/empty

    @staticmethod
    def _items(raw):
        if isinstance(raw, dict):
            return raw.get("items", [])
        return raw or []

    # -- home / account --------------------------------------------------------

    def homes(self):
        """List[Home] on the account."""
        raw = self.request("GET", "api-enki-home-prod", "homes", with_home=False)
        return [Home.from_api(h) for h in self._items(raw)]

    @property
    def home_id(self):
        hid = self.store.data.get("home_id")
        if hid:
            return hid
        homes = self.homes()
        if not homes:
            raise EnkiError("no home on this account")
        hid = homes[0].id
        self.store.data["home_id"] = hid
        self.store.save()
        return hid

    # -- devices ---------------------------------------------------------------

    def nodes(self):
        """Paired devices (List[Node], un-paired filtered out)."""
        q = urllib.parse.urlencode({"homeId": self.home_id})
        raw = self.request("GET", "api-enki-node-agg-prod", "nodes?" + q)
        nodes = [Node.from_api(n) for n in self._items(raw)]
        return [n for n in nodes if n.pairing_state in ("", "PAIRING_DONE")]

    def node(self, node_id):
        return Node.from_api(
            self.request("GET", "api-enki-node-agg-prod", "nodes/%s" % node_id))

    def radiators(self):
        """List[Node] limited to heating devices."""
        return [n for n in self.nodes() if n.is_radiator]

    def rename(self, node_id, label):
        """Rename a Zigbee device. PATCH .../zigbee-prod/nodes/{id} {label}."""
        return self.request("PATCH", "api-enki-zigbee-prod", "nodes/%s" % node_id,
                            {"label": label})

    # -- heating ---------------------------------------------------------------

    def overview(self):
        """Overview: home heating state + per-radiator measured/target temps."""
        return Overview.from_api(self.request(
            "GET", "api-enki-mobile-heating-bff-prod",
            "heating/homes/%s/overview" % self.home_id))

    def current(self, node_id):
        """CurrentPolicy: the radiator's active mode (and target, if MANUAL)."""
        return CurrentPolicy.from_api(self.request(
            "GET", "api-enki-heating-controller-prod",
            "nodes/%s/policies/current" % node_id))

    def policies(self, node_id):
        """List[PolicyOption]: modes available for the radiator."""
        raw = self.request("GET", "api-enki-heating-controller-prod",
                           "nodes/%s/policies" % node_id)
        return [PolicyOption.from_api(p) for p in (raw or {}).get("policies", [])]

    def set_policy(self, node_id, type_, capability_id=None, value=None):
        return self.request("POST", "api-enki-heating-controller-prod",
                            "nodes/%s/policies" % node_id,
                            {"type": type_, "capabilityId": capability_id, "value": value})

    def set_temp(self, node_id, celsius):
        return self.set_policy(node_id, HeatingMode.MANUAL,
                               Capability.TARGET_TEMPERATURE, float(celsius))

    def set_mode(self, node_id, mode):
        """`mode` is a HeatingMode (or its string value)."""
        try:
            mode = HeatingMode(mode)
        except ValueError:
            raise EnkiError("mode must be one of %s"
                            % [m.value for m in HeatingMode])
        return self.set_policy(node_id, mode)

    def window_open_detection(self, node_id, enabled):
        return self.request("POST", "api-enki-thermostat-prod",
                            "heating/%s/change-window-open-detection-mode" % node_id,
                            {"value": "ENABLED" if enabled else "DISABLED"})

    # -- native weekly schedule ------------------------------------------------

    def schedules(self, node_id):
        """List[Schedule] for a radiator."""
        q = urllib.parse.urlencode(
            [("nodeId", node_id), ("types", "CUSTOM"), ("types", "DEFAULT"),
             ("types", "PEAK_OFF_PEAK")])
        raw = self.request("GET", "api-enki-schedule-prod", "schedules?" + q)
        return [Schedule.from_api(s) for s in self._items(raw)]

    def default_schedule(self, device_id):
        return Schedule.from_api(self.request(
            "GET", "api-enki-schedule-prod",
            "devices/%s/default-schedule" % device_id))

    def create_schedule(self, node_id, timeslots, label="jarvis"):
        """Create a native Enki weekly schedule for a radiator.

        `timeslots`: {"MONDAY": [("06:00", 20.0), ("22:00", 17.0)], ...}
        (day = full upper-case English name, entry = (HH:MM, °C)).
        """
        payload_slots = {}
        for day, entries in timeslots.items():
            payload_slots[day.upper()] = [{
                "startTime": (t if len(t) == 8 else t + ":00"),
                "commands": [{"type": "COMMAND", "nodeId": node_id,
                              "capabilityId": Capability.TARGET_TEMPERATURE,
                              "value": float(c)}],
            } for (t, c) in entries]
        return self.request("POST", "api-enki-schedule-prod", "schedules", {
            "label": label, "homeId": self.home_id, "nodeId": node_id,
            "timeslots": payload_slots,
        })

    # -- sensors / presence ----------------------------------------------------

    def occupancy_mode(self, sensor_id, enabled):
        return self.request("POST", "api-enki-presence-detector-prod",
                            "sensors/%s/change-occupancy-mode" % sensor_id,
                            {"value": "ENABLED" if enabled else "DISABLED"})
