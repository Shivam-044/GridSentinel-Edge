"""Learns the normal operating values from finished 'normal' runs.

Run it after you have recorded a normal experiment with lamp 2 off for a while and on for a while:
    python -m detection.calibrate
"""
import json
import sqlite3

import pandas as pd

from gateway import settings


def _stats(s):
    return {"i": [float(s.current_a.mean()), float(s.current_a.std())],
            "v": [float(s.bus_v.mean()), float(s.bus_v.std())]}


def main():
    cfg = settings.load()
    con = sqlite3.connect(str(settings.resolve(cfg["gateway"]["db_path"])))
    df = pd.read_sql_query(
        "select t.* from telemetry t join experiments e on e.id = t.experiment_id "
        "where e.scenario = 'normal' and e.ended is not null order by t.arrival_ts", con)
    con.close()
    df = df[df.fw != "simulator"]
    if df.empty:
        raise SystemExit("No finished 'normal' experiment found. Record one from the dashboard first.")

    relay = df[(df.node_id == "B") & df.relay_on.notna()][["arrival_ts", "relay_on"]].rename(columns={"relay_on": "state"})
    a = pd.merge_asof(df[df.node_id == "A"], relay, on="arrival_ts")
    b = df[df.node_id == "B"].assign(state=lambda d: d.relay_on)

    nodes = {}
    for name, d in (("A", a), ("B", b)):
        d = d.dropna(subset=["state"])
        nodes[name] = {label: _stats(d[d.state == value]) for value, label in ((0, "off"), (1, "on"))
                       if len(d[d.state == value]) >= 20}
    lamp1 = a[a.state == 0]
    if lamp1.empty:
        raise SystemExit("The normal run needs some time with lamp 2 switched off, to measure lamp 1 alone.")

    out = {"base_current_a": float(lamp1.current_a.mean()), "nodes": nodes, "samples": int(len(df))}
    both = a[a.state == 1]
    if len(both) >= 20:                      # feeder with lamp 2 on, minus lamp 1 alone
        out["lamp2_current_a"] = float(both.current_a.mean() - lamp1.current_a.mean())
    path = settings.resolve(cfg["gateway"]["baseline_path"])
    path.write_text(json.dumps(out, indent=2))
    print(f"lamp 1 current {out['base_current_a']:.4f} A, written to {path}")
    if "lamp2_current_a" in out:
        print(f"lamp 2 adds {out['lamp2_current_a']:.4f} A")
    print("restart the gateway to load the new baseline")


if __name__ == "__main__":
    main()
