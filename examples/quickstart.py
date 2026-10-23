"""Minimal pyenki example: list radiators and nudge one up by 0.5 °C.

Prereqs (see docs/CAPTURE.md):
    python -m pyenki.cli keys enki.har
    python -m pyenki.cli login
"""
from pyenki import EnkiClient

enki = EnkiClient()  # ~/.config/enki/enki_secret.json

radiators = enki.radiators()
for r in radiators:
    cur = enki.current(r.id)
    print(f"{r.label:20s} {r.id}  mode={cur.mode.value}")

if radiators:
    r = radiators[0]
    target = enki.current(r.id).value or 19
    enki.set_temp(r.id, target + 0.5)
    print(f"-> {r.label} set to {target + 0.5} °C")
