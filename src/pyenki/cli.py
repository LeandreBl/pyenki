"""pyenki command line.

    python -m pyenki.cli login [--provider google]
    python -m pyenki.cli homes
    python -m pyenki.cli nodes | radiators | overview
    python -m pyenki.cli current  <nodeId>
    python -m pyenki.cli modes    <nodeId>
    python -m pyenki.cli temp     <nodeId> 21.5
    python -m pyenki.cli mode     <nodeId> FROST_PROTECTION
    python -m pyenki.cli rename   <nodeId> "Bedroom radiator"
    python -m pyenki.cli window   <nodeId> on|off
    python -m pyenki.cli schedules
    python -m pyenki.cli keys <capture.har>     # extract service keys locally
"""
import argparse
import json
import sys

from .client import EnkiClient, DEFAULT_SECRET
from .const import HeatingMode


def _dump(x):
    print(json.dumps(x, ensure_ascii=False, indent=2))


def extract_keys_from_har(har_path, out_path):
    """Harvest {service: x-gateway-apikey} from a HAR capture into out_path."""
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)
    keys = {}
    for entry in har.get("log", {}).get("entries", []):
        req = entry.get("request", {})
        url = req.get("url", "")
        if "devportal.adeo.cloud" not in url or "/v1/" not in url:
            continue
        service = url.split("//", 1)[-1].split("/")[1]
        for h in req.get("headers", []):
            if h.get("name", "").lower() == "x-gateway-apikey":
                keys[service] = h.get("value")
    keys = dict(sorted(keys.items()))
    with open(out_path, "w") as f:
        json.dump(keys, f, indent=2)
    print("wrote %d service keys -> %s" % (len(keys), out_path))


def main(argv=None):
    p = argparse.ArgumentParser(prog="pyenki")
    p.add_argument("--secret", default=DEFAULT_SECRET, help="token store path")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("login"); sp.add_argument("--provider", default="google")
    sub.add_parser("homes"); sub.add_parser("nodes")
    sub.add_parser("radiators"); sub.add_parser("overview")
    s = sub.add_parser("schedules"); s.add_argument("node")
    for name in ("current", "modes"):
        s = sub.add_parser(name); s.add_argument("node")
    s = sub.add_parser("temp"); s.add_argument("node"); s.add_argument("celsius", type=float)
    s = sub.add_parser("mode"); s.add_argument("node")
    s.add_argument("mode", choices=[m.value for m in HeatingMode])
    s = sub.add_parser("rename"); s.add_argument("node"); s.add_argument("label")
    s = sub.add_parser("window"); s.add_argument("node"); s.add_argument("state", choices=["on", "off"])
    s = sub.add_parser("keys"); s.add_argument("har"); s.add_argument("--out", default="service_keys.json")

    args = p.parse_args(argv)

    if args.cmd == "keys":
        return extract_keys_from_har(args.har, args.out)

    c = EnkiClient(args.secret)
    if args.cmd == "login":
        from . import auth
        auth.login(c.store, provider=args.provider)
    elif args.cmd == "homes":
        _dump(c.homes())
    elif args.cmd == "nodes":
        _dump(c.nodes())
    elif args.cmd == "radiators":
        _dump(c.radiators())
    elif args.cmd == "overview":
        _dump(c.overview())
    elif args.cmd == "schedules":
        _dump(c.schedules(args.node))
    elif args.cmd == "current":
        _dump(c.current(args.node))
    elif args.cmd == "modes":
        _dump(c.policies(args.node))
    elif args.cmd == "temp":
        c.set_temp(args.node, args.celsius); print("ok: %s -> %s°C" % (args.node, args.celsius))
    elif args.cmd == "mode":
        c.set_mode(args.node, args.mode); print("ok: %s -> %s" % (args.node, args.mode))
    elif args.cmd == "rename":
        c.rename(args.node, args.label); print("ok: renamed -> %s" % args.label)
    elif args.cmd == "window":
        c.window_open_detection(args.node, args.state == "on"); print("ok")


if __name__ == "__main__":
    sys.exit(main())
