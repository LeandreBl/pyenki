"""Heating enums: API-value serialization, coercion, rejection."""
import json

from pyenki import Capability, EnkiClient, EnkiError, HeatingMode


def test_str_enum_serializes_to_api_value():
    # equal to the raw API string, and json-serializes to it (bodies stay valid)
    assert HeatingMode.COLLECTIVE_SCHEDULE == "COLLECTIVE_SCHEDULE"
    assert json.dumps({"type": HeatingMode.MANUAL}) == '{"type": "MANUAL"}'
    assert Capability.TARGET_TEMPERATURE == "change_thermostat_target_temperature"


def test_coercion_from_string():
    assert HeatingMode("FROST_PROTECTION") is HeatingMode.FROST_PROTECTION


def test_set_mode_rejects_unknown(tmp_path):
    client = EnkiClient(str(tmp_path / "noexist.json"))  # no network in __init__
    try:
        client.set_mode("node", "BOGUS")  # fails on coercion, before any request
    except EnkiError:
        return
    raise AssertionError("set_mode should reject an unknown mode")
