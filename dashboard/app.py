"""GridSentinel Edge dashboard. Run from the project root:  streamlit run dashboard/app.py"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import altair as alt
import pandas as pd
import streamlit as st
from packaging.version import Version

from dashboard import feed, view

st.set_page_config(page_title="GridSentinel Edge", layout="wide", initial_sidebar_state="collapsed")
st.markdown(f"<style>{(Path(__file__).parent / 'style.css').read_text()}</style>", unsafe_allow_html=True)

CFG = feed.CFG
# Streamlit 1.50 replaced **FILL with **FILL
FILL = {"width": "stretch"} if Version(st.__version__) >= Version("1.50") else {"use_container_width": True}
NAVY, MUTED, GRID = "#11212F", "#5B6B7D", "#E8EDF3"
TEAL, ORANGE, RED, GREEN = "#1B8FA8", "#E8952E", "#C6483C", "#2E8B57"
START_CMD = "python -m uvicorn gateway.main:app --host 0.0.0.0 --port 8000"


def empty(title, body):
    st.markdown(f'<div class="empty"><b>{title}</b>{body}</div>', unsafe_allow_html=True)


def line_chart(df, palette, ytitle, band=None):
    base = alt.Chart(df).mark_line(strokeWidth=2.2, interpolate="monotone").encode(
        x=alt.X("t:T", title=None, axis=alt.Axis(format="%H:%M:%S", labelColor=MUTED, tickCount=4, grid=False, domain=False)),
        y=alt.Y("value:Q", title=ytitle, scale=alt.Scale(zero=False, nice=True),
                axis=alt.Axis(labelColor=MUTED, titleColor=MUTED, gridColor=GRID, domain=False, tickCount=5)),
        color=alt.Color("series:N", scale=alt.Scale(domain=list(palette), range=list(palette.values())),
                        legend=alt.Legend(orient="top", title=None, labelColor=NAVY, symbolType="stroke")))
    layers = [base]
    if band:
        layers.append(alt.Chart(pd.DataFrame({"y": [band, -band]}))
                      .mark_rule(color=RED, strokeDash=[5, 4], opacity=0.55).encode(y="y:Q"))
    return alt.layer(*layers).properties(height=210).configure_view(strokeWidth=0).configure(background="transparent")


def chart_card(title, df, palette, ytitle, band=None):
    with st.container(border=True):
        st.markdown(f'<div class="sec">{title}</div>', unsafe_allow_html=True)
        if df.empty:
            st.caption("Waiting for data")
        else:
            st.altair_chart(line_chart(df, palette, ytitle, band), **FILL)


def command(node, name, ok_text, text=""):
    ok, res = feed.send("/command", {"node_id": node, "command": name, "text": text})
    st.toast(ok_text if ok else f"Could not send the command: {res}")


# ---- header -----------------------------------------------------------------------------------
status = feed.status()
running = status["experiment"]["name"] if status and status.get("experiment") else None
proj = CFG["project"]
st.markdown(
    f'<div class="gs-header"><div><div class="gs-eyebrow">Cyber-physical security testbed</div>'
    f'<h1>{proj["name"]}</h1><div class="gs-sub">{proj["title"]}</div></div>'
    f'<div class="pills">{view.pills(status, running)}</div></div>', unsafe_allow_html=True)

tab_live, tab_runs, tab_events, tab_system = st.tabs(["Live", "Experiments", "Events", "System"])


# ---- live -------------------------------------------------------------------------------------
@st.fragment(run_every="2s")
def live():
    s = feed.status()
    if s is None:
        empty("The gateway is not reachable", f"Start it from the project folder with <code>{START_CMD}</code>")
        return
    st.markdown(view.banner(s["decision"]), unsafe_allow_html=True)
    if not any(n["seen"] for n in s["nodes"].values()):
        empty("Waiting for the nodes", "Check that both ESP32 boards are powered, on the same Wi-Fi, and that "
              "<code>GATEWAY_URL</code> in secrets.h points at this laptop.")
        return

    ca, cb = st.columns(2)
    card_a, card_b = view.node_cards(s, CFG["gateway"]["node_timeout_s"])
    ca.markdown(card_a, unsafe_allow_html=True)
    cb.markdown(card_b, unsafe_allow_html=True)
    st.write("")

    df = feed.telemetry(3)
    if not df.empty:
        base = feed.baseline().get("base_current_a")
        current, voltage, resid = view.long_frames(df, base, s.get("branch_meter", True))
        c1, c2, c3 = st.columns(3)
        with c1:
            chart_card("Current", current, {"Feeder (Node A)": TEAL, "Branch (Node B)": ORANGE}, "Amperes")
        with c2:
            chart_card("Voltage", voltage, {"INA226 bus voltage": TEAL, "Voltage sensor": GREEN}, "Volts")
        with c3:
            chart_card("Feeder residual", resid, {"Residual": RED}, "Amperes", CFG["rules"]["resid_tol_a"])
            if not s.get("branch_meter", True):
                st.caption("The residual needs the branch meter.")
            elif base is None:
                st.caption("The residual needs a baseline. See the System tab.")

    st.write("")
    b1, b2, b3, b4, _ = st.columns([1, 1, 1, 1, 3])
    if b1.button("Lamp 2 on", **FILL):
        command("B", "relay_on", "Lamp 2 switching on")
    if b2.button("Lamp 2 off", **FILL):
        command("B", "relay_off", "Lamp 2 switching off")
    if b3.button("Silence buzzer", **FILL):
        command("B", "buzzer_off", "Buzzer silenced")
    if b4.button("Test buzzer", **FILL):
        command("B", "buzzer_on", "Buzzer test sent", "Buzzer test")


with tab_live:
    live()


# ---- experiments --------------------------------------------------------------------------------
with tab_runs:
    left, right = st.columns([2, 3], gap="large")
    with left:
        with st.container(border=True):
            if status is None:
                st.caption("Start the gateway to run experiments.")
            elif running:
                exp = status["experiment"]
                st.markdown('<div class="sec">Run in progress</div>', unsafe_allow_html=True)
                st.markdown(f"**{exp['name']}**  \nScenario: {exp['scenario']}")
                if st.button("Stop run", type="primary"):
                    feed.send("/experiment/stop")
                    st.rerun()
            else:
                st.markdown('<div class="sec">Start a run</div>', unsafe_allow_html=True)
                name = st.text_input("Run name", value=f"run {time.strftime('%H%M')}")
                label = st.selectbox("Scenario", list(view.SCENARIOS))
                scenario = view.SCENARIOS[label]
                node, field, params = "A", "current_a", {}
                if scenario in ("fdi", "drift", "replay", "interruption"):
                    node = st.radio("Node", ["A", "B"], horizontal=True, index=1 if scenario == "interruption" else 0)
                if scenario in ("fdi", "drift"):
                    field = view.FIELDS[st.selectbox("Value to change", list(view.FIELDS))]
                if scenario == "fdi":
                    params = {"factor": st.slider("Scale factor", 0.3, 1.5, 0.6, 0.05),
                              "offset": st.slider("Offset", -2.0, 2.0, 0.0, 0.05)}
                elif scenario == "drift":
                    volts = field != "current_a"
                    params = {"rate_per_min": st.slider("Drift per minute", 0.1, 3.0, 0.5, 0.1) if volts
                              else st.slider("Drift per minute", 0.02, 1.0, 0.1, 0.02)}
                elif scenario == "replay":
                    params = {"depth": st.slider("Messages to replay", 5, 60, 20, 5)}
                if scenario == "physical_fault":
                    st.caption("Change lamp 2 by hand while the run is active. Leave lamp 1 connected, it is the base load.")
                if scenario == "normal":
                    st.caption("Keep lamp 2 off for a while, then switch it on from the Live tab. The baseline is learned from this.")
                if st.button("Start run", type="primary"):
                    ok, res = feed.send("/experiment/start", {"name": name, "scenario": scenario,
                                                              "node": node, "field": field, "params": params})
                    st.toast("Run started" if ok else f"Could not start: {res}")
                    st.rerun()
    with right:
        st.markdown('<div class="sec">Past runs</div>', unsafe_allow_html=True)
        runs = feed.experiments()
        if runs.empty:
            st.caption("No runs yet.")
        else:
            runs["started"] = runs["started"].dt.strftime("%d %b %H:%M:%S")
            runs["state"] = runs["running"].map({True: "running", False: "finished"})
            st.dataframe(runs[["id", "name", "scenario", "started", "samples", "state"]],
                         **FILL, hide_index=True)


# ---- events -------------------------------------------------------------------------------------
with tab_events:
    ev = feed.events()
    if ev.empty:
        empty("No events yet", "An entry is written every time the system state changes.")
    else:
        ev["State"] = ev["label"].map(lambda x: view.LABELS.get(x, (x,))[0])
        shown = ev.assign(Time=ev["time"].dt.strftime("%d %b %H:%M:%S"))[["Time", "State", "source", "response", "scenario"]]
        shown.columns = ["Time", "State", "Decided by", "Response", "Run scenario"]
        pick = st.multiselect("Show", sorted(shown["State"].unique()), default=sorted(shown["State"].unique()))
        st.dataframe(shown[shown["State"].isin(pick)], **FILL, hide_index=True)
        st.download_button("Download events as CSV", ev.drop(columns=["time"]).to_csv(index=False), "events.csv", "text/csv")


# ---- system -------------------------------------------------------------------------------------
with tab_system:
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        with st.container(border=True):
            st.markdown('<div class="sec">Detection setup</div>', unsafe_allow_html=True)
            if status is None:
                st.caption("Gateway offline.")
            else:
                st.markdown(f"**Baseline:** {'loaded' if status['baseline_loaded'] else 'not set'}")
                if not status["baseline_loaded"]:
                    st.caption("Record a normal run (lamp 2 off, then on), then run `python -m detection.calibrate` "
                               "and restart the gateway.")
                m = status["models"]
                st.markdown(f"**Isolation Forest:** {'loaded' if m.get('isolation_forest') else 'not trained'}  \n"
                            f"**Random Forest:** {'loaded' if m.get('random_forest') else 'not trained'}")
                if not all(m.values()):
                    st.caption("Until the models are trained, decisions come from the rule checks alone.")
        st.write("")
        with st.container(border=True):
            st.markdown('<div class="sec">What the states mean</div>', unsafe_allow_html=True)
            for key, (title, _, blurb) in view.LABELS.items():
                st.markdown(f"**{title}**  \n{blurb}")
    with c2:
        with st.container(border=True):
            st.markdown('<div class="sec">Project</div>', unsafe_allow_html=True)
            st.markdown(f"**{proj['title']}**  \n{proj['institution']}  \n{proj['department']}")
            st.markdown("**Team**  \n" + "  \n".join(proj["team"]))
            st.markdown("**Guided by**  \n" + "  \n".join(proj["guides"]))
