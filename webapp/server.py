#!/usr/bin/env python3
"""Enki heating webapp — stdlib only, uses the pyenki client.

    python -m pyenki.cli login      # once, to get tokens
    python webapp/server.py         # http://0.0.0.0:8099

Discover radiators, see live temperatures, set target/mode, rename a device, and
program a weekly plan (°C / time / day) applied locally by a scheduler thread.
Keep this host on a trusted network: anyone who reaches it controls the heating.
"""
import json
import os
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pyenki import EnkiClient            # requires `pip install -e .` (or the package)
from pyenki.schedule import desired_temp

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEDULE = os.path.join(HERE, "schedule.json")
INDEX = os.path.join(HERE, "index.html")
PORT = int(os.environ.get("ENKI_WEBAPP_PORT", "8099"))

enki = EnkiClient(os.environ.get("ENKI_SECRET", "~/.config/enki/enki_secret.json"))
_last_desired = {}


def load_schedule():
    try:
        with open(SCHEDULE) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {"enabled": False, "radiators": {}}


def save_schedule(s):
    tmp = SCHEDULE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    os.replace(tmp, SCHEDULE)


def scheduler_loop():
    while True:
        try:
            s = load_schedule()
            if s.get("enabled"):
                for node, rs in s.get("radiators", {}).items():
                    if rs.get("enabled"):
                        d = desired_temp(rs)
                        if d is not None and _last_desired.get(node) != d:
                            enki.set_temp(node, d)
                            _last_desired[node] = d
                            print("[sched] %s -> %s°C" % (node, d), flush=True)
        except Exception:
            traceback.print_exc()
        time.sleep(60)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_GET(self):
        try:
            if self.path in ("/", "/index.html"):
                with open(INDEX, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if self.path == "/api/radiators":
                return self._send(200, self._radiators())
            if self.path == "/api/schedule":
                return self._send(200, load_schedule())
            self._send(404, {"error": "not found"})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": str(e)})

    def do_POST(self):
        try:
            if self.path == "/api/set":
                b = self._json()
                if "temp" in b:
                    enki.set_temp(b["id"], b["temp"]); _last_desired[b["id"]] = float(b["temp"])
                elif "mode" in b:
                    enki.set_mode(b["id"], b["mode"])
                elif "label" in b:
                    enki.rename(b["id"], b["label"])
                return self._send(200, {"ok": True})
            if self.path == "/api/schedule":
                save_schedule(self._json()); _last_desired.clear()
                return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": str(e)})

    def _radiators(self):
        ov = {}
        try:
            for n in enki.overview().nodes:
                ov[n.id] = n
        except Exception:
            traceback.print_exc()
        out = []
        for r in enki.radiators():
            on = ov.get(r.id)
            mode = None
            try:
                mode = enki.current(r.id).mode.value
            except Exception:
                pass
            out.append({
                "id": r.id, "label": r.label or r.id[:6],
                "measured": on.measured if on else None,
                "target": on.target if on else None,
                "mode": mode,
            })
        return out


def main():
    threading.Thread(target=scheduler_loop, daemon=True).start()
    print("Enki webapp on http://0.0.0.0:%d" % PORT, flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()


if __name__ == "__main__":
    main()
