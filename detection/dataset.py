"""Builds labelled windows from finished experiments, for training and evaluation."""
import sqlite3

import numpy as np
import pandas as pd

from . import decision, features

STEP_S = 2.0


def _rows(df):
    return [{
        "ts": r["arrival_ts"],
        "seq_flag": r["seq_flag"] if isinstance(r["seq_flag"], str) else None,
        "same": bool(r["same"]),
        "bus_v": r["bus_v"], "current_a": r["current_a"], "power_w": r["power_w"],
        "vsense_v": None if pd.isna(r["vsense_v"]) else r["vsense_v"],
        "relay_on": None if pd.isna(r["relay_on"]) else bool(r["relay_on"]),
    } for r in df.to_dict("records")]


def build(db_path, cfg, base_current=None):
    """Returns feature vectors X, labels y and the experiment id of every window."""
    con = sqlite3.connect(str(db_path))
    exps = pd.read_sql_query("select * from experiments where ended is not null order by id", con)
    w = cfg["gateway"]["window_s"]
    X, y, groups = [], [], []
    for e in exps.itertuples():
        tel = pd.read_sql_query("select * from telemetry where experiment_id = ? order by arrival_ts",
                                con, params=(int(e.id),))
        if tel.empty or (tel.fw == "simulator").any():
            continue                       # simulated data never goes into training
        a, b = (_rows(tel[tel.node_id == n]) for n in ("A", "B"))
        label = decision.SCENARIO_LABEL[e.scenario]
        t = tel.arrival_ts.min() + w
        while t <= e.ended:
            ra = [r for r in a if t - w < r["ts"] <= t]
            rb = [r for r in b if t - w < r["ts"] <= t]
            X.append(features.vector(features.window(ra, rb, base_current)))
            y.append(label)
            groups.append(int(e.id))
            t += STEP_S
    con.close()
    return np.array(X), np.array(y), np.array(groups)
