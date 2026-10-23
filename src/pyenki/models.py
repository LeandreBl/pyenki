"""Typed objects returned by EnkiClient — no raw dicts leak out of the API.

Each API object is a frozen dataclass with a ``from_api`` parser. The low-level
``EnkiClient.request`` still returns parsed JSON for power users; the typed
helpers build these on top of it.
"""
from dataclasses import dataclass
from typing import List, Optional

from .const import HeatingMode


def _f(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Home:
    id: str
    label: str
    country_id: str = ""
    timezone: str = ""
    user_id: str = ""

    @classmethod
    def from_api(cls, d: dict) -> "Home":
        return cls(
            id=str(d.get("id", "")),
            label=str(d.get("label", "")),
            country_id=str(d.get("countryId", "")),
            timezone=str(d.get("timezone", "")),
            user_id=str(d.get("userId", "")),
        )


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    type: str = ""
    icon: str = ""
    device_id: str = ""
    home_id: str = ""
    parent_id: Optional[str] = None
    eui64: Optional[str] = None
    pairing_state: str = ""

    @property
    def is_radiator(self) -> bool:
        return ("heat" in self.icon or "pilot" in self.icon
                or "radiat" in self.label.lower())

    @classmethod
    def from_api(cls, d: dict) -> "Node":
        return cls(
            id=str(d.get("id", "")),
            label=(d.get("label") or "").strip(),
            type=str(d.get("type", "")),
            icon=str(d.get("icon", "")),
            device_id=str(d.get("deviceId", "")),
            home_id=str(d.get("homeId", "")),
            parent_id=d.get("parentId"),
            eui64=d.get("eui64"),
            pairing_state=str(d.get("pairingState", "")),
        )


@dataclass(frozen=True)
class CurrentPolicy:
    """The active mode of a radiator (GET .../policies/current)."""
    mode: HeatingMode
    capability: Optional[str] = None
    value: Optional[float] = None

    @classmethod
    def from_api(cls, d: dict) -> "CurrentPolicy":
        state = d.get("state") or {}
        return cls(HeatingMode(d["type"]),
                   state.get("capabilityId"), _f(state.get("value")))


@dataclass(frozen=True)
class PolicyOption:
    """One available mode for a radiator (GET .../policies)."""
    mode: HeatingMode
    enabled: bool
    current: bool
    schedule_id: Optional[str] = None

    @classmethod
    def from_api(cls, d: dict) -> "PolicyOption":
        cfg = d.get("configuration") or {}
        return cls(HeatingMode(d["type"]), bool(d.get("enabled")),
                   bool(d.get("current")), cfg.get("scheduleId"))


@dataclass(frozen=True)
class OverviewNode:
    id: str
    label: str
    measured: Optional[float] = None
    target: Optional[float] = None
    occupancy: Optional[str] = None
    window_open: Optional[str] = None

    @classmethod
    def from_api(cls, d: dict) -> "OverviewNode":
        st = {s.get("capabilityId"): s.get("value") for s in d.get("states", [])}
        return cls(
            id=str(d.get("id", "")),
            label=(d.get("label") or "").strip(),
            measured=_f(st.get("check_current_temperature")),
            target=_f(st.get("check_thermostat_target_temperature")),
            occupancy=st.get("check_occupancy"),
            window_open=st.get("check_window_open_detection"),
        )


@dataclass(frozen=True)
class Overview:
    state: str
    nodes: List[OverviewNode]

    @classmethod
    def from_api(cls, d: dict) -> "Overview":
        return cls(str(d.get("state", "")),
                   [OverviewNode.from_api(n) for n in d.get("nodes", [])])


@dataclass(frozen=True)
class Schedule:
    id: str
    node_id: str
    type: str
    label: str
    device_id: str = ""

    @classmethod
    def from_api(cls, d: dict) -> "Schedule":
        return cls(
            id=str(d.get("id", "")),
            node_id=str(d.get("nodeId", "")),
            type=str(d.get("type", "")),
            label=str(d.get("label") or d.get("i18n") or ""),
            device_id=str(d.get("deviceId", "")),
        )
