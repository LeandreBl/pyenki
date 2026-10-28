"""Typed objects returned by EnkiClient — no raw dicts leak out of the API.

Each API object is a frozen dataclass with a ``from_api`` parser. The low-level
``EnkiClient.request`` still returns parsed JSON for power users; the typed
helpers build these on top of it.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .const import ControlType, HeatingMode


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
class HomeMode:
    """A schedule mode of the home (Présent / Nuit / Absent / Hors-gel).

    ``end_date`` is only set on the modes the overview reports as current or
    next, where it says when that mode stops (ISO 8601).
    """
    id: str
    label: str
    type: str = ""
    color: str = ""
    offset: Optional[float] = None
    end_date: str = ""

    @property
    def ends_at(self) -> str:
        """``"22:00"`` — the local time ``end_date`` falls on, or ``""``."""
        return self.end_date[11:16] if len(self.end_date) >= 16 else ""

    @classmethod
    def from_api(cls, d: dict) -> "HomeMode":
        name = d.get("name") or {}
        return cls(
            id=str(d.get("id", "")),
            label=str(name.get("label") or name.get("i18n") or "").strip(),
            type=str(d.get("type", "")),
            color=str(d.get("color", "")),
            offset=_f(d.get("offset")),
            end_date=str(d.get("endDate") or ""),
        )


@dataclass(frozen=True)
class Overview:
    """Home heating state plus every radiator, from the one overview call.

    ``state`` is the active ControlType; ``current_mode`` / ``next_mode`` are the
    schedule modes around now, and ``current_schedule`` the named schedule
    driving them (all empty when the home is not on SCHEDULE).
    """
    state: str
    nodes: List[OverviewNode]
    current_mode: Optional[HomeMode] = None
    next_mode: Optional[HomeMode] = None
    current_schedule: Optional["HomeSchedule"] = None

    @classmethod
    def from_api(cls, d: dict) -> "Overview":
        def mode(key):
            raw = d.get(key)
            return HomeMode.from_api(raw) if raw else None
        sched = d.get("currentSchedule")
        return cls(
            state=str(d.get("state", "")),
            nodes=[OverviewNode.from_api(n) for n in d.get("nodes", [])],
            current_mode=mode("currentMode"),
            next_mode=mode("nextMode"),
            current_schedule=HomeSchedule.from_api(sched) if sched else None,
        )


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


@dataclass(frozen=True)
class TimeSlot:
    """One slot of a home schedule's week: a mode running from ``start``.

    Enki's slots tile the day, so ``end`` is the next slot's start and the last
    one ends ``"00:00"``. ``to_api`` is what the timeslots PUT expects back.
    """
    start: str
    mode_id: str
    end: str = "00:00"

    @classmethod
    def from_api(cls, d: dict) -> "TimeSlot":
        # the schedule detail gives modeId, the overview nests it under mode.id
        mode_id = d.get("modeId") or (d.get("mode") or {}).get("id") or ""
        return cls(start=str(d.get("startTime") or "00:00"),
                   mode_id=str(mode_id),
                   end=str(d.get("endTime") or "00:00"))

    def to_api(self) -> dict:
        return {"startTime": self.start, "endTime": self.end,
                "modeId": self.mode_id}


@dataclass(frozen=True)
class HomeSchedule:
    """A named schedule of the home (Enki's "Planning" screen).

    Distinct from :class:`Schedule`, which is a per-radiator schedule. ``i18n``
    is kept next to ``label`` because Enki's own default schedule is identified
    by its translation key, not by a stable label.
    """
    id: str
    label: str = ""
    i18n: str = ""
    type: str = ""
    timeslots: Dict[str, List[TimeSlot]] = field(default_factory=dict)

    @property
    def is_default(self) -> bool:
        """Enki's default schedule, however this account happens to name it."""
        return (self.type == "DEFAULT"
                or self.i18n in ("common.heating_default_schedule",
                                 "schedule.default_schedule")
                or self.label.strip().casefold() == "default")

    @classmethod
    def from_api(cls, d: dict) -> "HomeSchedule":
        name = d.get("name") or {}
        slots = d.get("timeslots") or {}
        return cls(
            id=str(d.get("id", "")),
            label=str(name.get("label") or "").strip(),
            i18n=str(name.get("i18n") or ""),
            type=str(d.get("type", "")),
            timeslots={
                day: sorted((TimeSlot.from_api(s) for s in (entries or [])),
                            key=lambda s: s.start)
                for day, entries in slots.items()
            },
        )
