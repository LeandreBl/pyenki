"""Service-key extraction from a HAR capture (pyenki keys)."""
import json

from pyenki.cli import extract_keys_from_har


def test_extract_keys_from_har(tmp_path):
    har = {
        "log": {
            "entries": [
                {"request": {
                    "url": "https://enki.api.devportal.adeo.cloud/api-enki-heating-controller-prod/v1/nodes/x/policies",
                    "headers": [
                        {"name": "x-gateway-apikey", "value": "KEY_HEATING"},
                        {"name": "authorization", "value": "Bearer z"},
                    ],
                }},
                {"request": {
                    "url": "https://enki.api.devportal.adeo.cloud/api-enki-node-agg-prod/v1/nodes",
                    "headers": [{"name": "X-Gateway-APIKey", "value": "KEY_NODE"}],
                }},
                {"request": {  # unrelated host: ignored
                    "url": "https://example.com/v1/x",
                    "headers": [{"name": "x-gateway-apikey", "value": "NOPE"}],
                }},
            ]
        }
    }
    har_path = tmp_path / "cap.har"
    out_path = tmp_path / "service_keys.json"
    har_path.write_text(json.dumps(har))

    extract_keys_from_har(str(har_path), str(out_path))

    keys = json.loads(out_path.read_text())
    assert keys == {
        "api-enki-heating-controller-prod": "KEY_HEATING",
        "api-enki-node-agg-prod": "KEY_NODE",
    }
