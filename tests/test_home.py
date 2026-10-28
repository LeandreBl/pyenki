"""Home-level control: validation guards, store injection, week round-trip."""
import pytest

from pyenki import (
    ControlType,
    EnkiClient,
    EnkiError,
    HomeMode,
    HomeSchedule,
    Overview,
    TimeSlot,
    WEEK,
)


class Store:
    """The minimal token store EnkiClient accepts: a dict plus save()."""

    def __init__(self, data=None):
        self.data = dict(data or {})
        self.saves = 0

    def save(self):
        self.saves += 1


def client(**kw):
    # no network and no file touched: __init__ only reads the store
    return EnkiClient(store=Store({"home_id": "h1"}), keys={}, **kw)


def test_injected_store_replaces_the_file():
    store = Store({"home_id": "h1"})
    c = EnkiClient(store=store, keys={})
    assert c.store is store
    assert c.home_id == "h1"          # served from the store, no call
    assert c.keys == {}


def test_set_home_control_rejects_unknown_type():
    c = client()
    with pytest.raises(EnkiError):
        c.set_home_control("PLANNING")       # not a ControlType


def test_schedule_control_needs_a_schedule_id():
    c = client()
    with pytest.raises(EnkiError):
        c.set_home_control(ControlType.SCHEDULE)
    with pytest.raises(EnkiError):
        c.select_schedule("")


def test_set_timeslots_refuses_a_partial_week():
    c = client()
    slot = [TimeSlot(start="00:00", mode_id="m")]
    with pytest.raises(EnkiError) as e:
        c.set_timeslots("sid", {"MONDAY": slot})
    assert "TUESDAY" in str(e.value)     # names what is missing


def test_timeslot_round_trip():
    raw = {"startTime": "09:00", "endTime": "00:00", "modeId": "day"}
    assert TimeSlot.from_api(raw).to_api() == raw
    # the overview nests the mode instead of giving modeId
    assert TimeSlot.from_api({"startTime": "07:00", "mode": {"id": "night"}}).mode_id == "night"


def test_home_schedule_sorts_slots_and_spots_the_default():
    s = HomeSchedule.from_api({
        "id": "s1", "type": "DEFAULT", "name": {"label": "Semaine"},
        "timeslots": {"MONDAY": [{"startTime": "09:00", "modeId": "day"},
                                 {"startTime": "00:00", "modeId": "night"}]},
    })
    assert [t.start for t in s.timeslots["MONDAY"]] == ["00:00", "09:00"]
    assert s.is_default
    # identified by translation key when the label is localized
    assert HomeSchedule.from_api(
        {"id": "s2", "name": {"i18n": "common.heating_default_schedule"}}).is_default
    assert not HomeSchedule.from_api({"id": "s3", "name": {"label": "Vacances"}}).is_default


def test_overview_keeps_the_home_state():
    ov = Overview.from_api({
        "state": "SCHEDULE",
        "currentMode": {"id": "m1", "name": {"label": "Présent"}},
        "nextMode": {"id": "m2", "name": {"label": "Nuit"}},
        "currentSchedule": {"id": "s1", "name": {"label": "Semaine"}},
        "nodes": [{"id": "n1", "label": "TV", "states": [
            {"capabilityId": "check_current_temperature", "value": 20.4}]}],
    })
    assert ov.state == "SCHEDULE"
    assert ov.current_mode.label == "Présent" and ov.next_mode.id == "m2"
    assert ov.current_schedule.id == "s1"
    assert ov.nodes[0].measured == 20.4
    # absent home state degrades to None rather than raising
    assert Overview.from_api({"state": "OFF", "nodes": []}).current_mode is None


def test_home_mode_exposes_when_it_ends():
    m = HomeMode.from_api({"id": "m1", "name": {"label": "Présent"},
                           "endDate": "2026-10-28T22:00:00Z"})
    assert m.label == "Présent" and m.ends_at == "22:00"
    # the mode list (not the overview) carries no endDate
    assert HomeMode.from_api({"id": "m2", "name": {"label": "Nuit"}}).ends_at == ""


def test_week_covers_seven_days_in_weekday_order():
    assert len(WEEK) == 7 and WEEK[0] == "MONDAY" and WEEK[6] == "SUNDAY"
