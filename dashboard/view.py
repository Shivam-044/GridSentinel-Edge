"""Small pure helpers for the dashboard: labels, HTML snippets and chart data. No Streamlit in here."""
import html
from datetime import datetime

import pandas as pd

LABELS = {
    "normal": ("Normal operation", "ok", "Both meters and the telemetry agree."),
    "physical_fault": ("Physical fault", "warn", "The circuit itself changed, and both meters agree on it."),
    "sensor_anomaly": ("Sensor anomaly", "violet", "One reading is sliding away from the other evidence."),
    "cyber_anomaly": ("Data anomaly", "alert", "Reported values disagree with the physical evidence."),
    "replay_stale": ("Replay or stale data", "alert", "Messages repeat, or readings are frozen."),
    "comm_interruption": ("Link lost", "muted", "A node went quiet, or its messages are missing."),
}

SCENARIOS = {
    "Normal operation": "normal",
    "Physical fault (change lamp 2 by hand)": "physical_fault",
    "False data injection": "fdi",
    "Sensor drift": "drift",
    "Replay of old messages": "replay",
    "Communication interruption": "interruption",
}

FIELDS = {"Current (A)": "current_a", "Bus voltage (V)": "bus_v", "Voltage sensor (V)": "vsense_v"}


def fmt(value, digits=2):
    if value is None or (isinstance(value, float) and value != value):
        return "&mdash;"
    return f"{value:.{digits}f}"


def ago(seconds):
    if seconds is None:
        return "never"
    return f"{seconds:.1f} s ago" if seconds < 60 else f"{seconds / 60:.0f} min ago"


def pills(status, running):
    out = []
    if status is None:
        out.append('<span class="pill pill-red"><i></i>Gateway offline</span>')
    else:
        out.append('<span class="pill pill-green"><i></i>Gateway online</span>')
        if status.get("simulated"):
            out.append('<span class="pill pill-amber">Simulated data</span>')
    if running:
        out.append(f'<span class="pill pill-blue">Run: {html.escape(running)}</span>')
    return "".join(out)


def banner(decision):
    title, tone, blurb = LABELS.get(decision["label"], (decision["label"], "muted", ""))
    since = decision.get("since") or 0
    when = f"since {datetime.fromtimestamp(since):%H:%M:%S}" if since and decision["label"] != "normal" else "monitoring"
    seen, chips = set(), []
    for f in decision.get("flags", []):
        text = f"Node {f['node']}: {f['detail']}" if f.get("node") else f["detail"]
        if text not in seen:
            seen.add(text)
            chips.append(f'<span class="chip">{html.escape(text)}</span>')
    return (f'<div class="banner banner-{tone}"><div><div class="banner-k">System state &middot; {when}</div>'
            f'<div class="banner-t">{title}</div><div class="banner-s">{blurb}</div></div>'
            f'<div class="chips">{"".join(chips[:4])}</div></div>')


def metric(key, value, unit=""):
    return (f'<div class="metric"><div class="k">{key}</div>'
            f'<div class="v">{value}<span class="u">{unit}</span></div></div>')


def node_card(title, sub, metrics, age, alive):
    dot = "dot-on" if alive else "dot-off"
    return (f'<div class="card"><div class="card-head"><div><div class="card-t">{title}</div>'
            f'<div class="card-s">{sub}</div></div><div class="seen"><i class="{dot}"></i>{ago(age)}</div></div>'
            f'<div class="metric-grid">{"".join(metrics)}</div></div>')


def node_cards(status, timeout):
    a, b = status["nodes"]["A"], status["nodes"]["B"]
    has_b = status.get("branch_meter", True)
    alive = lambda n: n["age_s"] is not None and n["age_s"] <= timeout
    relay = "on" if b.get("relay_on") else ("off" if b.get("seen") else None)
    ma = [metric("Bus voltage", fmt(a.get("bus_v")), "V"), metric("Current", fmt(a.get("current_a"), 3), "A"),
          metric("Power", fmt(a.get("power_w")), "W"), metric("Voltage sensor", fmt(a.get("vsense_v")), "V")]
    mb = [metric("Bus voltage", fmt(b.get("bus_v")), "V"), metric("Current", fmt(b.get("current_a"), 3), "A"),
          metric("Power", fmt(b.get("power_w")), "W"), metric("Lamp 2", relay if relay else "&mdash;")]
    if not has_b:
        mb = [metric("Branch meter", "none"), metric("Lamp 2", relay if relay else "&mdash;")]
    return (node_card("Node A", "Feeder meter and voltage sensor", ma, a["age_s"], alive(a)),
            node_card("Node B", "Switched branch, relay and display", mb, b["age_s"], alive(b)))


def long_frames(df, base_current, branch_meter=True):
    """Chart-ready frames: current, voltage and the feeder residual."""
    a = df[df.node_id == "A"]
    b = df[df.node_id == "B"]

    def stack(parts):
        return pd.concat([p.assign(series=s, value=v) for p, s, v in parts])[["t", "series", "value"]]

    current = stack([(a, "Feeder (Node A)", a.current_a), (b, "Branch (Node B)", b.current_a)] if branch_meter
                    else [(a, "Feeder (Node A)", a.current_a)])
    sensor = a.dropna(subset=["vsense_v"])
    voltage = stack([(a, "INA226 bus voltage", a.bus_v), (sensor, "Voltage sensor", sensor.vsense_v)])
    resid = pd.DataFrame(columns=["t", "series", "value"])
    if branch_meter and base_current is not None and len(a) and len(b):
        m = pd.merge_asof(a[["t", "current_a"]].sort_values("t"),
                          b[["t", "current_a"]].rename(columns={"current_a": "ib"}).sort_values("t"),
                          on="t", tolerance=pd.Timedelta("1s"), direction="nearest").dropna()
        resid = pd.DataFrame({"t": m.t, "series": "Residual", "value": m.current_a - m.ib - base_current})
    return current, voltage, resid
