"""Feeds the gateway with made-up telemetry so the software can be tried without the hardware.

Every message is tagged fw="simulator" and the dashboard shows a "simulated data" badge, so this
data cannot be mistaken for a real measurement. Do not use it for experiments you report.

    python tools/simulate.py --url http://127.0.0.1:8000
"""
import argparse
import random
import time

import requests

LAMP = 0.417   # amps drawn by one 12 V, 5 W lamp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--hz", type=float, default=2.0)
    args = ap.parse_args()

    relay, seq, t0, last_poll = False, 0, time.time(), 0.0
    while True:
        now = time.time()
        seq += 1
        up = int((now - t0) * 1000)
        v = 12.0 + random.gauss(0, 0.01)
        ib = (LAMP if relay else 0.0) + random.gauss(0, 0.002)
        ia = min(ib + LAMP + random.gauss(0, 0.002), 0.8192)   # the INA226 clips at 0.8192 A
        a = {"node_id": "A", "seq": seq, "uptime_ms": up, "bus_v": round(v, 3), "current_a": round(ia, 4),
             "power_w": round(v * ia, 3), "vsense_v": round(v + random.gauss(0, 0.02), 3), "rssi": -55, "fw": "simulator"}
        b = {"node_id": "B", "seq": seq, "uptime_ms": up, "bus_v": round(v, 3), "current_a": round(ib, 4),
             "power_w": round(v * ib, 3), "relay_on": relay, "rssi": -58, "fw": "simulator"}
        try:
            requests.post(f"{args.url}/telemetry", json=a, timeout=1)
            requests.post(f"{args.url}/telemetry", json=b, timeout=1)
            if now - last_poll > 1:
                last_poll = now
                cmd = requests.get(f"{args.url}/command/B", timeout=1).json()
                if cmd["id"]:
                    relay = {"relay_on": True, "relay_off": False}.get(cmd["command"], relay)
                    requests.post(f"{args.url}/command/{cmd['id']}/ack", json={}, timeout=1)
        except requests.RequestException:
            print("gateway not reachable, retrying")
        time.sleep(1 / args.hz)


if __name__ == "__main__":
    main()
