"""Typed models parse real API payload shapes."""
from pyenki import (
    CurrentPolicy,
    HeatingMode,
    Node,
    Overview,
    PolicyOption,
    Schedule,
)
from pyenki.models import Home


def test_home():
    h = Home.from_api({"id": "h1", "label": "Home", "countryId": "FR",
                       "timezone": "Europe/Paris", "userId": "u1"})
    assert (h.id, h.label, h.country_id, h.user_id) == ("h1", "Home", "FR", "u1")


def test_node_radiator_flag():
    rad = Node.from_api({"id": "n1", "label": "TV radiator ",
                         "type": "ZIGBEE", "icon": "heaters_and_pilot_wires",
                         "eui64": "0xAB"})
    assert rad.id == "n1"
    assert rad.label == "TV radiator"       # trimmed
    assert rad.is_radiator is True
    box = Node.from_api({"id": "b", "label": "Enki box", "icon": "gateways"})
    assert box.is_radiator is False


def test_current_policy_manual_and_schedule():
    manual = CurrentPolicy.from_api(
        {"type": "MANUAL",
         "state": {"capabilityId": "change_thermostat_target_temperature",
                   "value": 22.0}})
    assert manual.mode is HeatingMode.MANUAL
    assert manual.value == 22.0
    sched = CurrentPolicy.from_api({"type": "COLLECTIVE_SCHEDULE", "state": None})
    assert sched.mode is HeatingMode.COLLECTIVE_SCHEDULE
    assert sched.value is None


def test_policy_options():
    opts = [PolicyOption.from_api(p) for p in [
        {"type": "FROST_PROTECTION", "enabled": True, "current": False,
         "configuration": None},
        {"type": "INDIVIDUAL_SCHEDULE", "enabled": True, "current": True,
         "configuration": {"scheduleId": "sid"}},
    ]]
    assert opts[0].mode is HeatingMode.FROST_PROTECTION and not opts[0].current
    assert opts[1].current and opts[1].schedule_id == "sid"


def test_overview():
    ov = Overview.from_api({"state": "SCHEDULE", "nodes": [
        {"id": "n1", "label": "radiator ", "states": [
            {"capabilityId": "check_current_temperature", "value": 19.0},
            {"capabilityId": "check_thermostat_target_temperature", "value": 22.0},
            {"capabilityId": "check_window_open_detection", "value": "NO_WINDOW_OPEN"},
        ]},
    ]})
    assert ov.state == "SCHEDULE"
    node = ov.nodes[0]
    assert node.label == "radiator"
    assert node.measured == 19.0 and node.target == 22.0
    assert node.window_open == "NO_WINDOW_OPEN"


def test_schedule():
    s = Schedule.from_api({"id": "sid", "nodeId": "n1", "deviceId": "d1",
                           "type": "CUSTOM", "label": "test schedule"})
    assert (s.id, s.node_id, s.type, s.label) == ("sid", "n1", "CUSTOM", "test schedule")
